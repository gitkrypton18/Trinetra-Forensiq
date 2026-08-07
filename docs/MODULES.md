# Module Map

Backend package layout (`backend/`), the API surface, and the verification
harnesses. See `docs/ARCHITECTURE.md` and `docs/AUDIT.md` for design and
data-flow decisions.

## Package layout

| Module | Purpose |
|---|---|
| `schema.py` | Canonical record columns for BANK / CDR / IPDR / SUBSCRIBER / COMPLAINT datasets; format ids; entity & event constants; `empty_record()` factory. |
| `errors.py` | Error taxonomy: `BackendError` base; `DetectError`, `ParseError`, `SkipFileError`, `AskUser`, `ValidationError`. |
| `config.py` | Runtime knobs (env-driven): ingest limits, correlation window, report paths, API binding. |
| `log.py` | Structured logging (JSON lines) for the pipeline and API. |
| `pipeline.py` | `parse_file()` / `ingest_folder()` / `parse_ncrp_complaints()` — routes files through the parser registry, normalises records, bundles output, returns skip/error tallies. |
| `normalise.py` | Raw row → canonical record (`normalise_bank/cdr/ipdr/subscriber/complaints`), phone/account canonicalisation, `extract_entities()` (phones, accounts, IMEIs, subscriber names, complaint cross-refs). |
| `fusion.py` | Timeline fusion & correlation: `build_timeline`, `correlate_phones` (bank↔CDR phone coincidence), `rapid_payouts`, `rapid_in_out`, `fraud_heat` (composite account/phone/UPI risk scores), `search_bundle`. |
| `ml.py` | Statistical / ML anomaly detection (IsolationForest on engineered features) with explainability. |
| `graphs.py` | Investigation graphs: money flow (account↔account), phone↔account, account↔phone, central-entity ranking, UPI/payout patterns. |
| `report.py` | Forensic reports: `generate_pdf_report()` (reportlab) and `generate_docx_report()` (python-docx) with executive summary, risk tables, coincidence and payout sections. |
| `store.py` | SQLite persistence: bundle tables + investigations/findings CRUD (store/load/clear). |
| `api.py` | FastAPI v3 app (see API surface below). |
| `validate/` | Validation suite: `ground_truth.py` (synthetic CSV GT readers + police xlsx structural reader), `comparator.py` (ID coverage, correlation precision/recall, anomaly confusion matrix), `run()` entry point + CLI. |
| `adapters/synthetic.py` | Problem-statement synthetic dataset (`data/clean`, `data/anomalous`) → canonical bundle; `full_validation()` one-shot harness. |
| `detect/` | Format detection: `fingerprints.py` (19 signatures incl. EMAIL_COVER, CAF_FORM, SUBSCRIBER_DETAIL, binary), `engine.py` (`classify_file` with skip reasons, v2-compat `classify`/`classify_xlsx`). |
| `parsers/` | Parser plugins: `base.py` (BaseParser, ParseResult), `registry.py`, `common/spreadsheet.py` (xlsx/xls/ods row iterator), `common/csvutil.py`, plus `bank.py`, `cdr.py`, `ipdr.py`, `subscriber.py`, `complaint.py`. |
| `parsers_bank.py` | v2 bank row engines (axis/hdfc/centralbank/… PDF & CSV families) — row-level backends kept behind the plugins. |
| `parsers_cdr.py` | v2 CDR row engines (airtel/jio_nodal/jio_vvm/vi) incl. lat/lon mapping. |
| `parsers_ipdr.py` | v2 IPDR row engine (jio_ipv6 / generic). |

## Registered parser formats (17)

`airtel`, `airtel_sdr`, `bank_csv`, `bank_ods`, `bank_pdf`, `bank_txt`,
`bank_xls`, `bank_xlsx`, `caf_form`, `ipdr_csv`, `ipdr_xlsx`, `jio_ipv6`,
`jio_nodal`, `jio_vvm`, `ncrp_complaints`, `subs_detail`, `vi`.

## API surface (v3.0.0)

Data: `POST /ingest/upload`, `POST /ingest/clear`, `GET /ingest/status`,
`GET /summary`, `GET /accounts`, `GET /phones`, `GET /entities`,
`GET /phone/{phone}/egonet`, `GET /timeline`, `GET /coincidence`,
`GET /moneygraph`, `GET /accountgraph`, `GET /phonegraph`, `GET /central`,
`GET /flows`, `GET /patterns`, `GET /outliers`, `GET /search`, `GET /report`.

Investigations: `GET/POST /investigations`, `GET/PATCH/DELETE
/investigations/{id}`, `POST /investigations/{id}/findings` (delete is
admin-gated).

## Verification harnesses

| Harness | What it proves |
|---|---|
| `tests/` — 50 tests | Classification, parsing, normalisation, ingest, API, auth, validation suite. Run: `python -m pytest tests -p no:warnings`. |
| `Temp/opencode/sweep_detect.py` | Full 334-file sweep → zero misclassifications, skip reasons audited. |
| `Temp/opencode/smoke_parsers.py` | All 17 parser formats exercised on real files. |
| `Temp/opencode/bench_ingest.py` | Full-dataset ingest: 567 s; 32.5k bank / 335.9k cdr / 128 ipdr / 24 complaints / ~63 subscribers; 239 ok / 95 skipped / 0 errors. |
| Synthetic validation | `backend.adapters.synthetic.full_validation("data", "data/ground_truth")`: ID coverage 1.0 (bank/cdr/ipdr), correlation recall 1.0 (bank↔CDR precision 0.84, CDR↔IPDR precision 0.93 @ GT window), anomaly detection F1 0.90 @ risk threshold 25 (P 0.84 / R 0.96). |

## Known external dependency

Police `Validation_Ground_Truth/` xlsx folder is evicted from OneDrive; the
police xlsx reader (`validate.ground_truth.read_police_gt`) is implemented
and structural-tested and will consume the folder when restored.
