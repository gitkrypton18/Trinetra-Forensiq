"""Tests for the Phase C LLM layer: dual-provider client, continuous-
learning memory, general-answer mode, and engine fallback wiring.

All provider calls are mocked; no network access in tests.
"""

import pytest

from investigative_copilot.copilot_engine import InvestigativeCoPilotEngine
from investigative_copilot.db_builder import CopilotDBBuilder
from investigative_copilot.llm_client import LlmClient, _extract_json
from investigative_copilot.memory import MemoryStore, build_bundle_digest


# ------------------------------------------------------------------ JSON

def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_fences():
    text = "```json\n{\"intent\": \"trace\", \"sql\": null}\n```"
    assert _extract_json(text) == {"intent": "trace", "sql": None}


def test_extract_json_prose_around_object():
    text = ("Here you go:\n\n{\"a\": {\"b\": [1, 2]}}\n\nHope that helps.")
    assert _extract_json(text) == {"a": {"b": [1, 2]}}


def test_extract_json_handles_braces_in_strings():
    text = '{"note": "use {braces} carefully", "x": 2}'
    assert _extract_json(text) == {"note": "use {braces} carefully", "x": 2}


def test_extract_json_garbage_returns_none():
    assert _extract_json("no json here at all") is None
    assert _extract_json("") is None
    assert _extract_json(None) is None


# ------------------------------------------------------- provider fallback

class _FakeLlm(LlmClient):
    def __init__(self, gemini_ok=True, groq_ok=True):
        super().__init__()
        self.gemini_ok = gemini_ok
        self.groq_ok = groq_ok
        self.calls = []

    def _call_gemini(self, *a, **k):
        self.calls.append("gemini")
        if self.gemini_ok:
            return True, {"provider": "gemini", "v": 1}, ""
        return False, None, "boom"

    def _call_groq(self, *a, **k):
        self.calls.append("groq")
        if self.groq_ok:
            return True, {"provider": "groq", "v": 2}, ""
        return False, None, "also boom"


@pytest.fixture(autouse=True)
def _fake_keys(monkeypatch):
    import backend.config as cfg
    monkeypatch.setattr(cfg, "gemini_api_key", lambda: "g-key")
    monkeypatch.setattr(cfg, "groq_api_key", lambda: "gr-key")


def test_primary_groq_wins(monkeypatch):
    monkeypatch.setattr("investigative_copilot.llm_client.config.gemini_api_key",
                        lambda: "g-key")
    monkeypatch.setattr("investigative_copilot.llm_client.config.groq_api_key",
                        lambda: "gr-key")
    fake = _FakeLlm()
    ok, parsed, meta = fake.generate_json("s", "u")
    assert ok and parsed["provider"] == "groq"
    assert meta["provider"] == "groq"
    assert fake.calls == ["groq"]


def test_gemini_fallback_on_groq_failure():
    fake = _FakeLlm(groq_ok=False)
    ok, parsed, meta = fake.generate_json("s", "u")
    assert ok and parsed["provider"] == "gemini"
    assert fake.calls == ["groq", "gemini"]
    assert "boom" in meta["error"]


def test_both_fail_returns_false():
    fake = _FakeLlm(gemini_ok=False, groq_ok=False)
    ok, parsed, meta = fake.generate_json("s", "u")
    assert not ok and parsed is None
    assert "also boom" in meta["error"]


def test_no_keys_skips_both(monkeypatch):
    monkeypatch.setattr("investigative_copilot.llm_client.config.gemini_api_key",
                        lambda: "")
    monkeypatch.setattr("investigative_copilot.llm_client.config.groq_api_key",
                        lambda: "")
    fake = _FakeLlm()
    ok, parsed, meta = fake.generate_json("s", "u")
    assert not ok and fake.calls == []
    assert "no API key" in meta["error"]
    assert not fake.has_provider()


# ------------------------------------------------------------------ memory

def test_memory_roundtrip_and_cap(tmp_path):
    ms = MemoryStore(bundle={"bank": [{"mode": "UPI"}]}, path=tmp_path / "m.json")
    ms.remember_turn("q1", "s1")
    for i in range(10):
        ms.remember_turn(f"q{i}", f"s{i}")
    assert len(ms.recent_chat()) == 8
    assert ms.recent_chat()[-1] == {"user": "q9", "assistant": "s9"}


def test_memory_survives_restart(tmp_path):
    p = tmp_path / "m.json"
    bundle = {"bank": [{"mode": "UPI"}], "cdr": [], "ipdr": [],
              "complaints": [], "subscribers": []}
    ms1 = MemoryStore(bundle=bundle, path=p)
    ms1.remember_turn("find mules", "ACC1001 is a Layer-1 mule.")
    ms2 = MemoryStore(bundle=bundle, path=p)
    assert ms2.recent_chat() == [
        {"user": "find mules", "assistant": "ACC1001 is a Layer-1 mule."}]
    assert "CORPUS BRIEF" in ms2.memory_block()


def test_memory_fingerprint_isolates_bundles(tmp_path):
    p = tmp_path / "m.json"
    b1 = {"bank": [{"mode": "UPI"}], "cdr": [], "ipdr": [],
          "complaints": [], "subscribers": []}
    b2 = {"bank": [], "cdr": [], "ipdr": [], "complaints": [], "subscribers": []}
    MemoryStore(bundle=b1, path=p).remember_turn("q", "s")
    assert MemoryStore(bundle=b2, path=p).recent_chat() == []


