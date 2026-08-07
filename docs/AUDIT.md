# Repository Audit (v2.2 → v3)

Audit date: 2026-08-06
Scope: complete repository audit of `AI-BANK-TRANSACTIONS-TELECOM-ANALYZER` before the v3 production rebuild.
Method: source review of every module, full test-suite run, and a measured baseline parse of the real
Surat Police dataset (334 files, 157 MB, copied to `data/full_dataset`, gitignored).

---

## 1. Repository inventory

| Path | Purpose | Verdict |
|---|---|---|
| `backend/` | FastAPI v2.2 engine: detect → parse → normalise → fuse → score → report | **RETAIN as base, deep refactor** |
| `backend/` | Legacy v2.0 FastAPI (pdf-parser, scoring, graph, reports, upload, notebooks, joblib models) | **DEAD — archived to `legacy_archive/`** |
| `frontend/` | Next.js 16 UI (dashboard, ingest, timeline, network, anomalies, reports) | **KEEP unchanged** |
| `frontend_old/` | Legacy React/Vite UI | **DEAD — archived to `legacy_archive/`** |
| `tests/` | 40 pytest tests (pipeline 9, api 18, auth 13) | Keep, extend heavily |
| `data/` | Synthetic datasets (clean/anomalous/final), ground truth CSVs, police samples, SQLite store | Keep, extend |
| `docs/` | (empty before this audit) | Add AUDIT / ARCHITECTURE / MODULES |
| `scripts/` | `backend/scripts` (archived) + `backend` smoke tests | Merge useful scripts into new tooling |

---

## 2. Module-level audit of `backend/`

### 2.1 `detect.py` — format detection
- **Purpose**: classify a file as BANK/CDR/IPDR + format family.
- **Problems**:
  - Keyword heuristics only; **no confidence score**, no low-confidence → ask-user path.
  - All `.xlsx` classified BANK unless `classify_xlsx` says IPDR; `.ods` treated as BANK xlsx but never parsed (silently 0 rows — measured).
  - PDF classification: any PDF without CDR markers becomes BANK (CAF forms, subscriber-detail PDFs, scanned evidence land in BANK and are skipped as scanned — acceptable but untracked).
  - `.7z/.zip/.rar` returned as ARCHIVE but never handled by the pipeline (1 `.7z` file in dataset).
  - No extensionless-file handling (5 extensionless files in dataset; 4 are text dumps that must be sniffed by content).
- **Verdict**: REWRITE as confidence-scored detection engine with pluggable fingerprints.

### 2.2 `parsers_bank.py` — bank parsers
- **Purpose**: PDF (line-based), xlsx, txt, csv bank statements.
- **Good**: the generic line parser handles 14+ bank layouts (axis8/axis7, federal, hdfc, kotak, bandhan, pnb, union, icici, utkarsh, yes, associate, cityunion, rbl, generic); handles split dates (Bandhan), truncated years (HDFC), Cr/Dr suffixes, two-line headers, control blocks. Measured: 197 PDFs → 31,543 rows, 25 skipped as scanned (correct), 1 real miss (DBS "unreadable").
- **Problems**:
  - **CSV parser measured 0 rows on the 3 real bank CSV files** (header mapping is too strict; `bank_parsed.csv` has a wide synthetic schema).
  - xlsx parser is minimal (central-bank compact dates + one generic layout); no ODS, no legacy XLS.
  - No per-family plugin isolation; everything in one module; layout configs are module-level dicts.
  - `_normalise_row` heuristics (debit/credit from balance delta) can silently misclassify direction.
- **Verdict**: REFACTOR line-parser core into `parsers/bank/`, REWRITE tabular parsers (csv/xlsx/ods/xls), make families data-driven plugins.

### 2.3 `parsers_cdr.py` — CDR parsers
- **Purpose**: Jio VVM (F1), Vi (F2), Jio nodal (F3), Airtel (F4), Airtel SDR (F5).
- **Good**: measured 40 jio_vvm files → 177,304 rows; 40 vi → 137,872; 23 airtel → 20,442; 3 jio_nodal → 236. Robust CSV dialect handling (`="..."` quoting, BTS addresses with commas). A/B orientation against query value.
- **Problems**:
  - SDR (subscriber detail) returns **0 records** — metadata is dropped, yet it contains CAF-grade data (name, address, DOB, IMEI/IMSI, circle) needed for entity resolution.
  - IMEI-ticket CDRs (`vi_imei_*`, `airtel_imei_*`) parse `a_number` = IMEI (normalise_phone discards it) — IMEI-query CDRs lose their query identity.
  - Cell sites with lat/long (Vi columns `First_LAT`, `First_Long`) are dropped — location analytics impossible.
  - Duplicated `_canon` header scaffolding between files (acceptable, but move to base).
- **Verdict**: REFACTOR into plugins, ADD SDR record capture + IMEI-query support + lat/long capture.

### 2.4 `parsers_ipdr.py` — IPDR parsers
- **Purpose**: Jio IPv6 24-column CSV + generic xlsx.
- **Problems**: measured only 119 + 9 records total; `ipdr_xlsx` maps a tiny header subset and drops `f date/t date` row-level date parsing for datetime cells; end_ts computed from `date` + `end_time` but xlsx rows often have date in `f date` only.
- **Verdict**: REFACTOR into plugins, extend generic xlsx mapping, add multi-sheet discovery.

### 2.5 `normalise.py` — canonical normalisation + entity extraction
- **Problems**: entity registry is ad-hoc dicts (no typed entities, no confidence, no linkage); narration regexes are bank-UPI-specific; mode detection decent but incomplete; no counterparty-account/IFSC extraction from narrations.
- **Verdict**: REWRITE onto v3 canonical schema + typed entity registry.

