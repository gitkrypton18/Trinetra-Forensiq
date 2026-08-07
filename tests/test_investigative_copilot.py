"""Tests for the LLM Investigative Co-Pilot integrated into the FastAPI app.

Covers the bundle-driven SQLite builder, the NetworkX graph engine, the
deterministic CoT pipeline, SQL safety guards, and the /api/v1/copilot
endpoints mounted on the main API.
"""

import calendar
import datetime as dt

import pytest

from investigative_copilot.copilot_engine import InvestigativeCoPilotEngine
from investigative_copilot.db_builder import CopilotDBBuilder
from investigative_copilot.graph_engine import CopilotGraphEngine


def _ts(y, mo, d, h, mi):
    return float(calendar.timegm(dt.datetime(y, mo, d, h, mi).timetuple()))


@pytest.fixture(scope="module")
def copilot_bundle():
    return {
        "bank": [
            {
                "txn_id": "TXN1", "date": "2025-01-01", "time": "10:00:00",
                "ts": _ts(2025, 1, 1, 10, 0), "mode": "UPI", "txn_type": "D",
                "debit": 25000.0, "credit": None,
                "account_no": "ACC1001", "account_name": "Alice",
                "bank": "ICICI", "ifsc": "ICIC0001", "customer_id": "1001",
                "sender_phone": "+919160000001",
                "receiver_account": "ACC2002", "counterparty_name": "Bob",
                "counterparty_bank": "HDFC", "receiver_phone": "+919876543210",
            },
            {
                "txn_id": "TXN2", "date": "2025-01-02", "time": "11:30:00",
                "ts": _ts(2025, 1, 2, 11, 30), "mode": "IMPS", "txn_type": "D",
                "debit": 10000.0, "credit": None,
                "account_no": "ACC1001", "account_name": "Alice",
                "bank": "ICICI", "ifsc": "ICIC0001", "customer_id": "1001",
                "sender_phone": "+919160000001",
                "receiver_account": "ACC3003", "counterparty_name": "Carol",
                "counterparty_bank": "BOB", "receiver_phone": "+919999999999",
            },
        ],
        "cdr": [
            {
                "cdr_id": "CDR1", "date": "2025-01-01", "time": "10:05:00",
                "ts": _ts(2025, 1, 1, 10, 5), "a_number": "+919160000001",
                "b_number": "+919876543210", "call_type": "VOICE",
                "duration_sec": 120, "imsi": "404000000000001",
                "imei": "351111111111111", "bts_location_first": "WB_BTS_01",
                "roaming_circle": "West Bengal",
            },
            {
                "cdr_id": "CDR2", "date": "2025-01-02", "time": "11:35:00",
                "ts": _ts(2025, 1, 2, 11, 35), "a_number": "+919876543210",
                "b_number": "+919160000001", "call_type": "VOICE",
                "duration_sec": 60, "imsi": "404000000000002",
                "imei": "351111111111112", "bts_location_first": "WB_BTS_01",
                "roaming_circle": "West Bengal",
            },
        ],
        "ipdr": [
            {
                "ipdr_id": "IP1", "date": "2025-01-01", "start_time": "10:10:00",
                "start_ts": _ts(2025, 1, 1, 10, 10), "imsi": "404000000000001",
                "msisdn": "+919160000001", "imei": "351111111111111",
                "source_ip": "10.1.1.5", "dest_ip": "198.51.100.5",
                "dest_port": "443", "cell_id": "404-45-1-1", "duration_sec": 300,
            },
        ],
        "complaints": [
            {
                "complaint_id": "ACK9001", "acknowledgement_no": "ACK9001",
                "account_no": "ACC1001", "ifsc": "ICIC0001",
                "state": "West Bengal", "district": "Kolkata",
                "police_station": "Kolkata PS", "complainant_name": "Officer X",
                "designation": "PI", "mobile": "+919160000001", "email": "",
            },
        ],
        "subscribers": [
            {
                "phone": "+919160000001", "imsi": "404000000000001",
                "imei": "351111111111111", "name": "Alice",
                "circle": "West Bengal", "operator": "Jio",
            },
        ],
        "entities": {},
    }


@pytest.fixture(scope="module")
def db_conn(copilot_bundle):
    builder = CopilotDBBuilder()
    return builder.build_database_from_bundle(copilot_bundle)


@pytest.fixture(scope="module")
def graph_engine(db_conn):
    return CopilotGraphEngine(db_conn)


@pytest.fixture(scope="module")
def copilot_engine(db_conn):
    return InvestigativeCoPilotEngine(conn=db_conn)


