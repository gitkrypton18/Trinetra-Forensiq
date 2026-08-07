"""Hybrid Fraud Detection Engine tests: weights, profiling, temporal,
entity risk, telecom/internet, money-flow, scenarios, explainability and
the composite orchestrator — including robustness on degenerate bundles."""

from __future__ import annotations

import pytest

from backend.risk.entity_risk import entity_risk
from backend.risk.explain import (explain_account, explain_entity,
                                  explain_transaction)
from backend.risk.graph_features import graph_features
from backend.risk.hybrid import (clear_hybrid_cache, explanations_for_account,
                                 explanations_for_entity,
                                 explanations_for_txn, hybrid_account_risk,
                                 hybrid_analyze, hybrid_entity_risk,
                                 hybrid_transaction_risk, hybrid_weights)
from backend.risk.internet import internet_scores
from backend.risk.moneyflow import money_flow_analysis
from backend.risk.profiles import (account_profile_deviation,
                                   profile_deviation)
from backend.risk.scenarios import detect_account_scenarios
from backend.risk.telecom import telecom_scores
from backend.risk.temporal import (account_temporal_scores,
                                   txn_temporal_scores)
from backend.risk.weights import renormalise


@pytest.fixture
def bundle():
    """Deterministic bundle with deliberate fraud signals:
    TXN1 is a rapid in-out + call-assisted + shared-phone case."""
    ts = 1700000000
    return {
        "bank": [
            {"txn_id": "TXN1", "account_no": "ACC1", "customer_id": "C1",
             "sender_phone": "919000000001", "receiver_phone": "919000000009",
             "receiver_account": "ACC9", "ts": ts, "date": "2024-11-14",
             "time": "10:00:00", "debit": 950000.0, "credit": None,
             "mode": "RTGS", "counterparty_name": "Party9"},
            {"txn_id": "TXN2", "account_no": "ACC1", "customer_id": "C1",
             "sender_phone": "919000000001", "receiver_phone": "919000000002",
             "receiver_account": "ACC2", "ts": ts + 60, "date": "2024-11-14",
             "time": "10:01:00", "debit": 950000.0, "credit": None,
             "mode": "RTGS", "counterparty_name": "Party2"},
            {"txn_id": "TXN3", "account_no": "ACC2", "customer_id": "C2",
             "sender_phone": "919000000002", "receiver_phone": "919000000001",
             "receiver_account": "ACC1", "ts": ts + 120, "date": "2024-11-14",
             "time": "10:02:00", "debit": 950000.0, "credit": None,
             "mode": "RTGS", "counterparty_name": "Party1"},
            {"txn_id": "TXN4", "account_no": "ACC1", "customer_id": "C1",
             "sender_phone": "919000000001", "receiver_phone": "919000000009",
             "receiver_account": "ACC9", "ts": ts + 180, "date": "2024-11-14",
             "time": "10:03:00", "debit": 950000.0, "credit": None,
             "mode": "RTGS", "counterparty_name": "Party9"},
            {"txn_id": "TXN5", "account_no": "ACC9", "customer_id": "C9",
             "sender_phone": "919000000001", "receiver_phone": "919000000009",
             "receiver_account": "ACC10", "ts": ts + 240, "date": "2024-11-14",
             "time": "10:04:00", "debit": 950000.0, "credit": None,
             "mode": "RTGS", "counterparty_name": "Party10"},
        ],
        "cdr": [
            {"cdr_id": "CDR1", "a_number": "919000000001",
             "b_number": "919000000009", "call_type": "VOICE",
             "ts": ts - 120, "duration_sec": 120},
            {"cdr_id": "CDR2", "a_number": "919000000001",
             "b_number": "919000000009", "call_type": "VOICE",
             "ts": ts - 90, "duration_sec": 90},
            {"cdr_id": "CDR3", "a_number": "919000000001",
             "b_number": "919000000009", "call_type": "VOICE",
             "ts": ts - 60, "duration_sec": 60},
        ],
        "ipdr": [
            {"ipdr_id": "IP1", "msisdn": "919000000001",
             "ip": "2409:1:1:1::1", "start_ts": ts - 60,
             "imei": "IMEI-1", "imsi": "IMSI-1", "cell_id": "CELL-1"},
            {"ipdr_id": "IP2", "msisdn": "919000000001",
             "ip": "2409:1:1:1::1", "start_ts": ts - 30,
             "imei": "IMEI-1", "imsi": "IMSI-1", "cell_id": "CELL-1"},
            {"ipdr_id": "IP3", "msisdn": "919000000001",
             "ip": "2409:1:1:1::1", "start_ts": ts,
             "imei": "IMEI-1", "imsi": "IMSI-1", "cell_id": "CELL-1"},
            {"ipdr_id": "IP4", "msisdn": "919000000002",
             "ip": "2409:1:1:1::1", "start_ts": ts + 30,
             "imei": "IMEI-2", "imsi": "IMSI-2", "cell_id": "CELL-2"},
            {"ipdr_id": "IP5", "msisdn": "919000000009",
             "ip": "2409:1:1:1::1", "start_ts": ts + 60,
             "imei": "IMEI-9", "imsi": "IMSI-9", "cell_id": "CELL-3"},
        ],
        "complaints": [
            {"ref": "NCRP-1", "account_no": "ACC2",
             "complainant_name": "Victim"},
        ],
        "subscribers": [],
    }


