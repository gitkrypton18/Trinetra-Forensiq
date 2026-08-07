# Target Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              Investigator / API consumer                     │
│   Next.js frontend (unchanged) · curl · future LLM chat agent                │
└──────────────────────────────┬─────────────────────────────────────────────┘
                               │  HTTP (FastAPI)
┌──────────────────────────────▼─────────────────────────────────────────────┐
│  backend/api/  — routers: auth · ingest · entities · timeline ·           │
│                  correlation · anomalies · risk · graphs · analytics ·      │
│                  reports · search · query(NL-ready) · validation            │
└──────────────────────────────┬─────────────────────────────────────────────┘
┌──────────────────────────────▼─────────────────────────────────────────────┐
│  backend/pipeline.py  — orchestrator                                      │
│   detect ─▶ parse ─▶ normalise ─▶ resolve entities ─▶ build timeline ─▶     │
│   correlate ─▶ detect anomalies ─▶ score risk ─▶ build graph ─▶ report      │
└──────┬──────────────┬──────────────┬──────────────┬──────────────┬─────────┘
       │              │              │              │              │
┌──────▼──────┐ ┌─────▼─────┐ ┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼──────┐
│ detect/     │ │ parsers/  │ │ entities/   │ │ timeline  │ │ correlation│
│ confidence- │ │ plugin    │ │ registry +  │ │ fusion    │ │ rule engine│
│ scored      │ │ registry  │ │ resolver    │ │ + filters │ │ + evidence │
│ fingerprint │ │ bank/cdr/ │ │ (fuzzy,     │ │           │ │ payloads   │
│ engine      │ │ ipdr +    │ │ confidence) │ │           │ │            │
│             │ │ common/   │ │             │ │           │ │            │
└─────────────┘ └───────────┘ └─────────────┘ └───────────┘ └────────────┘
       │              │              │              │              │
┌──────▼─────────────▼──────────────▼──────────────▼──────────────▼───────┐
│ anomalies/ (rules + IF/LOF/DBSCAN + graph) · risk/ (explainable 0–100)  │
│ graphs/ (networkx + Neo4j-ready schema + analytics)                     │
│ analytics/ (stats · heatmaps · money flow · top entities)               │
│ reporting/ (PDF + DOCX + STR)                                           │
│ validate.py (ground-truth precision/recall/coverage)                    │
│ store.py (SQLite WAL now, PG-ready mapping) · schema.py (canonical v3)  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Principles

1. **Plugin parsers** — every parser registers itself (decorator) with:
   - supported file types, fingerprints, capability flags (tabular/line/meta),
   - parse entry point returning `ParseResult(records, meta, issues)`.
   Detection scores *candidate parsers* by fingerprints; the highest-confidence
   parser wins; below a threshold → `AskUser` result.
2. **Canonical v3 schema** (`schema.py`) — typed dataclass-like records:
   `BankTransaction`, `CDREvent`, `IPDREvent`, `SubscriberRecord` (SDR/CAF),
   `ComplaintRecord`, plus typed entity schemas `Customer`, `Phone`, `Account`,
   `IMEI`, `IMSI`, `Device`, `IPAddress`, `UPI`, `Beneficiary`, `Location`,
   `Tower`, `Case`, `Investigation`, `TimelineEvent`, `RiskScore`.
   Raw provider columns never escape the parser layer.
3. **Entity resolution** — deterministic exact keys first (normalised phone,
   IMEI, account, VPA, IP), then fuzzy fallbacks (edit distance on names/VPAs,
   truncated digits) with a confidence field on every link.
4. **Everything explainable** — correlation rules, anomaly detectors and risk
   contributions all emit `(rule_id, title, weight, evidence, reason)` so every
   finding can be audited by an investigator.
5. **Configuration-driven** — no hardcoded bank/operator names; operators,
   banks, layouts, rule thresholds, risk weights and windows come from
   `config.py` env vars + fingerprint catalogs.