def test_db_builder_schema_and_counts(db_conn):
    assert db_conn is not None
    cursor = db_conn.cursor()
    for table in ("bank_transactions", "cdr_records", "ipdr_records",
                  "bank_cdr_links", "cdr_ipdr_links", "anomaly_records",
                  "complaints", "subscribers"):
        cursor.execute(f"SELECT count(*) as c FROM {table}")
        cnt = cursor.fetchone()["c"]
        assert cnt >= 0, f"{table} should be queryable"

    cursor.execute("SELECT count(*) as c FROM bank_transactions")
    assert cursor.fetchone()["c"] == 2
    cursor.execute("SELECT count(*) as c FROM cdr_records")
    assert cursor.fetchone()["c"] == 2
    cursor.execute("SELECT count(*) as c FROM ipdr_records")
    assert cursor.fetchone()["c"] == 1
    cursor.execute("SELECT count(*) as c FROM bank_cdr_links")
    assert cursor.fetchone()["c"] == 2
    cursor.execute("SELECT count(*) as c FROM cdr_ipdr_links")
    assert cursor.fetchone()["c"] == 1
    cursor.execute("SELECT count(*) as c FROM complaints")
    assert cursor.fetchone()["c"] == 1
    cursor.execute("SELECT count(*) as c FROM subscribers")
    assert cursor.fetchone()["c"] == 1


def test_graph_engine_3_hops(graph_engine):
    trace_res = graph_engine.trace_mule_chain("ACC1001", max_hops=3)
    assert trace_res["found"] is True
    assert trace_res["max_hops"] == 3
    assert "Layer-1 Mules" in trace_res["layers"]
    assert trace_res["layers"]["Layer-1 Mules"]


def test_copilot_west_bengal_query(copilot_engine):
    res = copilot_engine.analyze_query(
        "Show me all accounts that received money within 5 minutes of a call "
        "originating from West Bengal tower locations.")
    assert res["execution_success"] is True
    assert len(res["chain_of_thought"]) == 5
    assert "West Bengal" in res["intent"] or "5 minutes" in res["intent"]
    assert res["executive_summary"] != ""


def test_copilot_mule_trace_query(copilot_engine):
    res = copilot_engine.analyze_query(
        "Trace the 3-hop mule money flow from 1001.")
    assert res["execution_success"] is True
    assert "graph_traversal" in res
    assert res["graph_traversal"]["max_hops"] == 3
    assert res["graph_traversal"]["found"] is True


def test_copilot_complaint_query(copilot_engine):
    res = copilot_engine.analyze_query("Show NCRP complaints for 1001.")
    assert res["execution_success"] is True
    assert "complaints" in res["generated_sql"]
    assert len(res["records"]) >= 1
    assert res["linking_tree"]["found"] is True


def test_copilot_phone_query(copilot_engine):
    res = copilot_engine.analyze_query(
        "Trace all activity for phone 9160000001.")
    assert res["execution_success"] is True
    assert "sender_phone_number" in res["generated_sql"]
    assert res["linking_tree"]["found"] is True


def test_copilot_account_query(copilot_engine):
    res = copilot_engine.analyze_query("Show me the full account profile for 1001.")
    assert res["execution_success"] is True
    assert res["row_count"] >= 1


def test_copilot_amount_query(copilot_engine):
    res = copilot_engine.analyze_query("Show UPI transactions greater than 15000.")
    assert res["execution_success"] is True
    assert res["row_count"] >= 1
    assert "UPI" in res["generated_sql"].upper()


def test_copilot_top_receivers_query(copilot_engine):
    res = copilot_engine.analyze_query("Who are the top receivers showing layering?")
    assert res["execution_success"] is True
    assert "GROUP BY" in res["generated_sql"].upper()
    assert res["row_count"] >= 1


def test_linking_tree_method(graph_engine):
    tree = graph_engine.linking_tree("TXN1", max_hops=3)
    assert tree["found"] is True
    assert len(tree["layers"]) >= 2
    assert tree["layers"][0]["label"] == "Layer-0 (Source)"
    assert any(t["txn_id"] == "TXN1"
               for layer in tree["layers"] for t in layer["transactions"])


def test_sql_safety_guard(copilot_engine):
    with pytest.raises(ValueError, match="Security violation"):
        copilot_engine._execute_safe_sql("DROP TABLE bank_transactions;")
    with pytest.raises(ValueError, match="Security violation"):
        copilot_engine._execute_safe_sql("DELETE FROM cdr_records;")