def test_weights_renormalise():
    w = renormalise({"txn_rules": 50, "txn_ml": 100})
    assert w > 0 and w <= 100
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("APP_HYBRID_TXN_RULES", "0.5")
        from backend.risk.weights import hybrid_weights, weight
        wts = hybrid_weights()
        assert wts["txn_rules"] == 0.5
        assert wts["txn_ml"] == 0.2
        assert weight("txn_rules") == 0.5


def test_profile_deviation_flags_anomalous(bundle):
    prof = profile_deviation(bundle)
    assert "TXN1" in prof
    assert 0.0 <= prof["TXN1"].get("score", 0) <= 100.0
    acc = account_profile_deviation(bundle)
    assert "ACC1" in acc
    assert 0.0 <= acc["ACC1"].get("behaviour_score", 0) <= 100.0


def test_temporal_scores(bundle):
    txn = txn_temporal_scores(bundle)
    acc = account_temporal_scores(bundle)
    assert "TXN1" in txn
    assert "ACC1" in acc
    assert 0.0 <= txn["TXN1"].get("temporal_score", 0) <= 100.0


def test_telecom_call_assist_and_network(bundle):
    tel = telecom_scores(bundle)
    assert tel["txn"]["TXN1"]["call_assist_score"] > 0
    assert tel["phone"]["919000000001"]["degree"] >= 1


def test_internet_shared_ip(bundle):
    net = internet_scores(bundle)
    assert net["txn"]["TXN1"]["internet_score"] > 0


def test_moneyflow_cycles(bundle):
    mf = money_flow_analysis(bundle)
    assert "ACC1" in mf["accounts"]
    assert mf["accounts"]["ACC1"]["layering_depth"] >= 1


def test_entity_risk_concentration(bundle):
    ent = entity_risk(bundle)
    assert ent["stats"]["phone"]["entity_count"] >= 1
    by_kind = ent["entities"]["phone"]
    assert any(e["account_count"] >= 2 for e in by_kind)


def test_scenarios_detect(bundle):
    from backend.risk.moneyflow import money_flow_analysis
    from backend.risk.scenarios import scenario_engine
    info = {"breakdown": {}, "profile": {}, "temporal": {}, "graph": {},
            "telecom": {"txn": {}}, "internet": {"txn": {}},
            "acc_profile": {}}
    res = scenario_engine(bundle, info,
                          moneyflow=money_flow_analysis(bundle),
                          entity=entity_risk(bundle))
    names = {s["scenario"] for s in res["account"].get("ACC1", [])}
    assert names & {"Rapid In-Out", "Circular Flow", "NCRP-linked"}


