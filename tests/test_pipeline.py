"""Pipeline-level tests: classification, parsing, normalisation, ingestion."""

from __future__ import annotations

from backend import detect
from backend.pipeline import ingest_folder, parse_file


def test_detect_bank_csv(fixtures_dir):
    cls = detect.classify(str(fixtures_dir / "bank_statement.csv"))
    assert cls["dataset"] == "BANK"
    assert cls["format"] == "bank_csv"


def test_detect_cdr_vvm(fixtures_dir):
    cls = detect.classify(str(fixtures_dir / "cdr_jio_vvm.csv"))
    assert cls["dataset"] == "CDR"
    assert cls["format"] == "jio_vvm"


def test_detect_ipdr_xlsx(fixtures_dir):
    cls = detect.classify_xlsx(str(fixtures_dir / "ipdr_session.xlsx"))
    assert cls["dataset"] == "IPDR"


def test_bank_csv_parses_amounts(fixtures_dir):
    _, res = parse_file(str(fixtures_dir / "bank_statement.csv"))
    recs = res["records"]
    assert len(recs) == 5
    assert {r["txn_type"] for r in recs} == {"C", "D"}
    assert any(r["credit"] == 5000.0 for r in recs)
    assert all(r["date"] for r in recs)


def test_cdr_vvm_parses_and_orients(fixtures_dir):
    _, res = parse_file(str(fixtures_dir / "cdr_jio_vvm.csv"))
    recs = res["records"]
    assert len(recs) == 3
    by_b = {r["b_number"]: r for r in recs}
    assert "919876543210" in by_b
    sms = [r for r in recs if r["call_type"] == "SMS"]
    assert len(sms) == 1
    assert recs[0]["operator"] == "Jio"


def test_ipdr_xlsx_parses(fixtures_dir):
    _, res = parse_file(str(fixtures_dir / "ipdr_session.xlsx"))
    recs = res["records"]
    assert len(recs) == 2
    assert recs[0]["source_ip"] == "10.20.30.40"
    assert recs[0]["msisdn"] == "916000000001"


def test_complaints_ledger(fixtures_dir):
    from backend.pipeline import parse_ncrp_complaints
    comps = parse_ncrp_complaints(str(fixtures_dir / "All Account complain.csv"))
    assert len(comps) == 2
    assert comps[0]["account_no"] == "924010036411120"
    assert comps[0]["police_station"] == "Mahatma Gandhi PS"


def test_empty_csv_is_harmless(fixtures_dir):
    cls = detect.classify(str(fixtures_dir / "empty.csv"))
    _, res = parse_file(str(fixtures_dir / "empty.csv"))
    assert res["records"] == []
    assert cls["dataset"] == "BANK"


def test_ingest_folder_bundle(fixtures_dir):
    b = ingest_folder(str(fixtures_dir))
    assert len(b["bank"]) == 5
    assert len(b["cdr"]) == 3
    assert len(b["ipdr"]) == 2
    assert len(b["complaints"]) == 2
    assert len(b["files"]["ok"]) == 5  # bank + cdr + complaints + ipdr + empty.csv
    assert "empty.csv" in b["files"]["ok"]
    assert len(b["entities"]["phones"]) >= 2
    assert "924010036411120" in b["entities"]["accounts"]