def test_fastapi_copilot_endpoints(client, synthetic_fixtures_dir):
    r = client.post("/ingest", json={"folder": str(synthetic_fixtures_dir)})
    assert r.status_code == 200

    # GET /api/v1/copilot/schema
    resp_schema = client.get("/api/v1/copilot/schema")
    assert resp_schema.status_code == 200
    assert len(resp_schema.json()["sample_queries"]) >= 4

    # GET /api/v1/copilot/stats
    resp_stats = client.get("/api/v1/copilot/stats")
    assert resp_stats.status_code == 200
    data_stats = resp_stats.json()
    assert data_stats["dataset_source"] == "bundle"
    assert data_stats["max_graph_hops"] == 3
    assert data_stats["tables"]["bank_transactions"] >= 2
    assert data_stats["tables"]["cdr_records"] >= 2

    # POST /api/v1/copilot/query
    resp_q = client.post("/api/v1/copilot/query", json={
        "query": "Show me all accounts that received money within 5 minutes "
                 "of a call originating from West Bengal tower locations."
    })
    assert resp_q.status_code == 200
    data_q = resp_q.json()
    assert data_q["execution_success"] is True
    assert len(data_q["chain_of_thought"]) == 5

    # POST /api/v1/copilot/summarize-cluster with an account id
    resp_sum = client.post("/api/v1/copilot/summarize-cluster", json={
        "entity_ids": ["ACC001"]
    })
    assert resp_sum.status_code == 200
    data_sum = resp_sum.json()
    assert "executive_summary" in data_sum
    assert "Layer-1 mule" in data_sum["executive_summary"]

    # POST /api/v1/copilot/summarize-cluster with a transaction id
    resp_tx = client.post("/api/v1/copilot/summarize-cluster", json={
        "entity_ids": ["TXN1"]
    })
    assert resp_tx.status_code == 200
    data_tx = resp_tx.json()
    assert data_tx["graph_analysis"]["found"] is True
    assert "Layer-1 mule" in data_tx["executive_summary"]

    # GET /api/v1/copilot/graph/{entity_id}
    resp_g = client.get("/api/v1/copilot/graph/ACC001")
    assert resp_g.status_code == 200
    assert resp_g.json()["found"] is True


def test_fastapi_copilot_tree_and_fused(client, synthetic_fixtures_dir):
    r = client.post("/ingest", json={"folder": str(synthetic_fixtures_dir)})
    assert r.status_code == 200

    # Linking-tree endpoint
    t = client.get("/api/v1/copilot/tree/TXN1")
    assert t.status_code == 200
    tree = t.json()
    assert tree["found"] is True
    assert len(tree["layers"]) >= 1

    # Fused data preview (the post-ingestion fusion view)
    f = client.get("/data/fused?limit=10")
    assert f.status_code == 200
    fused = f.json()
    assert fused["total"] >= 2
    row = next(r for r in fused["rows"] if r["transaction_id"] == "TXN1")
    assert row["call_count"] >= 1
    assert row["ipdr_count"] >= 1

    # Fused CSV export
    csv_resp = client.get("/data/fused.csv")
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert "transaction_id" in csv_resp.text

    # Risk annotation
    fr = client.get("/data/fused?limit=10&risk_annotate=1")
    assert fr.status_code == 200
    assert "risk_score" in fr.json()["rows"][0]


def test_fastapi_copilot_requires_data(client):
    """Without an ingested bundle the copilot endpoints fail cleanly."""
    resp_stats = client.get("/api/v1/copilot/stats")
    assert resp_stats.status_code == 409

    resp_q = client.post("/api/v1/copilot/query", json={"query": "test"})
    assert resp_q.status_code == 409


def test_fastapi_copilot_requires_auth(client):
    """Copilot endpoints are protected like the rest of the API."""
    client.headers.pop("Authorization", None)
    assert client.get("/api/v1/copilot/schema").status_code == 401
    assert client.get("/api/v1/copilot/stats").status_code == 401
    assert client.post("/api/v1/copilot/query",
                       json={"query": "test"}).status_code == 401


# ---------------------------------------------------------------------------
# Investigation intelligence layer (OmniWatcher spec: section 3-4, 11-12)
# ---------------------------------------------------------------------------


def _assert_intel_shape(data):
    """Every query envelope must carry the AI Investigation Assistant block."""
    assert "entity_resolution" in data
    er = data["entity_resolution"]
    assert {"entity_id", "entity_type", "resolved"} <= set(er)

    s = data["investigation_summary"]
    assert {"found_transactions", "total_amount", "highest_risk",
            "primary_account", "common_phone", "linked_ips",
            "linked_beneficiaries", "narrative"} <= set(s)
    assert isinstance(s["found_transactions"], int)
    assert s["narrative"]

    m = data["metrics"]
    assert {"records", "total_amount", "accounts", "phones", "ips",
            "beneficiaries", "highest_risk", "avg_risk"} <= set(m)

    assert isinstance(data["insights"], list)
    assert isinstance(data["suggestions"], list)
    assert isinstance(data["explanation"], list)
    assert len(data["explanation"]) >= 1