def test_hybrid_analyze_shape(bundle):
    res = hybrid_analyze(bundle)
    assert res["stats"]["total_txns"] == 5
    assert "TXN1" in res["transactions"]
    t = res["transactions"]["TXN1"]
    assert t["risk_band"] in ("SAFE", "LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert 0.0 <= t["risk_score"] <= 100.0
    assert set(t["hybrid_components"]) == {
        "rules", "ml", "behaviour", "temporal", "telecom", "internet"}
    assert set(t["models_fired"]) <= {
        "rules", "ml", "behaviour", "temporal", "telecom", "internet"}
    assert t["scenarios"]
    acc = res["accounts"]["ACC1"]
    assert set(acc["components"]) == {
        "rules", "ml_ensemble", "behaviour", "temporal", "graph",
        "entity", "moneyflow"}
    assert isinstance(acc["ml_detectors"], list)


def test_hybrid_api_entry_points(bundle):
    txns = hybrid_transaction_risk(bundle)
    ids = [t["transaction_id"] for t in txns]
    assert "TXN1" in ids
    accs = {a["account_no"] for a in hybrid_account_risk(bundle)}
    assert "ACC1" in accs
    ents = hybrid_entity_risk(bundle)
    assert all(e["risk_band"] in
               ("SAFE", "LOW", "MEDIUM", "HIGH", "CRITICAL") for e in ents)


def test_explainability(bundle):
    ex = explanations_for_txn(bundle, "TXN1")
    assert ex["narrative"]
    assert ex["recommendations"]
    assert ex["top_features"]
    assert isinstance(ex["timeline"], list)
    assert explanations_for_account(bundle, "ACC1")["narrative"]
    assert explanations_for_entity(bundle, "phone",
                                   "919000000001")["narrative"]
    # low-level explainers take (txn, info) or (acc, info) records
    res = hybrid_analyze(bundle)
    txn_info = res["transactions"]["TXN1"]
    acc_info = res["accounts"]["ACC1"]
    assert explain_transaction("TXN1", txn_info, txn_info)["narrative"]
    assert explain_account("ACC1", acc_info)["narrative"]


def test_hybrid_cache_and_clear(bundle):
    clear_hybrid_cache()
    r1 = hybrid_analyze(bundle)
    r2 = hybrid_analyze(bundle)  # cached
    assert r1["stats"] == r2["stats"]
    clear_hybrid_cache()
    r3 = hybrid_analyze(bundle)
    assert r3["stats"] == r1["stats"]


def test_empty_bundle_safe():
    b = {"bank": [], "cdr": [], "ipdr": [], "complaints": []}
    res = hybrid_analyze(b)
    assert res["stats"]["total_txns"] == 0
    assert hybrid_transaction_risk(b) == []
    assert hybrid_account_risk(b) == []
    assert hybrid_entity_risk(b) == []


def test_empty_txn_id_rows_do_not_collapse(bundle):
    import copy
    b = copy.deepcopy(bundle)
    for r in b["bank"][:3]:
        r["txn_id"] = ""
    res = hybrid_analyze(b)
    assert res["stats"]["total_txns"] == 5
    assert res["stats"]["transactions"] == 2
    assert "" not in res["transactions"]


def test_small_account_count_pca_safe():
    """PCA must not explode when accounts < component count."""
    b = {
        "bank": [
            {"txn_id": f"T{i}", "account_no": f"ACC{i % 2}", "ts": 1700000000 + i,
             "debit": 100.0 * i, "credit": None, "sender_phone": "",
             "receiver_phone": "", "receiver_account": "",
             "customer_id": f"C{i % 2}", "date": "2024-11-14", "time": "10:00:00",
             "mode": "UPI", "counterparty_name": ""}
            for i in range(4)
        ],
        "cdr": [], "ipdr": [], "complaints": [],
        "subscribers": [],
    }
    res = hybrid_analyze(b)
    assert res["stats"]["accounts"] >= 1


def test_hybrid_weights_exposed():
    w = hybrid_weights()
    for k in ("txn_rules", "txn_ml", "txn_behaviour", "txn_temporal",
              "txn_telecom", "txn_internet", "acc_rules", "acc_ml",
              "acc_behaviour", "acc_temporal", "acc_graph", "acc_entity",
              "acc_moneyflow", "ent_ml", "ent_graph", "ent_temporal",
              "ent_telecom", "ent_internet"):
        assert k in w
    assert w["txn_rules"] > 0


def test_graph_features_small_bundle(bundle):
    feats, meta = graph_features(bundle)
    assert meta["nodes"] >= 3
    assert "ACC1" in feats
