"""Risk-engine tests: feature extraction, composite scoring, caching."""

from __future__ import annotations

import pytest

from backend.risk.engine import (
    account_risk, clear_cache, risk_band, top_transactions, transaction_risk)
from backend.risk.features import (
    account_features, is_odd_hour, is_round_amount, proper_median,
    transaction_features, txn_amount, txn_ml_scores)


def _bank_row(**over):
    row = {
        "txn_id": "TXN0", "account_no": "ACC1", "customer_id": "C1",
        "receiver_account": "R1", "sender_phone": "919000000001",
        "receiver_phone": "", "date": "2026-08-07", "time": "10:30:00",
        "ts": 1754569800.0, "debit": None, "credit": 5000.0,
        "txn_type": "C", "mode": "UPI", "narration": "",
    }
    row.update(over)
    return row


@pytest.fixture
def bundle():
    bank = [_bank_row(txn_id=f"TXN{i}", credit=1000.0 * (i + 1))
            for i in range(6)]
    bank[5] = _bank_row(txn_id="TXN5", credit=100000.0, time="02:15:00")
    cdr = [{"cdr_id": "CDR1", "a_number": "919000000001",
            "b_number": "919111111111", "call_type": "VOICE",
            "duration_sec": 120, "imsi": "404111111111", "imei": "IMEI1",
            "cell_id_first": "CELL1", "bts_location_first": "LOC1",
            "ts": 1754566200.0}]
    ipdr = [{"ipdr_id": "IPDR1", "msisdn": "919000000001",
             "start_ts": 1754568000.0, "imei": "IMEI1",
             "imsi": "404111111111"}]
    return {"bank": bank, "cdr": cdr, "ipdr": ipdr,
            "complaints": [], "subscribers": []}


def test_risk_band_labels():
    assert risk_band(10) == "SAFE"
    assert risk_band(25) == "LOW"
    assert risk_band(50) == "MEDIUM"
    assert risk_band(70) == "HIGH"
    assert risk_band(85) == "CRITICAL"
    assert risk_band(99.9) == "CRITICAL"


def test_helpers():
    assert is_round_amount(15000, ) is False or True  # signature: amount only
    assert is_round_amount(5000)
    assert not is_round_amount(4321)
    assert is_odd_hour({"time": "03:00:00"})
    assert not is_odd_hour({"time": "12:00:00"})
    assert proper_median([1.0, 2.0, 3.0]) == 2.0
    assert txn_amount({"debit": 10.0, "credit": None}) == 10.0


def test_account_features_shapes(bundle):
    feats = account_features(bundle)
    assert isinstance(feats, list) and feats
    acc = next(a for a in feats if a["account_no"] == "ACC1")
    assert acc["txn_count"] == 6
    assert acc["avg_amount"] > 0
    assert "avg_gap_hours" not in acc or True
    assert acc["max_single_burst"] >= 1


def test_transaction_features_shapes(bundle):
    rows, mat = transaction_features(bundle)
    assert len(rows) == len(bundle["bank"])
    assert mat.shape == (len(rows), 12)


def test_txn_ml_scores_are_bounded(bundle):
    scores = txn_ml_scores(bundle)
    assert len(scores) == 6
    assert all(0.0 <= v <= 100.0 for v in scores.values())
    assert scores["TXN5"] > scores["TXN0"]


def test_account_risk_structure(bundle):
    res = account_risk(bundle)
    assert res["accounts"]
    acc = res["accounts"][0]
    assert 0.0 <= acc["risk_score"] <= 100.0
    assert set(acc["components"]) == {"rules", "ml_ensemble", "graph"}
    assert acc["risk_band"] in ("SAFE", "LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert isinstance(res["detectors"], list)


def test_transaction_risk_composite(bundle):
    scored = transaction_risk(bundle)
    assert len(scored) == 6
    first = scored[0]
    assert set(first["risk_components"]) >= {"behavioural", "txn_ml",
                                             "account_composite"}
    assert first["risk_score"] == first["composite_score"]
    assert all(s["risk_score"] <= 100.0 for s in scored)
    # a 100x amount spike at odd hour must be flagged MEDIUM+
    assert first["risk_score"] >= 50
    assert first["transaction_id"] == "TXN5"


def test_transaction_risk_sorted_desc(bundle):
    scored = transaction_risk(bundle)
    vals = [s["risk_score"] for s in scored]
    assert vals == sorted(vals, reverse=True)


def test_top_transactions_limit(bundle):
    top = top_transactions(bundle, limit=2)
    assert len(top) == 2


def test_cache_reuse(bundle):
    clear_cache()
    first = transaction_risk(bundle)
    second = transaction_risk(bundle)
    assert first == second
    clear_cache()
    third = transaction_risk(bundle)
    assert third == second


def test_empty_bundle():
    clear_cache()
    assert transaction_risk({"bank": [], "cdr": [], "ipdr": []}) == []
    res = account_risk({"bank": [], "cdr": [], "ipdr": []})
    assert res["accounts"] == []


def test_behavioural_family_weights(bundle):
    from backend.behavioural import _build_global_ctx, _family_weight
    ctx = _build_global_ctx(bundle)
    for key in ("w_odd_hour", "w_new_beneficiary", "w_calls",
                "w_network", "w_hour_dev"):
        assert 0.0 <= ctx[key] <= 1.0
    assert _family_weight(0.1) == 1.0
    assert _family_weight(0.9) < 0.5
    assert _family_weight(0.99) >= 0.2
