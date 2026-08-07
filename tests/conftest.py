"""Shared pytest fixtures: a mini police-dataset folder on disk.

Fixtures mirror the real file shapes (bank CSV, Jio VVM CDR, NCRP complaint
ledger, generic IPDR xlsx) small enough to run in milliseconds.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("APP_DATA_DIR",
                      tempfile.mkdtemp(prefix="backend_test_data_"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import api, auth, store  # noqa: E402

BANK_CSV = """date,narration,debit,credit,balance,mode,account_no
01/04/2025,"UPI/ABC@okaxis refund",,5000.00,15000.00,UPI,924010036411120
02/04/2025,"NEFT/RAHUL KUMAR transfer",2000.00,,13000.00,NEFT,924010036411120
03/04/2025,"ATM WITHDRAWAL BR SURAT",1000.00,,12000.00,ATM,924010036411120
04/04/2025,"UPI/XYZ@okhdfc payment",3000.00,,9000.00,UPI,924010036411120
05/04/2025,"UPI/ABC@okaxis transfer",4000.00,,5000.00,UPI,924010036411120
"""

CDR_JIO_VVM_CSV = """Input Value (MSISDN),916000000001
Date Range,2025-04-01 to 2025-04-05
Total Records,3
Subscriber Name,JOHN DOE
Circle,Gujarat

Calling Party Telephone Number,Called Party Telephone Number,Call Date,Call Time,Call Type,Call Duration,First Cell ID,Last Cell ID,IMEI,IMSI,Roaming Circle Name,LRN Called No
916000000001,919876543210,2025-04-01,10:15:00,MO Call Out,120,GJ01A01,GJ01B01,351234567890123,405000123456789,Gujarat,
919876543210,916000000001,2025-04-01,10:30:00,MT Call In,60,GJ01A01,GJ01B01,351234567890123,405000123456789,Gujarat,
916000000001,919999999999,2025-04-02,11:00:00,SMS MO,0,GJ01A01,GJ01B01,351234567890123,405000123456789,Gujarat,
"""

COMPLAINTS_CSV = """Acknowledgement no,Account No,IFSC,State,District,Police Station,Name of Complainant,Designation,Mobile,Email
ACK001,924010036411120,UTIB0000001,Gujarat,Surat,Mahatma Gandhi PS,Officer XYZ,PI,9876501234,officer@police.guj.in
ACK002,100200300400,SBIN0000002,Gujarat,Surat,Chowk Bazaar PS,Officer ABC,PSI,9876505678,officer2@police.guj.in
"""


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="backend_fixtures_"))
    _write(tmp / "bank_statement.csv", BANK_CSV)
    _write(tmp / "cdr_jio_vvm.csv", CDR_JIO_VVM_CSV)
    _write(tmp / "All Account complain.csv", COMPLAINTS_CSV)

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["No.", "IP Address", "Date", "Time(IST)", "username", "mobile"])
    ws.append([1, "10.20.30.40", "2025-04-01", "10:00:00", "user1", "916000000001"])
    ws.append([2, "10.20.30.41", "2025-04-02", "11:00:00", "user1", "916000000001"])
    wb.save(tmp / "ipdr_session.xlsx")

    _write(tmp / "empty.csv", "")
    return tmp


@pytest.fixture(scope="session")
def synthetic_fixtures_dir() -> Path:
    """Problem-statement synthetic exports (clean/anomalous CSV shapes)."""
    tmp = Path(tempfile.mkdtemp(prefix="backend_synthetic_fixtures_"))
    _write(
        tmp / "bank_final.csv",
        "Transaction_ID,Date,Timestamp,Txn_Ref_Number,Transaction_Mode,"
        "Currency,Transaction_Amount,Sender_Customer_ID,Sender_Customer_Name,"
        "Sender_Bank_Name,Sender_Account_Number,Sender_Account_Type,Sender_IFSC,"
        "Sender_Phone_Number,Receiver_Customer_ID,Receiver_Customer_Name,"
        "Receiver_Bank_Name,Receiver_Account_Number,Receiver_Account_Type,"
        "Receiver_IFSC,Receiver_Phone_Number\n"
        "TXN1,2025-01-01,10:00:00,REF1,UPI,INR,25000.0,1001,Alice,ICICI,"
        "ACC001,Savings,ICIC0001,+919160000001,1002,Bob,HDFC,ACC002,Savings,"
        "HDFC0001,+919876543210\n"
        "TXN2,2025-01-02,11:30:00,REF2,IMPS,INR,10000.0,1001,Alice,ICICI,"
        "ACC001,Savings,ICIC0001,+919160000001,1003,Carol,BOB,ACC003,Savings,"
        "BOB0001,+919999999999\n")
    _write(
        tmp / "cdr_final.csv",
        "CDR_ID,Call_Date,Call_Start_Time,A_Party_Number,B_Party_Number,"
        "Call_Type,Call_Duration_Seconds,IMSI,IMEI,First_BTS_Location,"
        "First_Cell_Global_ID,Roaming_Network_Circle\n"
        "CDR1,2025-01-01,10:05:00,+919160000001,+919876543210,VOICE,120,"
        "404000000000001,351111111111111,GJ_BTS_01,404-45-1-1,Gujarat\n"
        "CDR2,2025-01-02,11:35:00,+919876543210,+919160000001,VOICE,60,"
        "404000000000002,351111111111111,GJ_BTS_01,404-45-1-1,Gujarat\n")
    _write(
        tmp / "ipdr_final.csv",
        "IPDR_ID,Session_Date,Session_Start_Time,Subscriber_IMSI,"
        "Subscriber_MSISDN,Device_IMEI,Source_IP_Address,Destination_IP_Address,"
        "Destination_Port,Cell_Global_ID,Session_Duration_Seconds\n"
        "IP1,2025-01-01,10:10:00,404000000000001,+919160000001,351111111111111,"
        "10.1.1.5,198.51.100.5,443,404-45-1-1,300\n")
    return tmp


@pytest.fixture(scope="session", autouse=True)
def _offline_llm_transport():
    """Keeps the whole suite offline and deterministic.

    Patches only the HTTP transport of the copilot LlmClient: provider
    selection logic still runs, but every live call returns "offline", so
    engines fall back to the deterministic pipeline. Tests that exercise the
    provider chain override _call_gemini/_call_groq and are unaffected.
    """
    from investigative_copilot import llm_client

    original = llm_client.LlmClient._post_json

    def offline(self, *args, **kwargs):
        return False, None, "offline test suite"

    llm_client.LlmClient._post_json = offline
    yield
    llm_client.LlmClient._post_json = original


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient with a fresh store + API state for every test.

    A user is registered and logged in on the fly, so every test starts
    authenticated (Bearer header set as the client default).
    """
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    api._state.clear()
    auth._CSRF.clear()
    store.clear_bundle()
    with TestClient(api.app) as c:
        c.post("/auth/register", json={"username": "tester",
                                       "password": "testpass123"})
        tok = c.post("/auth/login", json={"username": "tester",
                                          "password": "testpass123"}).json()
        c.headers.update({"Authorization": f"Bearer {tok['access_token']}"})
        yield c
    auth._CSRF.clear()
    api._state.clear()
