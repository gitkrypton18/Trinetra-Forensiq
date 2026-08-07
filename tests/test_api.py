"""API-level tests against the real FastAPI app (TestClient)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend import api


def _ingest(client: TestClient, fixtures_dir) -> dict:
    r = client.post("/ingest", json={"folder": str(fixtures_dir)})
    assert r.status_code == 200, r.text
    return r.json()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "last_ingested" in body


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["name"] == "Financial & Telecom Analysis API"


def test_ingest_bad_folder(client):
    r = client.post("/ingest", json={"folder": "C:/does/not/exist"})
    assert r.status_code == 400


def test_ingest_then_summary(client, fixtures_dir):
    body = _ingest(client, fixtures_dir)
    assert body["bank"] == 5
    assert body["cdr"] == 3
    assert body["ipdr"] == 2
    assert body["complaints"] == 2
    assert body["errors"] == []

    s = client.get("/summary").json()
    assert s["bank_records"] == 5
    assert s["entities"]["phones"] >= 2
    assert s["entities"]["accounts"] >= 1


def test_scoring_alerts_flags_ncrp_account(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    a = client.get("/scoring/alerts?min_risk=50").json()
    ids = [x["sender_customer_id"] for x in a["results"]]
    assert "924010036411120" in ids
    alert = next(x for x in a["results"]
                 if x["sender_customer_id"] == "924010036411120")
    assert alert["risk_score"] >= 60
    assert "NCRP_FRAUD_ACCOUNT" in alert["rules_fired"]
    assert alert["risk_band"] in ("HIGH", "CRITICAL")
    assert isinstance(alert["amount_usd"], float)
    assert alert["transaction_id"]


def test_accounts_phones_payouts_timeline(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    assert client.get("/accounts?min_score=0").status_code == 200
    assert client.get("/phones").status_code == 200
    assert client.get("/payouts").status_code == 200
    tl = client.get("/timeline").json()
    assert tl["count"] >= 1
    co = client.get("/coincidence").json()
    assert "hits" in co


def test_account_detail(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    r = client.get("/account/924010036411120")
    assert r.status_code == 200
    assert r.json()["profile"]["account_no"] == "924010036411120"
    assert client.get("/account/000000").status_code == 404


def test_phone_egonet(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    r = client.get("/phone/916000000001/egonet?mode=full")
    assert r.status_code == 200
    assert r.json()["node"] == "916000000001"
    assert any(n["id"] == "919876543210" for n in r.json()["nodes"])


def test_phone_egonet_missing_node_no_500(client, fixtures_dir):
    """Regression: ego-graph on a phone absent from the CDR must be 200."""
    _ingest(client, fixtures_dir)
    for mode in ("evidence", "full"):
        r = client.get(f"/phone/999999999999/egonet?mode={mode}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["node"] == "999999999999"
        assert body["nodes"] == []
        assert body["edges"] == []


def test_phone_egonet_evidence_mode(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    r = client.get("/phone/916000000001/egonet?mode=evidence")
    assert r.status_code == 200
    body = r.json()
    assert body["node"] == "916000000001"
    assert "filtered" in body and "kept" in body and "total" in body
    for n in body["nodes"]:
        assert "risk" in n and "degree" in n


def test_entity_evidence_endpoint(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    acct = client.get("/entity/account/924010036411120")
    assert acct.status_code == 200
    a = acct.json()
    assert a["risk_score"] >= 60
    assert a["breakdown"]  # explainable rules
    assert a["counts"]["transactions"] == 5
    assert a["activity"]["first"]
    assert client.get("/entity/phone/916000000001").status_code == 200
    assert client.get("/entity/phone/9999999999").status_code == 404
    assert client.get("/entity/banana/x").status_code == 400


def test_relationship_endpoint(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    r = client.get("/relationship/916000000001/919876543210")
    assert r.status_code == 200
    body = r.json()
    assert body["a"] == "916000000001"
    assert "calls" in body and "evidence" in body
    assert body["relationship"] in ("call", "money", "mixed", None)


def test_device_and_ip_graphs(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    d = client.get("/graph/device?phone=916000000001").json()
    assert "nodes" in d and "edges" in d
    ip = client.get("/graph/ip?phone=916000000001").json()
    assert "nodes" in ip and "edges" in ip


def test_entity_report_pdf(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    r = client.get("/report/entity/account/924010036411120")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert len(r.content) > 1000
    assert client.get("/report/entity/phone/9999999999").status_code == 404


def test_synthetic_csv_ingestion(client, synthetic_fixtures_dir):
    """Problem-statement clean/anomalous CSVs must parse via the pipeline."""
    body = client.post("/ingest",
                       json={"folder": str(synthetic_fixtures_dir)}).json()
    assert body["errors"] == []
    assert body["bank"] >= 1
    assert body["cdr"] >= 1
    assert body["ipdr"] >= 1
    s = client.get("/summary").json()
    assert s["bank_records"] >= 1
    assert s["cdr_records"] >= 1
    assert s["ipdr_records"] >= 1


def test_report_pdf(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    r = client.get("/report")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert len(r.content) > 1000


def test_upload_parse_multi(client, fixtures_dir):
    r = client.post(
        "/upload/parse-multi",
        files=[
            ("files", ("bank_statement.csv",
                       (fixtures_dir / "bank_statement.csv").read_bytes(),
                       "text/csv")),
            ("files", ("cdr_jio_vvm.csv",
                       (fixtures_dir / "cdr_jio_vvm.csv").read_bytes(),
                       "text/csv")),
            ("files", ("complain.csv",
                       (fixtures_dir / "All Account complain.csv").read_bytes(),
                       "text/csv")),
        ],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["detail"] == "fusion complete"
    assert len(body["files"]) == 3
    assert body["bank"] == 5
    assert body["cdr"] == 3
    alerts = client.get("/scoring/alerts?min_risk=50").json()
    assert len(alerts["results"]) >= 1


def test_persistence_across_restart(client, fixtures_dir):
    """After /ingest the bundle survives a simulated process restart."""
    _ingest(client, fixtures_dir)
    client.close()

    api._state.clear()
    with TestClient(api.app) as c2:  # startup hook reloads from the store
        tok = c2.post("/auth/login", json={"username": "tester",
                                           "password": "testpass123"}).json()
        auth_h = {"Authorization": f"Bearer {tok['access_token']}"}
        s = c2.get("/summary", headers=auth_h)
        assert s.status_code == 200, s.text
        assert s.json()["bank_records"] == 5


def test_ingest_status_and_clear(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    st = client.get("/ingest/status").json()
    assert st["loaded"] is True
    assert st["bank"] == 5
    d = client.delete("/ingest")
    assert d.status_code == 200
    st2 = client.get("/ingest/status").json()
    assert st2["loaded"] is False
    assert client.get("/summary").status_code == 409


def test_money_graph_endpoint(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    r = client.get("/graph/money")
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body and "edges" in body and "stats" in body
    assert body["stats"]["nodes"] >= 0


def test_account_phone_graph_endpoint(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    body = client.get("/graph/account-phone").json()
    assert "nodes" in body and "edges" in body


def test_central_phones_endpoint(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    body = client.get("/graph/central-phones?top=5").json()
    assert "phones" in body
    phones = [p["phone"] for p in body["phones"]]
    assert "916000000001" in phones  # highest degree in the fixture CDR


def test_flows_patterns_endpoint(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    body = client.get("/flows/patterns").json()
    assert "circular" in body and "rapid_in_out" in body
    assert isinstance(body["circular"], list)


def test_ml_outliers_endpoint(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    body = client.get("/ml/outliers").json()
    assert "fitted" in body
    assert isinstance(body["accounts"], list)


def test_search_endpoint(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    by_phone = client.get("/search?q=916000000001").json()
    assert by_phone["total"] >= 1
    kinds = {r["kind"] for r in by_phone["results"]}
    assert "phone" in kinds or "account" in kinds or "transaction" in kinds
    by_ncrp = client.get("/search?q=924010036411120").json()
    assert by_ncrp["total"] >= 1
    empty = client.get("/search?q=").json()
    assert empty["total"] == 0


# ---------------------------------------------------------------- risk engine


def test_risk_accounts_endpoint(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    r = client.get("/risk/accounts")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["accounts"], list)
    assert body["accounts"], "fixture must produce at least one risk account"
    acc = body["accounts"][0]
    assert 0.0 <= acc["risk_score"] <= 100.0
    assert set(acc["components"]) == {"rules", "ml_ensemble", "graph"}
    filtered = client.get("/risk/accounts?min_score=99.9").json()
    assert filtered["accounts"] == []


def test_risk_transactions_endpoint(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    r = client.get("/risk/transactions")
    assert r.status_code == 200
    body = r.json()
    assert body["results"], "fixture must produce scored transactions"
    first = body["results"][0]
    assert "transaction_id" in first
    assert "risk_components" in first
    assert set(first["risk_components"]) >= {"behavioural", "txn_ml",
                                             "account_composite"}
    banded = client.get("/risk/transactions?band=CRITICAL").json()
    assert all(x["risk_band"] == "CRITICAL" for x in banded["results"])
    limited = client.get("/risk/transactions?limit=1").json()
    assert len(limited["results"]) == 1


def test_anomalies_top50_endpoint(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    r = client.get("/anomalies/top-50")
    assert r.status_code == 200
    body = r.json()
    assert len(body["results"]) <= 50
    scores = [x["risk_score"] for x in body["results"]]
    assert scores == sorted(scores, reverse=True)


def test_transaction_detail_endpoint(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    top = client.get("/anomalies/top-50").json()["results"]
    tid = top[0]["transaction_id"]
    r = client.get(f"/transactions/{tid}")
    assert r.status_code == 200
    body = r.json()["transaction"]
    assert body["transaction_id"] == tid
    assert "risk_components" in body and "evidence" in body
    assert client.get("/transactions/DOESNOTEXIST1").status_code == 404


def test_transaction_report_endpoint(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    tid = client.get("/anomalies/top-50").json()["results"][0]["transaction_id"]
    r = client.get(f"/report/transaction/{tid}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"
    assert client.get("/report/transaction/DOESNOTEXIST1").status_code == 404


def test_loading_status_endpoint(client, fixtures_dir):
    st = client.get("/loading/status").json()
    assert st["loaded"] is False
    _ingest(client, fixtures_dir)
    st = client.get("/loading/status").json()
    assert st["loaded"] is True
    assert st["bank"] == 5
    assert "last_ingested" in st


def test_investigation_tree_endpoint(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    inv = client.post("/investigations",
                      json={"title": "case 1", "notes": "probe"}).json()
    inv_id = inv["investigation"]["id"]
    tid = client.get("/anomalies/top-50").json()["results"][0]["transaction_id"]
    client.post(f"/investigations/{inv_id}/findings",
                json={"kind": "alert", "title": f"flag {tid}",
                      "detail": f"review {tid}"})
    r = client.get(f"/investigations/{inv_id}/tree")
    assert r.status_code == 200
    body = r.json()
    assert body["investigation"]["id"] == inv_id
    assert len(body["flagged_transactions"]) == 1
    leg = body["flagged_transactions"][0]
    assert leg["transaction_id"] == tid
    assert "risk_score" in leg and "evidence" in leg


def test_fused_data_pagination_and_search(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    page1 = client.get("/data/fused?limit=2").json()
    assert page1["total"] == 5
    assert len(page1["rows"]) == 2
    page2 = client.get("/data/fused?limit=2&offset=2").json()
    assert len(page2["rows"]) == 2
    ids1 = {r["transaction_id"] for r in page1["rows"]}
    ids2 = {r["transaction_id"] for r in page2["rows"]}
    assert ids1.isdisjoint(ids2)
    row = page1["rows"][0]
    assert {"transaction_id", "account_no", "amount", "mode",
            "call_count", "ipdr_count", "ncrp"} <= set(row)
    searched = client.get("/data/fused?q=" + row["account_no"]).json()
    assert all(r["account_no"] == row["account_no"] for r in searched["rows"])
    assert searched["total"] >= 1


def test_fused_data_risk_annotation(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    plain = client.get("/data/fused?limit=5").json()["rows"][0]
    assert plain["risk_score"] is None
    scored = client.get("/data/fused?limit=5&risk_annotate=1").json()["rows"][0]
    assert isinstance(scored["risk_score"], float)
    assert scored["risk_band"]


def test_fused_csv_export(client, fixtures_dir):
    _ingest(client, fixtures_dir)
    r = client.get("/data/fused.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    lines = r.content.decode("utf-8-sig").strip().splitlines()
    header = lines[0].split(",")
    assert "transaction_id" in header and "risk_score" in header
    assert len(lines) == 6  # header + 5 fixture rows
    filtered = client.get("/data/fused.csv?q=UPI")
    assert len(filtered.content.decode("utf-8-sig").strip().splitlines()) <= 6


def test_fused_requires_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    with TestClient(api.app) as anon:  # no default Authorization header
        r = anon.get("/data/fused")
        assert r.status_code == 401
        r2 = anon.get("/data/fused.csv")
        assert r2.status_code == 401