### 2.6 `fusion.py` — timeline, coincidence, fraud heat
- **Problems**: timeline is a plain list rebuilt per request (no filters for entity/relationship); `kind` for complaints missing (frontend schema expects it); correlation is 5 hand-written functions, none with explainable evidence; `fraud_heat` mixes rules + scoring with opaque flags.
- **Verdict**: REWRITE into `timeline.py` + `correlation/` rule engine + `risk/` scorer.

### 2.7 `ml.py` — anomaly detection
- **Problems**: IsolationForest + z-score only; account-level only; no LOF/DBSCAN, no graph anomalies, no explainability, refits per request.
- **Verdict**: REWRITE into `anomalies/` (hybrid rules + ML + graph), cached fit.

### 2.8 `graphs.py` — networkx graphs
- **Problems**: 3 builders + ego/central; no shortest-path, community, centrality or money-flow analytics APIs; no Neo4j-ready schema.
- **Verdict**: REFACTOR into `graphs/` with analytics + schema.

### 2.9 `report.py` — STR PDF
- **Problems**: PDF only, single monolithic builder; no DOCX, no evidence/network/anomaly/recommendation sections; table rows truncated.
- **Verdict**: REWRITE into `reporting/` (pdf + docx + shared sections).

### 2.10 `store.py` / `auth.py` / `config.py` — infra
- **Good**: SQLite WAL persistence, stdlib-only JWT+PBKDF2 auth with lockout, env-config.
- **Problems**: bundle-as-JSON blob (no per-record query, no investigations/cases); auth tokens manual (fine); config lacks pipeline knobs (timeouts, threads, correlation windows).
- **Verdict**: REFACTOR store to keep bundle + add investigations; extend config; keep auth.

### 2.11 `api.py` — FastAPI surface
- **Good**: 40 tests pass against it; frontend contract captured in `frontend/lib/api.ts`.
- **Problems**: single-file app; ingest is folder-path only (upload limited to 6 files); no entities/correlation/anomalies/graph-analytics/validation routers beyond minimal ones.
- **Verdict**: REWRITE into `api/` package with routers; preserve every endpoint the frontend calls.

---

## 3. Measured baseline (v2.2) on the real dataset

| Dataset | Files | Records | Notes |
|---|---|---|---|
| BANK pdf | 197 | 31,543 | 25 scanned skipped (correct), 1 DBS miss |
| BANK xlsx | 8 | 738 | central-bank + generic only |
| BANK txt | 4 | 119 | |
| BANK csv | 3 | **0** | real regression |
| CDR (all) | 107 | 335,858 | strong |
| IPDR (all) | 9 | 128 | weak |
| **Total** | **334** | **368,386** | elapsed 512 s |

Known dataset facts:
- 334 files: 197 PDF, 117 CSV, 13 xlsx (post-validation-folder eviction), 4 TXT, 1 ODS, 5 extensionless text dumps, 1 `.7z` (password-protected HDFC).
- `Validation_Ground_Truth/` (83 police xlsx reports) was evicted from OneDrive during the audit; validator will support its format (Add Summary / Common A&B / Common IMEI / Common First-Cell-ID reports) for when it is restored.
- NCRP complaints ledger `All Account complain.csv` parses cleanly (166 rows).

---

## 4. Gap analysis vs official problem statement (ERH26_PS_03)

| Requirement | v2.2 status | v3 plan |
|---|---|---|
| I-a parse bank PDF/Excel/CSV | partial | full (PDF/CSV/XLS/XLSX/ODS/TXT, plugin registry) |
| I-b CDR/IPDR operators | good CDR, weak IPDR | add SDR, IMEI-query, IPDR layouts |
| I-c schema auto-detection | heuristic, no confidence | confidence-scored engine + ask-user fallback |
| II-a unified timeline | naive | typed timeline + entity/kind/relationship filters |
| II-b temporal coincidences | 1 window rule | rule engine (call→txn, txn→call, IMEI/IP windows) |
| II-c entity linking | exact match only | resolver: deterministic + fuzzy + confidence |
| III-a rules + ML anomalies | partial | hybrid: rules + IF/LOF/DBSCAN + graph anomalies |
| III-b risk scoring | opaque flags | 0–100 per entity with per-rule contributions |
| III-c mule signatures | partial | explicit mule rules |
| IV-a money/communication graphs | basic | + shortest-path, communities, centrality, flow |
| IV-b filter/search | substring search | entity/time/location filters + search |
| IV-c forensic report | PDF only | PDF + DOCX, evidence/anomaly/network/STR sections |
| Bonus STR | yes (PDF) | yes, automated + cached |
| Bonus NL layer | no | query APIs designed for LLM backends |
| Deliverable: validation | no | `validate.py` — precision/recall/coverage |
| Synthetic dataset compat | no | ingestion adapters for clean/anomalous CSVs |

---

## 5. Keep / Rewrite / Delete decision

**RETAIN (refactor):** util phone/date/amount/CSV helpers; bank PDF line-parser core + family layouts; CDR parser row-mapping logic; store SQLite pattern; auth (PBKDF2 + HMAC-JWT); config pattern; networkx graph builders; reportlab STR pattern; frontend API contract.

**REWRITE:** detect engine; tabular parsers; normalise + narration NLP; entity registry/resolver; timeline; correlation rule engine; anomaly engine; risk scorer; analytics; reporting (add DOCX); validation; API package.

**DELETE/ARCHIVE:** `backend/`, `frontend_old/`, stale joblib models, scratch scripts, `BANK_PATTERN_CATALOG.md` (superseded by fingerprint catalog in code), old smoke tests.

**Integration requirements:** synthetic `data/clean|anomalous|final` CSV schemas must ingest via adapters; `data/ground_truth` CSVs drive validation metrics.
