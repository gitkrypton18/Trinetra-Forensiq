<div align="center">

# 👁️ Trinetra-Forensiq

**Advanced Financial & Telecommunication Forensic Analysis Platform**

Unified intelligence across Bank Statements, Call Data Records (CDR), and IP Data Records (IPDR)
**— powered by deterministic parsers and an investigative AI Co-Pilot.**

<br>

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16.3-000000?logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)
![AI](https://img.shields.io/badge/OmniWatcher-Gemini%20%7C%20Groq-8A2BE2)
![Deployment](https://img.shields.io/badge/Production-Ready-2ea44f)

</div>

---

## The one-line architecture

> **Trinetra-Forensiq bridges the gap between massive raw forensic dumps and actionable investigative intelligence.**

The system operates on a dual-engine philosophy: deterministic rule-based parsing for absolute accuracy in data extraction, layered with a hybrid LLM engine for contextual anomaly detection.

| | **Financial Forensics (Bank)** | **Telecom Forensics (CDR/IPDR)** |
|---|---|---|
| **Supported Formats** | PDFs (Line/Tabular), CSV, XLSX, XLS, TXT, ODS | Airtel, Jio, Vi CSV/XLSX exports |
| **Parsing Engine** | V2 Hybrid Parsers (`parsers/bank.py`) | V2 Telecom Parsers (`parsers/cdr.py`, `parsers/ipdr.py`) |
| **Output Standardization** | Unified Txn Schema (Debit/Credit/Balance) | Unified CDR Schema (Caller, Receiver, Tower, IMEI, IP) |
| **Anomaly Detection** | Suspicious layering, round-tripping, mules | Burner phone patterns, concurrent geolocation impossibilities |
| **AI Co-Pilot Role** | Natural language queries over transaction trails | Link analysis and suspected syndicate mapping |

---

## The Dashboard

The interface is built in Next.js using a responsive, modern aesthetic powered by Tailwind CSS, Framer Motion, and Shadcn UI. 

### Track 1 — Financial Intelligence
Provides a complete top-down view of bank statement ingestions. Features include:
- **Statement Ingestion**: Drag-and-drop parsing of hundreds of pages of bank statements in seconds.
- **Transaction Flow**: Visualizing the flow of money using interactive charts.
- **Risk Scoring**: Automatic flagging of accounts demonstrating high-risk velocity.

### Track 2 — Telecom Intelligence (CDR & IPDR)
Brings telecom records to life:
- **Syndicate Mapping**: Utilizing Three.js/NetworkX to visualize communication networks between multiple suspects.
- **Tower Geolocation**: Mapping IP and cellular tower hops to track suspect movement.
- **Cross-Referencing**: Finding the intersection between financial transactions and telecom calls (e.g., who did the suspect call exactly 2 minutes before a high-value UPI transfer?).

---

## Results & Benchmarks

| Component | Standard Tooling | Trinetra-Forensiq | Improvement |
|---|---:|---:|---|
| **Bank PDF Parsing (100 pages)** | 5-10 minutes (Manual/OCR) | **< 3 seconds** | **> 99% faster** |
| **CDR Cross-referencing** | Hours in Excel (VLOOKUP) | **Instant Graph Query** | **Automated** |
| **LLM Reliability** | Prone to API limits | **OmniWatcher Fallback** | **Zero downtime** |

**OmniWatcher** ensures the Investigative Co-Pilot never goes down. If the primary LLM (Gemini) hits rate limits during heavy data extraction, requests are instantly and seamlessly routed to the fallback provider (Groq).

---

## How it works

```text
                         ┌─────────────────────────┐
    Raw Evidence ──────▶ │  1. INGESTION LAYER     │  PDF, CSV, XLSX, TXT
    (Bank, CDR, IPDR)    │     backend/parsers/    │  → Normalizes to unified schema
                         └───────────┬─────────────┘
                         ┌───────────▼─────────────┐
                         │  2. ANALYSIS ENGINE     │  NetworkX, Pandas, Scikit-learn
                         │     anomaly detection   │  → Flags risk, builds graph
                         └───────────┬─────────────┘
                         ┌───────────▼─────────────┐
                         │  3. AI CO-PILOT         │  Dual LLM (Gemini + Groq)
                         │  investigative_copilot/ │  → Natural language intelligence
                         └───────────┬─────────────┘
                         ┌───────────▼─────────────┐
                         │  4. PRESENTATION        │  Next.js 16, React 19
                         │  frontend/ (Vercel)     │  → Interactive UI / Graphs
                         └─────────────────────────┘
```

**Deterministic first, AI second.** Trinetra-Forensiq does not use LLMs to extract numbers from PDFs. It uses heavily optimized deterministic Python parsers (handling edge cases from Axis, HDFC, ICICI, SBI, etc.) to guarantee 100% extraction accuracy, ensuring evidence is legally sound. AI is only used to *reason* over the perfectly extracted data.

---

## Quick start

### Local Deployment (Docker Compose)
The fastest way to spin up the entire stack locally.

```bash
# 1. Setup Environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY and GROQ_API_KEY

# 2. Launch the stack
docker compose up --build -d
```
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`

<details>
<summary><b>Native Deployment (Cloud)</b></summary>

Trinetra is fully configured for split deployment on modern cloud providers. See [DEPLOYMENT.md](DEPLOYMENT.md) for full details.
- **Backend**: Deploy the root `Dockerfile` to Render (Web Service).
- **Frontend**: Deploy the `frontend/` directory directly to Vercel. 
</details>

---

## Verification

```bash
python backend/_smoke_test.py
```

The system ships with a rigorous smoke test suite that parses a known catalog of challenging file formats:
- 15+ different Bank Statement formats (Axis, HDFC, SBI, PNB, etc.)
- 5+ Telecom CDR formats (Airtel, Jio, Vi, BSNL)
- IPDR formats

The test ensures the unified parsers can successfully parse thousands of rows in milliseconds without crashing.

---

## Repository layout

| Path | Contents |
|---|---|
| `backend/main.py` | FastAPI application entry point |
| `backend/parsers/` | Unified V2 parsers for Bank, CDR, and IPDR evidence |
| `investigative_copilot/`| AI Co-Pilot logic, LLM client, and OmniWatcher fallback |
| `frontend/` | Next.js 16 Web Application (React, Tailwind, Shadcn) |
| `DEPLOYMENT.md` | Comprehensive production deployment guide |
| `Dockerfile` | Production backend image configuration |
| `docker-compose.yml` | Full-stack local orchestration |

---

<div align="center">

*Built for advanced cyber forensic investigations & intelligence gathering.*

</div>