6. **Synthetic + real compatibility** — ingestion adapters normalise the
   synthetic `data/clean|anomalous|final` CSV schemas onto the same canonical
   records; ground-truth CSVs drive `validate.py`.
7. **Scalability** — pandas dataframes internally for analytics; streaming
   ingest per file with timeout; graph built once and cached; Neo4j-ready
   schema so a Cypher export can be added without rework.
8. **Frontend contract preserved** — every endpoint in
   `frontend/lib/api.ts` keeps working.

## Module map (v3)

```
backend/
├── __init__.py        version
├── config.py          env-driven settings (new knobs: windows, weights, timeouts)
├── log.py             structured logging (parser/pipeline/api/correlation channels)
├── errors.py          SkipFileError, ParseError, DetectError, AskUser
├── schema.py          canonical v3 records + entities + format registry
├── detect/
│   ├── engine.py      DetectionResult(parser_id, dataset, confidence, hints)
│   └── fingerprints.py  signature catalog (headers/keywords/regex/magic bytes)
├── parsers/
│   ├── base.py        Parser base + ParseResult
│   ├── registry.py    decorator-driven plugin registry
│   ├── common/        csvutil · textutil (amounts/dates/phones) · pdftotext ·
│   │                  spreadsheet (xlsx/ods/xls unified)
│   ├── bank/          generic_line (PDF/TXT), generic_tabular (CSV/XLS/XLSX/ODS),
│   │                  families.py layout catalog
│   ├── cdr/           jio_vvm · jio_nodal · vi · airtel · sdr
│   └── ipdr/          jio_ipv6 · generic xlsx · generic csv
├── normalise.py       canonicalisation + narration NLP (UPI/refs/phones/banks)
├── entities/
│   ├── registry.py    typed entity index
│   └── resolver.py    deterministic + fuzzy linking with confidence
├── timeline.py        fused event stream + filters (kind/entity/relationship/time)
├── correlation/
│   ├── engine.py      runs registered rules over timeline+entities
│   └── rules.py       call→txn, txn→call, shared IMEI/IP/UPI/beneficiary, device reuse…
├── anomalies/
│   ├── rules.py       structuring · layering · smurfing · rapid in-out · dormant …
│   ├── ml.py          IsolationForest · LOF · DBSCAN · z-score (cached)
│   ├── graph_anomalies.py  community/centrality outliers
│   └── engine.py      hybrid explainable detector
├── risk/
│   ├── rules.py       contribution catalog (mule link, shared IMEI, circular flow…)
│   └── scorer.py      0–100 per entity + explanation
├── graphs/
│   ├── builder.py     money · call · entity · investigation graphs
│   ├── analytics.py   shortest path · communities · centrality · money flow
│   └── schema.py      Neo4j-ready node/edge types
├── analytics.py       stats · heatmaps · top entities · flows
├── reporting/
│   ├── pdf.py         STR + forensic PDF
│   ├── docx.py        forensic DOCX
│   └── sections.py    shared builders (summary/entities/timeline/evidence)
├── pipeline.py        orchestrator + per-file timeout + progress
├── store.py           SQLite (bundle + investigations) · PG mapping doc
├── validate.py        ground-truth comparison (precision/recall/coverage)
└── api/               auth · ingest · entities · timeline · correlation ·
                       anomalies · risk · graphs · analytics · reports ·
                       search · query · validation · main assembly
```

## Execution order (phases)

1. Audit + archive + deps (done) → 2. schema/errors/config/log →
3. detect engine → 4. parser plugin framework + bank/cdr/ipdr plugins →
5. normalise v3 + SDR/complaints → 6. entity registry + resolver →
7. timeline → 8. correlation engine → 9. anomalies → 10. risk →
11. graphs + analytics → 12. reporting → 13. pipeline orchestrator →
14. store + investigations → 15. API package (frontend contract) →
16. validation vs ground truth → 17. synthetic adapters →
18. test suite expansion → 19. full-dataset verification + perf + docs.