def test_build_bundle_digest_counts():
    digest = build_bundle_digest({
        "bank": [{"mode": "UPI"}], "cdr": [{"roaming_circle": "WB"}],
        "ipdr": [], "complaints": [{"account_no": "A1"}], "subscribers": [],
    })
    assert "1 bank transactions" in digest
    assert "1 NCRP complaints" in digest
    assert "UPI" in digest


# ------------------------------------------------------------------ engine

def _bundle():
    return {
        "bank": [
            {"txn_id": "TXN1", "date": "2025-01-01", "time": "10:00:00",
             "ts": 1.0, "mode": "UPI", "txn_type": "D", "debit": 25000.0,
             "credit": None, "account_no": "ACC1001",
             "account_name": "Alice", "bank": "ICICI", "ifsc": "ICIC0001",
             "customer_id": "1001", "sender_phone": "+919160000001",
             "receiver_account": "ACC2002", "counterparty_name": "Bob",
             "counterparty_bank": "HDFC", "receiver_phone": "+919876543210"},
        ],
        "cdr": [], "ipdr": [], "complaints": [], "subscribers": [],
        "entities": {},
    }


@pytest.fixture
def llm_engine(tmp_path, monkeypatch):
    builder = CopilotDBBuilder()
    conn = builder.build_database_from_bundle(_bundle())
    monkeypatch.setattr(
        "investigative_copilot.memory.config.data_dir",
        lambda: tmp_path)
    return InvestigativeCoPilotEngine(conn=conn, bundle=_bundle())


def _stub_llm(monkeypatch, engine, result, meta=None):
    def fake_generate_json(system_prompt, user_content, **kw):
        return True, result, (meta or {"provider": "groq",
                                      "model": "llama-x", "latency_ms": 42})
    monkeypatch.setattr(engine.llm, "generate_json", fake_generate_json)


def test_engine_sql_mode(llm_engine, monkeypatch):
    _stub_llm(monkeypatch, llm_engine, {
        "intent": "trace mule",
        "sql_query": ("SELECT transaction_id, transaction_amount, "
                      "sender_account_number, receiver_account_number "
                      "FROM bank_transactions WHERE transaction_amount > 10000"),
        "graph_start_node": "ACC2002",
        "cot_reasoning": ["extract entities", "build query"],
        "executive_summary": "Lead: ACC2002 is a Layer-1 mule.",
        "general_answer": None,
    })
    res = llm_engine.analyze_query("trace money to ACC2002")
    assert res["mode"] == "sql"
    assert res["llm_provider"] == "groq"
    assert res["row_count"] == 1
    assert res["records"][0]["transaction_id"] == "TXN1"
    assert "risk_score" in res["records"][0]
    assert res["executive_summary"].startswith("Lead:")


def test_engine_general_answer_mode(llm_engine, monkeypatch):
    _stub_llm(monkeypatch, llm_engine, {
        "intent": "explain layering",
        "sql_query": None,
        "graph_start_node": None,
        "cot_reasoning": ["step1", "step2"],
        "executive_summary": "Layering summary for officers.",
        "general_answer": "Money layering moves funds through multiple tiers...",
    })
    res = llm_engine.analyze_query("what is money layering?")
    assert res["mode"] == "general"
    assert res["general_answer"].startswith("Money layering")
    assert res["records"] == []
    assert res["entity_resolution"]["resolved"] is False
    assert "narrative" in res["investigation_summary"]


def test_engine_llm_failure_falls_back_to_deterministic(llm_engine, monkeypatch):
    monkeypatch.setattr(
        llm_engine.llm, "generate_json",
        lambda *a, **k: (False, None, {"provider": "", "error": "no keys"}))
    res = llm_engine.analyze_query("tower call correlation")
    assert res["mode"] == "deterministic"
    assert res["llm_provider"] == ""


def test_engine_prompt_includes_memory(llm_engine, monkeypatch):
    captured = {}

    def fake_generate_json(system_prompt, user_content, **kw):
        captured["sys"] = system_prompt
        captured["user"] = user_content
        return True, {
            "intent": "x", "sql_query": None, "graph_start_node": None,
            "cot_reasoning": [], "executive_summary": "s",
            "general_answer": "a",
        }, {"provider": "groq", "model": "m", "latency_ms": 1}
    monkeypatch.setattr(llm_engine.llm, "generate_json", fake_generate_json)
    llm_engine.analyze_query("first query")
    assert "CORPUS BRIEF" in captured["user"]
    assert "1 bank transactions" in captured["user"]
    llm_engine.analyze_query("second query")
    assert "first query" in captured["user"]
    assert "CONVERSATION MEMORY" in captured["user"]


def test_engine_remembers_turns(llm_engine, monkeypatch):
    _stub_llm(monkeypatch, llm_engine, {
        "intent": "x", "sql_query": None, "graph_start_node": None,
        "cot_reasoning": [], "executive_summary": "Learned: ACC2002 mule.",
        "general_answer": "a",
    })
    llm_engine.analyze_query("who is the mule?")
    assert any(t["user"] == "who is the mule?"
               and t["assistant"].startswith("Learned:")
               for t in llm_engine.memory.recent_chat())
