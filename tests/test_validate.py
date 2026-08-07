"""Validation-suite tests: ground-truth readers, comparator, synthetic adapters."""

from __future__ import annotations

import csv
import os

import pytest

from backend.adapters.synthetic import build_synthetic_bundle
from backend.validate import read_police_gt, read_synthetic_gt, run
from backend.validate.comparator import (
    compare_anomalies, compare_correlation, compare_coverage,
    _bank_cdr_pairs, _cdr_ipdr_pairs, _norm_phone)


@pytest.fixture
def gt_dir(tmp_path):
    with open(tmp_path / "anomaly_ground_truth.csv", "w", newline="",
              encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, ["Anomaly_ID", "Customer_ID", "Transaction_ID",
                                "Scenario_Type", "Source_Scope", "Is_Suspicious"])
        w.writeheader()
        w.writerow({"Anomaly_ID": "ANOM1", "Customer_ID": "C1",
                    "Transaction_ID": "TXN1", "Scenario_Type": "ODD_HOUR",
                    "Source_Scope": "BANK_ONLY", "Is_Suspicious": "1"})
    with open(tmp_path / "bank_cdr_ground_truth.csv", "w", newline="",
              encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, ["Transaction_ID", "CDR_ID",
                                "Time_Difference_Seconds", "Is_Correlated"])
        w.writeheader()
        w.writerow({"Transaction_ID": "TXN1", "CDR_ID": "CDR1",
                    "Time_Difference_Seconds": "60", "Is_Correlated": "1"})
        w.writerow({"Transaction_ID": "TXN2", "CDR_ID": "CDR2",
                    "Time_Difference_Seconds": "10", "Is_Correlated": "0"})
    with open(tmp_path / "cdr_ipdr_ground_truth.csv", "w", newline="",
              encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, ["CDR_ID", "IPDR_ID",
                                "Time_Difference_Seconds", "Is_Correlated"])
        w.writeheader()
        w.writerow({"CDR_ID": "CDR1", "IPDR_ID": "IPDR1",
                    "Time_Difference_Seconds": "30", "Is_Correlated": "1"})
    return str(tmp_path)


@pytest.fixture
def mini_bundle():
    return {
        "bank": [
            {"txn_id": "TXN1", "account_no": "ACC1",
             "receiver_phone": "919876543210", "sender_phone": "",
             "ts": 1700000100},
            {"txn_id": "TXN2", "account_no": "ACC2",
             "receiver_phone": "910000000001", "sender_phone": "",
             "ts": 1700000200},
        ],
        "cdr": [
            {"cdr_id": "CDR1", "a_number": "919876543210",
             "b_number": "", "imsi": "404111111111", "imei": "IMEI1",
             "ts": 1700000060},
            {"cdr_id": "CDR2", "a_number": "919876543210",
             "b_number": "", "imsi": "404111111111", "imei": "IMEI1",
             "ts": 1700000500},
        ],
        "ipdr": [
            {"ipdr_id": "IPDR1", "msisdn": "919876543210",
             "imsi": "404111111111", "imei": "IMEI1", "start_ts": 1700000070},
        ],
        "complaints": [],
        "subscribers": [],
    }


def test_norm_phone():
    assert _norm_phone("+91-98765 43210") == "919876543210"
    assert _norm_phone("9876543210") == "919876543210"
    assert _norm_phone("") == ""


def test_synthetic_gt_reader(gt_dir):
    gt = read_synthetic_gt(gt_dir)
    assert gt["source"] == "synthetic"
    assert "ANOM1" in gt["anomalies"]
    assert gt["bank_cdr"]["TXN1"]["Is_Correlated"] == "1"


def test_police_gt_reader_requires_dir(tmp_path):
    with pytest.raises(Exception):
        read_police_gt(str(tmp_path / "missing"))


def test_coverage_perfect(mini_bundle, gt_dir):
    gt = read_synthetic_gt(gt_dir)
    cov = compare_coverage(mini_bundle, gt)
    assert cov["bank"]["recall"] == 1.0
    assert cov["cdr"]["recall"] == 1.0
    assert cov["ipdr"]["recall"] == 1.0


def test_bank_cdr_pairs_found(mini_bundle):
    pairs = _bank_cdr_pairs(mini_bundle, window=300)
    assert ("TXN1", "CDR1") in pairs
    assert ("TXN1", "CDR2") not in pairs  # outside window


def test_cdr_ipdr_pairs_found(mini_bundle):
    pairs = _cdr_ipdr_pairs(mini_bundle, window=300)
    assert ("CDR1", "IPDR1") in pairs


def test_correlation_report(mini_bundle, gt_dir):
    gt = read_synthetic_gt(gt_dir)
    rep = compare_correlation(mini_bundle, gt)
    assert rep["bank_cdr"]["gt_window"]["recall"] == 1.0
    assert rep["cdr_ipdr"]["gt_window"]["recall"] == 1.0


def test_anomaly_detection_metrics(gt_dir, tmp_path):
    """The behavioural scorer flags TXN3: a customer-relative amount spike
    (30x the account's prior median) with enough prior history."""
    bank = []
    for i in range(6):
        bank.append({
            "txn_id": f"TXN{i}", "account_no": "ACC1",
            "receiver_phone": f"9198765432{i % 10:02d}",
            "sender_phone": "",
            "ts": 1700000100 + i * 60,
            "credit": 5000.0,
            "debit": None, "txn_type": "C", "mode": "UPI",
            "narration": "",
        })
    bank[3] = {**bank[3], "credit": 150000.0}
    bundle = {"bank": bank, "cdr": [{"cdr_id": "CDR1",
                                     "a_number": "919876543210",
                                     "b_number": "", "imsi": "", "imei": "",
                                     "ts": 1700000100}],
              "ipdr": [], "complaints": [], "subscribers": []}
    gt_file = tmp_path / "anomaly_ground_truth.csv"
    with open(gt_file, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, ["Anomaly_ID", "Customer_ID", "Transaction_ID",
                                "Scenario_Type", "Source_Scope",
                                "Is_Suspicious"])
        w.writeheader()
        w.writerow({"Anomaly_ID": "ANOM1", "Customer_ID": "C1",
                    "Transaction_ID": "TXN3",
                    "Scenario_Type": "CUSTOMER_RELATIVE_AMOUNT_SPIKE",
                    "Source_Scope": "BANK_ONLY", "Is_Suspicious": "1"})
    gt = read_synthetic_gt(str(tmp_path))
    rep = compare_anomalies(bundle, gt, (25,))
    overall = rep["overall"]["25"]
    assert overall["tp"] == 1
    assert overall["fn"] == 0


def test_full_validation_run(mini_bundle, gt_dir):
    rep = run(mini_bundle, gt_dir, (25,))
    assert rep["source"] == "synthetic"
    assert "coverage" in rep and "correlation" in rep and "anomalies" in rep


def test_synthetic_bundle_shapes():
    if not os.path.isdir("data/anomalous"):
        pytest.skip("synthetic dataset not present")
    b = build_synthetic_bundle("data")
    assert len(b["bank"]) > 0 and len(b["cdr"]) > 0 and len(b["ipdr"]) > 0
    assert all(r["receiver_phone"].startswith("91") or r["receiver_phone"] == ""
               for r in b["bank"][:50])
    assert all(r["cdr_id"] for r in b["cdr"][:50])
