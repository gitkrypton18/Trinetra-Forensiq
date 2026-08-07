"""FastAPI backend.

Production entrypoint:

    uvicorn backend.api:app --host 0.0.0.0 --port 8000

or inside the container (see Dockerfile):

    python -m uvicorn backend.api:app --host $APP_API_HOST --port $APP_API_PORT
"""

from __future__ import annotations

import csv
import io
import os
import tempfile
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import (Depends, FastAPI, File, HTTPException, Query,
                     UploadFile)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from . import auth, config, evidence, ml, risk, store
from .behavioural import score_transactions
from .fusion import (account_analysis, build_timeline, circular_flows,
                     correlate_phones, fraud_heat, fused_table,
                     rapid_in_out, rapid_payouts, search_bundle)
from .graphs import (account_phone_graph, central_phones, ego_network,
                     money_graph, phone_call_graph)
from .pipeline import ingest_folder
from .report import (generate_entity_str_report,
                     generate_str_report,
                     generate_transaction_str_report)
from investigative_copilot import router as copilot_router

_log = config.log


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Restore the last ingested bundle so data survives restarts."""
    bundle = store.load_bundle()
    if bundle:
        with _lock:
            _state["bundle"] = bundle
        copilot_router.reset_engine()
        _log.info("restored persisted bundle (bank=%d cdr=%d ipdr=%d)",
                  len(bundle.get("bank", [])), len(bundle.get("cdr", [])),
                  len(bundle.get("ipdr", [])))
        _hybrid_warm(bundle)
    yield


app = FastAPI(
    title="Financial & Telecom Analysis API",
    description="Bank-statement / CDR / IPDR ingestion, fusion and risk scoring "
                "for cyber-crime investigations.",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(copilot_router.router)

_state: dict = {}
_lock = threading.Lock()


def _persist() -> None:
    try:
        store.save_bundle(_state["bundle"])
    except Exception:
        _log.exception("failed to persist bundle")


class IngestRequest(BaseModel):
    folder: str


class IngestResponse(BaseModel):
    files_ok: int
    files_skipped: int
    errors: list[str]
    bank: int
    cdr: int
    ipdr: int
    complaints: int


@app.get("/")
def root():
    return {
        "name": "Financial & Telecom Analysis API",
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
        "status": "/ingest/status",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "loaded": bool(_state),
        "last_ingested": store.last_ingested(),
    }


# ---------------------------------------------------------------- auth


@app.post("/auth/register")
def auth_register(body: auth.RegisterBody):
    """Create an account (first registered user becomes admin)."""
    user = auth.register(body)
    return {"detail": "user created", "user": user}


@app.post("/auth/login")
def auth_login(body: auth.LoginBody):
    """Exchange credentials for a Bearer token."""
    return auth.login(body)


@app.get("/auth/me")
def auth_me(user: dict = Depends(auth.require_user)):
    return {"user": user}


@app.get("/ingest/status")
def ingest_status(user: dict = Depends(auth.require_user)):
    b = _state.get("bundle")
    return {
        "loaded": bool(b),
        "last_ingested": store.last_ingested(),
        "bank": len(b["bank"]) if b else 0,
        "cdr": len(b["cdr"]) if b else 0,
        "ipdr": len(b["ipdr"]) if b else 0,
        "subscribers": len(b["subscribers"]) if b else 0,
        "complaints": len(b["complaints"]) if b else 0,
        "files_ok": len(b["files"]["ok"]) if b else 0,
        "files_skipped": len(b["files"]["skipped"]) if b else 0,
        "errors": b["files"]["errors"] if b else [],
    }


@app.delete("/ingest")
def ingest_clear(user: dict = Depends(auth.require_admin)):
    """Drop the loaded bundle (and its persisted copy). Admin only."""
    with _lock:
        _state.pop("bundle", None)
    copilot_router.reset_engine()
    risk.clear_cache()
    risk.clear_hybrid_cache()
    store.clear_bundle()
    return {"cleared": True}


@app.post("/ingest")
def ingest(req: IngestRequest, user: dict = Depends(auth.require_user)) -> IngestResponse:
    if not os.path.isdir(req.folder):
        raise HTTPException(400, f"folder not found: {req.folder}")
    _log.info("ingesting folder %s", req.folder)
    with _lock:
        _state["bundle"] = ingest_folder(req.folder)
        _persist()
    copilot_router.reset_engine()
    risk.clear_cache()
    risk.clear_hybrid_cache()
    _hybrid_warm(_state["bundle"])
    b = _state["bundle"]
    _log.info("ingest done: %d files ok, %d skipped, %d errors | bank=%d cdr=%d ipdr=%d",
              len(b["files"]["ok"]), len(b["files"]["skipped"]),
              len(b["files"]["errors"]), len(b["bank"]), len(b["cdr"]),
              len(b["ipdr"]))
    return IngestResponse(
        files_ok=len(b["files"]["ok"]),
        files_skipped=len(b["files"]["skipped"]),
        errors=b["files"]["errors"],
        bank=len(b["bank"]), cdr=len(b["cdr"]),
        ipdr=len(b["ipdr"]), complaints=len(b["complaints"]),
    )


def _require_bundle() -> dict:
    if "bundle" not in _state:
        raise HTTPException(409, "no data loaded; POST /ingest first")
    return _state["bundle"]


@app.get("/summary")
def summary(user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    heat = fraud_heat(b)
    return {
        "files": b["files"],
        "bank_records": len(b["bank"]),
        "cdr_records": len(b["cdr"]),
        "ipdr_records": len(b["ipdr"]),
        "complaints": len(b["complaints"]),
        "entities": {
            "phones": len(b["entities"]["phones"]),
            "accounts": len(b["entities"]["accounts"]),
            "upi_ids": len(b["entities"]["upi_ids"]),
            "imeis": len(b["entities"]["imeis"]),
            "imsis": len(b["entities"]["imsis"]),
            "ips": len(b["entities"]["ips"]),
        },
        "top_risk_accounts": [
            {"account_no": a["account_no"], "score": a["score"], "flags": a["flags"]}
            for a in heat["accounts"][:10]],
        "top_risk_phones": [
            {"phone": p["phone"], "score": p["score"], "flags": p["flags"]}
            for p in heat["phones"][:10]],
        "last_ingested": store.last_ingested(),
    }


@app.get("/accounts")
def accounts(min_score: float = 0, limit: int = Query(50, le=500),
             user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    heat = fraud_heat(b)
    out = [a for a in heat["accounts"] if a["score"] >= min_score][:limit]
    return {"accounts": out}


@app.get("/phones")
def phones(min_score: float = 0, limit: int = Query(50, le=500),
           user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    heat = fraud_heat(b)
    return {"phones": [p for p in heat["phones"] if p["score"] >= min_score][:limit]}


@app.get("/phone/{phone}/egonet")
def phone_egonet(phone: str, depth: int = Query(1, ge=1, le=3), min_weight: int = 0,
                 mode: str = Query("evidence", pattern="^(evidence|full)$"),
                 user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    if mode == "evidence":
        return evidence.evidence_egonet(b, phone, depth=depth)
    g = phone_call_graph(b["cdr"])
    return ego_network(g, phone, depth=depth, min_weight=min_weight)


@app.get("/entity/{kind}/{value}")
def entity_evidence(kind: str, value: str,
                    user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    if kind not in ("account", "phone", "upi", "imei", "imsi", "ip", "name"):
        raise HTTPException(400, f"unsupported entity kind: {kind}")
    info = evidence.entity_intelligence(b, kind, value)
    if info is None:
        raise HTTPException(404, f"no evidence found for {kind} {value}")
    return info


@app.get("/relationship/{a}/{b}")
def relationship_evidence(a: str, b: str,
                          user: dict = Depends(auth.require_user)):
    return evidence.relationship_intelligence(_require_bundle(), a, b)


@app.get("/graph/device")
def graph_device(phone: str, user: dict = Depends(auth.require_user)):
    return evidence.device_graph(_require_bundle(), phone)


@app.get("/graph/ip")
def graph_ip(phone: str, user: dict = Depends(auth.require_user)):
    return evidence.ip_graph(_require_bundle(), phone)


@app.get("/report/entity/{kind}/{value}")
def entity_report(kind: str, value: str,
                  user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    path = os.path.join(tempfile.gettempdir(),
                        f"str_entity_{kind}_{abs(hash(value)) % 100000}.pdf")
    try:
        generate_entity_str_report(b, kind, value, path)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return FileResponse(path, media_type="application/pdf",
                        filename=f"STR_{kind}_{value[:32]}.pdf")


@app.get("/timeline")
def timeline(kind: str | None = None, since: int | None = None,
             until: int | None = None, limit: int = Query(2000, le=20000),
             user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    events = build_timeline(b)
    if kind:
        events = [e for e in events if e["kind"] == kind]
    if since is not None:
        events = [e for e in events if e["ts"] >= since]
    if until is not None:
        events = [e for e in events if e["ts"] <= until]
    return {"count": len(events), "events": events[:limit]}


@app.get("/coincidence")
def coincidence(window_sec: int = Query(3600, ge=60, le=86400),
                limit: int = Query(100, le=1000),
                user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    res = correlate_phones(b, window_sec=window_sec)
    return {"window_sec": window_sec, "hits": res["hits"][:limit],
            "total": len(res["hits"])}


@app.get("/payouts")
def payouts(threshold: int = Query(5, ge=1, le=100), window_min: int = Query(60, ge=1),
            user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    return {"rapid": rapid_payouts(b, threshold, window_min),
            "round": fraud_heat(b)["round_payouts"]}


@app.get("/account/{account_no}")
def account_detail(account_no: str, user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    accts = account_analysis(b["bank"], b["complaints"])
    if account_no not in accts:
        raise HTTPException(404, "account not found")
    txns = [r for r in b["bank"] if r.get("account_no") == account_no]
    return {"profile": accts[account_no],
            "txns": sorted(txns, key=lambda r: r.get("ts") or 0,
                           reverse=True)[:200]}


_STR_PATH = os.path.join(tempfile.gettempdir(), "str_report.pdf")


def _str_is_fresh() -> bool:
    if not os.path.exists(_STR_PATH):
        return False
    age_h = (datetime.now(timezone.utc).timestamp()
             - os.path.getmtime(_STR_PATH)) / 3600
    return age_h <= config.str_file_ttl_hours()


@app.get("/report")
def report(user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    if not _str_is_fresh():
        generate_str_report(b, _STR_PATH)
    return FileResponse(_STR_PATH, media_type="application/pdf",
                        filename="STR_Report.pdf")


@app.get("/entities")
def entities(user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    return b["entities"]


# ---------------------------------------------------------------- investigations
# Case files: investigators open an investigation, attach findings (which the
# analysis API can auto-suggest), and export the STR report for the FIR.


class InvestigationBody(BaseModel):
    title: str = ""
    notes: str = ""


class FindingBody(BaseModel):
    kind: str = "note"
    title: str = ""
    detail: str = ""
    severity: str = "medium"


@app.get("/investigations")
def investigations(user: dict = Depends(auth.require_user)):
    return {"investigations": store.list_investigations()}


@app.post("/investigations")
def investigation_create(body: InvestigationBody,
                         user: dict = Depends(auth.require_user)):
    if not body.title.strip():
        raise HTTPException(400, "title is required")
    inv = store.create_investigation(body.title.strip(), body.notes)
    return {"investigation": inv}


@app.get("/investigations/{investigation_id}")
def investigation_detail(investigation_id: int,
                         user: dict = Depends(auth.require_user)):
    inv = store.get_investigation(investigation_id)
    if inv is None:
        raise HTTPException(404, "investigation not found")
    return {"investigation": inv}


@app.patch("/investigations/{investigation_id}")
def investigation_update(investigation_id: int, body: InvestigationBody,
                         user: dict = Depends(auth.require_user)):
    inv = store.update_investigation(
        investigation_id,
        title=body.title or None, notes=body.notes or None)
    if inv is None:
        raise HTTPException(404, "investigation not found")
    return {"investigation": inv}


@app.delete("/investigations/{investigation_id}")
def investigation_delete(investigation_id: int,
                         user: dict = Depends(auth.require_admin)):
    store.delete_investigation(investigation_id)
    return {"deleted": investigation_id}


@app.post("/investigations/{investigation_id}/findings")
def finding_create(investigation_id: int, body: FindingBody,
                   user: dict = Depends(auth.require_user)):
    if store.get_investigation(investigation_id) is None:
        raise HTTPException(404, "investigation not found")
    if not body.title.strip():
        raise HTTPException(400, "title is required")
    f = store.add_finding(investigation_id, body.kind, body.title.strip(),
                          body.detail, body.severity)
    return {"finding": f}


# ---------------------------------------------------------------- hybrid engine
# Hybrid Multi-Stage Fraud Detection Engine (ERH26_PS_03): rules + ML
# ensemble + behavioural profiling + temporal windows + telecom/internet
# correlation + money-flow N-hop + entity risk + named scenario detection,
# fused through configurable weights with full explainability.
# The engine runs once per bundle and caches; ingest/restore trigger a
# background warm-up so the first UI request is fast.


def _hybrid_warm(bundle: dict) -> None:
    def _run() -> None:
        try:
            import backend.risk.hybrid as hybrid
            hybrid.hybrid_analyze(bundle)
            _log.info("hybrid engine warmed (%d txns)", len(bundle.get("bank", [])))
        except Exception:
            _log.exception("hybrid engine warm-up failed")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return


def _enrich_txn_row(row: dict, bank_by_id: dict) -> dict:
    """Attach customer name + phone to a hybrid transaction row."""
    rec = bank_by_id.get(row.get("transaction_id") or "", {})
    row = dict(row)
    row["customer_name"] = rec.get("account_name") or rec.get("customer_name") or ""
    row["customer_phone"] = rec.get("sender_phone") or rec.get("customer_phone") or ""
    return row


@app.get("/hybrid/transactions")
def hybrid_transactions(min_score: float = Query(0, ge=0, le=100),
                        limit: int = Query(50, le=1000),
                        band: str = Query("", pattern="^(SAFE|LOW|MEDIUM|HIGH|CRITICAL)?$"),
                        user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    scored = risk.hybrid_transaction_risk(b)
    bank_by_id = {r.get("txn_id"): r for r in b.get("bank", [])}
    results = []
    for s in scored:
        if s["risk_score"] < min_score:
            continue
        if band and s["risk_band"] != band:
            continue
        results.append(_enrich_txn_row({
            "transaction_id": s.get("transaction_id"),
            "account_no": s.get("account_no"),
            "amount": s.get("amount"),
            "mode": s.get("mode"),
            "customer_id": s.get("sender_customer_id"),
            "risk_score": s["risk_score"],
            "risk_band": s["risk_band"],
            "rules_fired": s.get("rules_fired", []),
            "breakdown": s.get("breakdown", []),
            "evidence": s.get("evidence", []),
            "hybrid_components": s.get("hybrid_components", {}),
            "models_fired": s.get("models_fired", []),
            "scenarios": s.get("scenarios", []),
            "confidence": s.get("confidence"),
        }, bank_by_id))
        if len(results) >= limit:
            break
    return {"results": results, "total": len(results)}


@app.get("/hybrid/accounts")
def hybrid_accounts(min_score: float = Query(0, ge=0, le=100),
                    limit: int = Query(50, le=500),
                    user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    accounts = [a for a in risk.hybrid_account_risk(b)
                if a["risk_score"] >= min_score][:limit]
    return {"accounts": accounts, "total": len(accounts)}


@app.get("/hybrid/entities")
def hybrid_entities(min_score: float = Query(0, ge=0, le=100),
                    limit: int = Query(50, le=500),
                    user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    entities = [e for e in risk.hybrid_entity_risk(b)
                if e["risk_score"] >= min_score][:limit]
    return {"entities": entities, "total": len(entities)}


@app.get("/hybrid/scenarios")
def hybrid_scenarios(limit: int = Query(20, le=100),
                     user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    res = risk.hybrid_analyze(b)
    scen = res["scenarios"]
    return {"stats": scen["stats"],
            "moneyflow": scen["moneyflow"]["stats"],
            "entity": {k: v for k, v in res["entity_risk"]["stats"].items()},
            "top": scen["stats"]["top_scenarios"][:limit]}


@app.get("/hybrid/stats")
def hybrid_stats(user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    res = risk.hybrid_analyze(b)
    return {"stats": res["stats"],
            "scenarios": res["scenarios"]["stats"],
            "weights": risk.hybrid_weights()}


@app.get("/hybrid/explain/transaction/{transaction_id}")
def hybrid_explain_transaction(transaction_id: str,
                               user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    out = risk.explanations_for_txn(b, transaction_id)
    if not out:
        raise HTTPException(404, "transaction not found")
    return {"explanation": out}


@app.get("/hybrid/explain/account/{account_no}")
def hybrid_explain_account(account_no: str,
                           user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    out = risk.explanations_for_account(b, account_no)
    if not out:
        raise HTTPException(404, "account not found")
    return {"explanation": out}


@app.get("/hybrid/explain/entity/{kind}/{entity}")
def hybrid_explain_entity(kind: str, entity: str,
                          user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    out = risk.explanations_for_entity(b, kind, entity)
    if not out:
        raise HTTPException(404, "entity not found")
    return {"explanation": out}


@app.get("/hybrid/weights")
def hybrid_weights(user: dict = Depends(auth.require_user)):
    return {"weights": risk.hybrid_weights()}


# ---------------------------------------------------------------- risk engine
# Phase-1 hybrid scoring: rule/ML/graph composite per account and the
# max() fusion per transaction, exposed for the investigation UI.


@app.get("/risk/accounts")
def risk_accounts(min_score: float = Query(0, ge=0, le=100),
                  limit: int = Query(50, le=500),
                  user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    res = risk.account_risk(b)
    accounts = [a for a in res["accounts"] if a["risk_score"] >= min_score][:limit]
    return {"accounts": accounts, "total": len(accounts),
            "detectors": res["detectors"], "graph": res["graph"],
            "ensemble_fitted": res["ensemble_fitted"]}


@app.get("/risk/transactions")
def risk_transactions(min_score: float = Query(0, ge=0, le=100),
                      limit: int = Query(50, le=1000),
                      band: str = Query("", pattern="^(SAFE|LOW|MEDIUM|HIGH|CRITICAL)?$"),
                      user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    scored = risk.transaction_risk(b)
    results = []
    for s in scored:
        if s["risk_score"] < min_score:
            continue
        if band and s["risk_band"] != band:
            continue
        results.append({
            "transaction_id": s["transaction_id"],
            "account_no": s.get("account_no"),
            "amount": s.get("amount"),
            "mode": s.get("mode"),
            "risk_score": s["risk_score"],
            "risk_band": s["risk_band"],
            "rules_fired": s["rules_fired"],
            "breakdown": s["breakdown"],
            "evidence": s["evidence"],
            "risk_components": s["risk_components"],
        })
        if len(results) >= limit:
            break
    return {"results": results, "total": len(results)}


@app.get("/anomalies/top-50")
def anomalies_top(limit: int = Query(50, le=500),
                  user: dict = Depends(auth.require_user)):
    """The 50 highest-risk transactions — the analyst alert feed."""
    return risk_transactions(min_score=0, limit=limit, band="", user=user)


@app.get("/transactions/{transaction_id}")
def transaction_detail(transaction_id: str,
                       user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    scored = risk.transaction_risk(b)
    s = next((x for x in scored if x["transaction_id"] == transaction_id),
             None)
    if s is None:
        raise HTTPException(404, "transaction not found")
    return {"transaction": s}


@app.get("/loading/status")
def loading_status(user: dict = Depends(auth.require_user)):
    b = _state.get("bundle")
    if not b:
        return {"loaded": False, "detail": "no bundle ingested yet"}
    return {
        "loaded": True,
        "bank": len(b.get("bank", [])),
        "cdr": len(b.get("cdr", [])),
        "ipdr": len(b.get("ipdr", [])),
        "complaints": len(b.get("complaints", [])),
        "entities": len(b.get("entities", [])),
        "last_ingested": store.last_ingested(),
        "cache_warm": False,
    }


@app.get("/report/transaction/{transaction_id}")
def transaction_report(transaction_id: str,
                       user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    path = os.path.join(tempfile.gettempdir(),
                        f"str_transaction_{transaction_id}.pdf")
    try:
        generate_transaction_str_report(b, transaction_id, path)
    except ValueError:
        raise HTTPException(404, "transaction not found")
    return FileResponse(path, media_type="application/pdf",
                        filename=f"STR_{transaction_id}.pdf")


@app.get("/investigations/{investigation_id}/tree")
def investigation_tree(investigation_id: int,
                       user: dict = Depends(auth.require_user)):
    """Case tree: the investigation, its findings, the flagged transactions
    mentioned in them, and the money/evidence legs for each."""
    inv = store.get_investigation(investigation_id)
    if inv is None:
        raise HTTPException(404, "investigation not found")
    b = _require_bundle()
    scored = {s["transaction_id"]: s
              for s in risk.transaction_risk(b)}
    findings = inv.get("findings", [])
    txn_ids = []
    for f in findings:
        blob = " ".join([str(f.get("title") or ""), str(f.get("detail") or "")])
        for tok in blob.split():
            if tok in scored:
                txn_ids.append(tok)
    legs = []
    for tid in sorted(set(txn_ids)):
        s = scored.get(tid)
        if s is None:
            continue
        legs.append({
            "transaction_id": tid,
            "risk_score": s["risk_score"],
            "risk_band": s["risk_band"],
            "rules_fired": s["rules_fired"],
            "evidence": s["evidence"][:10],
            "receiver_account": s.get("receiver_account"),
        })
    return {"investigation": {k: v for k, v in inv.items() if k != "findings"},
            "findings": findings,
            "flagged_transactions": legs}


# ---------------------------------------------------------------- analytics
# Problem-statement coverage: money-flow network (IV-a), circular flows and
# layering (III-a), ML anomaly layer (III-a), cross-entity search (IV-b).


@app.get("/graph/money")
def graph_money(min_amount: float = 0, limit: int = Query(300, le=1000),
                user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    g = money_graph(b["bank"])
    nodes, edges = [], []
    for n in g.nodes:
        nodes.append({"id": n, "kind": "account"
                      if g.nodes[n].get("kind") == "account" else "counterparty"})
    for u, v, d in g.edges(data=True):
        if d.get("amount", 0) < min_amount:
            continue
        edges.append({"source": u, "target": v, "weight": d.get("weight", 0),
                      "amount": round(d.get("amount", 0), 2)})
        if len(edges) >= limit:
            break
    return {"nodes": nodes, "edges": edges,
            "stats": {"nodes": len(nodes), "edges": g.number_of_edges()}}


@app.get("/graph/account-phone")
def graph_account_phone(limit: int = Query(200, le=500),
                        user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    g = account_phone_graph(b["bank"], b["ipdr"])
    nodes = [{"id": n, "kind": g.nodes[n].get("kind", "")} for n in list(g.nodes)[:limit]]
    edges = [{"source": u, "target": v, "kind": d.get("kind", "")}
             for u, v, d in list(g.edges(data=True))[:limit * 4]]
    return {"nodes": nodes, "edges": edges}


@app.get("/graph/central-phones")
def graph_central_phones(top: int = Query(15, ge=1, le=100),
                         user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    return {"phones": central_phones(phone_call_graph(b["cdr"]), top)}


@app.get("/flows/patterns")
def flows_patterns(min_amount: float = Query(10000, ge=0),
                   window_min: int = Query(15, ge=1),
                   user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    return {
        "circular": circular_flows(b, min_amount=min_amount),
        "rapid_in_out": rapid_in_out(b, window_min=window_min),
    }


@app.get("/ml/outliers")
def ml_outliers_endpoint(contamination: float = Query(0.05, gt=0, le=0.5),
                         min_txns: int = Query(5, ge=1),
                         user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    return ml.ml_outliers(b, contamination=contamination, min_txns=min_txns)


@app.get("/search")
def search(q: str = Query("", max_length=128),
           limit: int = Query(50, le=200),
           user: dict = Depends(auth.require_user)):
    b = _require_bundle()
    return search_bundle(b, q, limit=limit)


# ---------------------------------------------------------------- frontend
# Legacy endpoints the Next.js frontend (localhost:3000) calls; kept in the
# old shape so the UI works unchanged against this engine.


@app.post("/upload/parse-multi")
async def upload_parse_multi(files: list[UploadFile] = File(...),
                             user: dict = Depends(auth.require_user)):
    if not files:
        raise HTTPException(400, "no files uploaded")
    tmp = tempfile.mkdtemp(prefix="backend_upload_")
    names: list[str] = []
    for f in files:
        name = os.path.basename(f.filename or "upload")
        with open(os.path.join(tmp, name), "wb") as fh:
            fh.write(await f.read())
        names.append(name)
    _log.info("uploading %d files -> %s", len(names), tmp)
    with _lock:
        _state["bundle"] = ingest_folder(tmp)
        _persist()
    copilot_router.reset_engine()
    risk.clear_cache()
    risk.clear_hybrid_cache()
    _hybrid_warm(_state["bundle"])
    b = _state["bundle"]
    return {
        "detail": "fusion complete",
        "files": [{"name": n} for n in b["files"]["ok"]]
                 or [{"name": n} for n in names],
        "skipped": b["files"]["skipped"],
        "errors": b["files"]["errors"],
        "bank": len(b["bank"]), "cdr": len(b["cdr"]), "ipdr": len(b["ipdr"]),
        "complaints": len(b["complaints"]),
    }


@app.get("/scoring/alerts")
def scoring_alerts(min_risk: float = Query(50, ge=0, le=100),
                   limit: int = Query(100, le=1000),
                   user: dict = Depends(auth.require_user)):
    """Highest-risk *transactions* flagged by the behavioural engine.

    Accounts listed in the NCRP fraud complaint ledger receive a hard
    +60 boost (rule NCRP_FRAUD_ACCOUNT), so complaints never disappear
    from the alert feed regardless of transaction behaviour.
    """
    b = _require_bundle()
    if not b.get("bank"):
        return {"results": [], "total": 0}
    ncrp_accounts = {str(c.get("account_no") or "").strip()
                     for c in b.get("complaints", [])}
    ncrp_accounts.discard("")
    scored = list(_cached_scored(b))  # defensive copy: NCRP boost mutates rows
    results = []
    for s in scored:
        if s["account_no"] in ncrp_accounts and \
                "NCRP_FRAUD_ACCOUNT" not in s["rules_fired"]:
            s["risk_score"] = min(s["risk_score"] + 60, 100)
            s["risk_band"] = ("CRITICAL" if s["risk_score"] >= 75 else "HIGH"
                              if s["risk_score"] >= 50 else "MEDIUM")
            s["rules_fired"] = [*s["rules_fired"], "NCRP_FRAUD_ACCOUNT"]
            s["breakdown"] = [*s["breakdown"], {
                "rule": "NCRP_FRAUD_ACCOUNT", "points": 60,
                "reason": "Account is listed in the NCRP fraud complaint "
                          "ledger"}]
        if s["risk_score"] < min_risk:
            continue
        results.append({
            "transaction_id": s["transaction_id"],
            "sender_customer_id": s["sender_customer_id"],
            "amount_usd": s["amount"],
            "risk_score": s["risk_score"],
            "risk_band": s["risk_band"],
            "rules_fired": str(s["rules_fired"]),
            "rules": s["rules_fired"],
            "breakdown": s["breakdown"],
            "evidence": s["evidence"],
            "confidence": s["confidence"],
            "mode": s["mode"],
            "bank": s["bank"],
            "ncrp_states": [],
        })
        if len(results) >= limit:
            break
    return {"results": results, "total": len(results)}


_FUSED_CSV_COLUMNS = (
    "transaction_id", "date", "time", "mode", "amount", "direction",
    "account_no", "account_name", "bank", "counterparty_name",
    "counterparty_bank", "receiver_account", "sender_phone",
    "receiver_phone", "call_count", "ipdr_count", "ncrp",
    "risk_score", "risk_band",
)

_score_cache: dict = {}
_score_cache_lock = threading.Lock()


def _cached_scored(bundle: dict) -> list[dict]:
    """Behavioural risk scores for the loaded bundle, recomputed only when a
    new bundle is ingested (keyed on the store's last_ingested stamp plus
    bundle identity). On a 20k-row bundle the scoring pass takes ~10s, so
    sharing it across /scoring/alerts and the fused views keeps pagination
    and CSV exports instant after the first request."""
    stamp = store.last_ingested() or "none"
    with _score_cache_lock:
        if (_score_cache.get("stamp") == stamp
                and _score_cache.get("bundle") is bundle):
            return _score_cache["scored"]
        scored = score_transactions(bundle)
        _score_cache.clear()
        _score_cache.update({"stamp": stamp, "bundle": bundle,
                             "scored": scored})
        return scored


@app.get("/data/fused")
def fused_data(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
               q: str = Query(""), account: str = Query(""),
               risk_annotate: int = Query(0, ge=0, le=1),
               user: dict = Depends(auth.require_user)):
    """Fused bank x CDR x IPDR preview table (the post-ingestion fusion view).

    Pass risk_annotate=1 to attach behavioural risk scores to each row
    (expensive on large bundles — runs the full scoring engine once).
    """
    b = _require_bundle()
    scored = None
    if risk_annotate:
        scored = {s["transaction_id"]: s for s in _cached_scored(b)}
    return fused_table(b, offset=offset, limit=limit, q=q,
                       account=account, scored=scored)


@app.get("/data/fused.csv")
def fused_data_csv(q: str = Query(""), account: str = Query(""),
                   max_rows: int = Query(50000, ge=1, le=200000),
                   user: dict = Depends(auth.require_user)):
    """Download the fused dataset as CSV (the 'fused CSV' export)."""
    b = _require_bundle()
    page = fused_table(b, offset=0, limit=max_rows, q=q, account=account)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_FUSED_CSV_COLUMNS,
                            extrasaction="ignore")
    writer.writeheader()
    for row in page["rows"]:
        writer.writerow({k: row.get(k) for k in _FUSED_CSV_COLUMNS})
    data = "\ufeff" + buf.getvalue()
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="fused_data.csv"'},
    )
