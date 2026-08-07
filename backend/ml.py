"""Unsupervised anomaly detection layer (scikit-learn).

fraud_heat() applies deterministic rules; this module adds the ML component
of the "Rules + ML" requirement — an IsolationForest over account-level
behavioural features:

  * txn count, total credit/debit, average and max amount,
  * unique counterparties, phones and UPI ids (entity breadth),
  * round-amount share, night-hour share, rapid payout count.

Output is a z-scored anomaly score per account; the detector is refit on
every request over the current bundle so it adapts to the dataset at hand
and never sees labels (fully unsupervised, cold-start safe).
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest

from .fusion import rapid_payouts

_FEATURES = (
    "txn_count", "total_credit", "total_debit", "avg_amount",
    "max_amount", "uniq_counterparties", "uniq_phones", "uniq_upi",
    "round_share", "night_share", "rapid_payouts",
)


def _account_features(bundle: dict) -> list[dict]:
    bank = bundle.get("bank", [])
    night = 0
    agg: dict[str, dict] = {}
    for r in bank:
        acc = r.get("account_no") or ""
        if not acc:
            continue
        d = agg.setdefault(acc, {
            "account_no": acc, "credit": 0.0, "debit": 0.0, "amounts": [],
            "counterparties": set(), "phones": set(), "upis": set(),
            "round": 0, "night": 0, "txns": 0,
        })
        d["txns"] += 1
        amt = r.get("credit") or r.get("debit") or 0.0
        d["amounts"].append(amt)
        if r.get("credit"):
            d["credit"] += r["credit"]
        if r.get("debit"):
            d["debit"] += r["debit"]
        if r.get("receiver_account"):
            d["counterparties"].add(r["receiver_account"])
        for ph in (r.get("receiver_phone"), r.get("sender_phone")):
            if ph:
                d["phones"].add(ph)
        if r.get("upi_id"):
            d["upis"].add(r["upi_id"])
        if (r.get("debit") or 0) >= 1000 and (r.get("debit") or 0) % 5000 == 0:
            d["round"] += 1
        t = r.get("time") or ""
        if t and len(t) >= 5 and t[0] == "2":
            try:
                if int(t[:2]) >= 20:
                    d["night"] += 1
            except ValueError:
                pass

    rapids = {rp["account_no"] for rp in rapid_payouts(bundle)}
    rows = []
    for acc, d in agg.items():
        n = max(d["txns"], 1)
        rows.append({
            "account_no": acc,
            "txn_count": d["txns"],
            "total_credit": d["credit"],
            "total_debit": d["debit"],
            "avg_amount": sum(d["amounts"]) / n,
            "max_amount": max(d["amounts"]),
            "uniq_counterparties": len(d["counterparties"]),
            "uniq_phones": len(d["phones"]),
            "uniq_upi": len(d["upis"]),
            "round_share": d["round"] / n,
            "night_share": d["night"] / n,
            "rapid_payouts": 1 if acc in rapids else 0,
        })
    return rows


def _zscore_outliers(matrix: np.ndarray, contamination: float) -> set[int]:
    mean = matrix.mean(axis=0)
    std = matrix.std(axis=0)
    std[std == 0] = 1.0
    z = np.abs((matrix - mean) / std)
    mask = z.max(axis=1) >= 3.0
    return set(np.where(mask)[0].tolist())


def ml_outliers(bundle: dict, contamination: float = 0.05,
                min_txns: int = 5, cap: int = 100) -> dict:
    """Fit IsolationForest over account features; return flagged accounts.

    Accounts with fewer than `min_txns` are excluded (noise), and an
    extreme-feature (z-score) fallback catches cases the forest misses.
    """
    rows = _account_features(bundle)
    rows = [r for r in rows if r["txn_count"] >= min_txns]
    if len(rows) < 8:
        return {"fitted": False, "accounts": []}

    X = np.array([[float(r[f]) for f in _FEATURES] for r in rows])
    X = np.log1p(np.abs(X))
    model = IsolationForest(
        n_estimators=200, contamination=contamination,
        random_state=42, n_jobs=1)
    pred = model.fit_predict(X)
    flagged = set(np.where(pred == -1)[0].tolist())
    flagged |= _zscore_outliers(X, contamination)

    accounts = []
    for i in sorted(flagged):
        r = rows[i]
        accounts.append({
            "account_no": r["account_no"],
            "txn_count": r["txn_count"],
            "total_credit": round(r["total_credit"], 2),
            "total_debit": round(r["total_debit"], 2),
            "avg_amount": round(r["avg_amount"], 2),
            "max_amount": round(r["max_amount"], 2),
            "counterparties": r["uniq_counterparties"],
            "phones": r["uniq_phones"],
            "round_share": round(r["round_share"], 3),
            "night_share": round(r["night_share"], 3),
            "rapid_payouts": r["rapid_payouts"],
        })
    accounts.sort(key=lambda a: (-a["max_amount"], -a["total_debit"]))
    return {"fitted": True, "method": "isolation_forest+zscore",
            "accounts": accounts[:cap]}