def test_entity_resolution_types(copilot_engine):
    from investigative_copilot.copilot_engine import _resolve_entity_type
    assert _resolve_entity_type("9160000001") == "phone"
    assert _resolve_entity_type("+919160000001") == "phone"
    assert _resolve_entity_type("919160000001") == "phone"
    assert _resolve_entity_type("351111111111111") == "imei"
    assert _resolve_entity_type("10.1.1.5") == "ip"
    assert _resolve_entity_type("TXN250103XYZ") == "transaction"
    assert _resolve_entity_type("ICIC0001234") == "ifsc"
    # DB-backed resolution refines ambiguous identifiers
    assert copilot_engine._resolve_entity_in_db("ACC1001") == "account"
    assert copilot_engine._resolve_entity_in_db("ACK9001") == "complaint"
    assert copilot_engine._resolve_entity_in_db("9160000001") == "phone"


def test_investigation_intel_mule_query(copilot_engine):
    res = copilot_engine.analyze_query("Trace the 3-hop mule flow from ACC1001")
    _assert_intel_shape(res)
    assert res["entity_resolution"]["entity_type"] == "account"
    assert res["entity_resolution"]["entity_id"] == "ACC1001"
    assert res["investigation_summary"]["found_transactions"] >= 1
    assert res["investigation_summary"]["total_amount"] > 0
    assert res["metrics"]["records"] >= 1
    assert res["linking_tree"]["found"] is True
    for rec in res["records"]:
        assert 0 <= rec["risk_score"] <= 100
        assert rec["risk_band"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL", "SEVERE")


def test_investigation_intel_phone_query(copilot_engine):
    res = copilot_engine.analyze_query("Trace all activity for phone 9160000001")
    _assert_intel_shape(res)
    assert res["entity_resolution"]["entity_type"] == "phone"
    assert res["entity_resolution"]["entity_id"] == "9160000001"


def test_investigation_intel_amount_query(copilot_engine):
    res = copilot_engine.analyze_query(
        "Show UPI transactions greater than 20000")
    _assert_intel_shape(res)
    if res["investigation_summary"]["found_transactions"]:
        # even without an explicit identifier the engine resolves the
        # primary account from the result set
        assert res["entity_resolution"]["resolved"] is True
        assert res["entity_resolution"]["entity_id"] == \
            res["investigation_summary"]["primary_account"]
    if res["records"]:
        amounts = [r["risk_score"] for r in res["records"]]
        assert res["metrics"]["highest_risk"] == max(amounts)
        assert res["metrics"]["avg_risk"] >= 0
    assert any(s.get("action") == "Investigate Entity"
               for s in res["suggestions"])


def test_investigation_intel_explain_and_suggest(copilot_engine):
    res = copilot_engine.analyze_query("Who are the top receivers showing layering")
    _assert_intel_shape(res)
    assert res["investigation_summary"]["found_transactions"] >= 1
    # every suggestion is actionable (carries a query) and explains itself
    for s in res["suggestions"]:
        assert {"action", "target", "why", "query"} <= set(s)
        assert s["query"]


def test_investigation_intel_night_and_risk_scoring(copilot_engine):
    """A night-hour UPI transfer ≥ 25k must score as HIGH or above."""
    cursor = copilot_engine.conn.cursor()
    cursor.execute("""
        INSERT INTO bank_transactions(
            transaction_id, timestamp, transaction_amount, transaction_mode,
            sender_account_number, sender_customer_name,
            receiver_account_number, receiver_customer_name)
        VALUES('TXNNIGHT1', '2025-01-03 23:45:00', 400000, 'UPI',
               'ACC1001', 'Alice', 'ACCDARK', 'Dave')
    """)
    copilot_engine.conn.commit()
    res = copilot_engine.analyze_query(
        "Show all transactions greater than 100000")
    row = next(r for r in res["records"]
               if r.get("transaction_id") == "TXNNIGHT1")
    assert row["risk_score"] >= 55
    assert row["risk_band"] in ("HIGH", "CRITICAL", "SEVERE")
    assert res["investigation_summary"]["highest_risk"] >= 55


def test_fastapi_copilot_intel_block(client, synthetic_fixtures_dir):
    client.post("/ingest", json={"folder": str(synthetic_fixtures_dir)})
    resp = client.post("/api/v1/copilot/query", json={
        "query": "Show me all accounts that received money within 5 minutes "
                 "of a call originating from West Bengal tower locations."
    })
    assert resp.status_code == 200
    data = resp.json()
    _assert_intel_shape(data)
    assert data["entity_resolution"]["entity_type"] == "identifier"
    assert data["metrics"]["records"] >= 0
    if data["records"]:
        assert 0 <= data["records"][0]["risk_score"] <= 100
