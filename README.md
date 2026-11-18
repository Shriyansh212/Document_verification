# Document Verification Pipeline — AI-Powered Document Processing & Validation

An end-to-end KYC and financial document verification platform built with **Python**, **FastAPI**, **Tesseract OCR**, **Groq Llama**, **SQL (SQLAlchemy)**, and a **React + TypeScript + Tailwind CSS** dashboard.

## Key Features

- **Multi-Format Document Ingestion & OCR**: Accepts identity (`passport`, `drivers_license`, `national_id`) and financial (`bank_statement`, `tax_document`, `utility_bill`, `pay_stub`, `invoice`) documents in image (`PNG`, `JPG`, `WEBP`, `TIFF`), `PDF`, or plain-text formats with Pillow image preprocessing and **Tesseract OCR**.
- **Structured LLM Extraction (Groq Llama)**: Extracts normalized structured JSON fields (dates, holder identity, document numbers, issuing authorities, account numbers, financial totals, and confidence scores) using **Groq Llama (`llama-3.3-70b-versatile`)**, with an automatic local heuristic fallback when `GROQ_API_KEY` is not set.
- **Modular Python Validation Engine**: Flags missing required fields, malformed dates, expired documents, chronological anomalies (e.g., issue date before DOB or after expiry), low OCR/extraction confidence, and applicant cross-check discrepancies (fuzzy name similarity, DOB/ID mismatches).
- **Deterministic Decision Workflow**: Computes a transparent risk score (`0–100`) and routes every document to **`PASS`**, **`FAIL`**, or **`MANUAL_REVIEW`**.
- **SQL Persistence & Immutable Audit Logging**: Stores documents, normalized extracted fields, verification outcomes, and stage-by-stage audit events (`DOCUMENT_UPLOADED`, `OCR_COMPLETED`, `EXTRACTION_COMPLETED`, `VALIDATION_COMPLETED`, `DECISION_ROUTED`, `MANUAL_REVIEW_SUBMITTED`) in SQLite (default) or PostgreSQL via `DATABASE_URL`.
- **Interactive Compliance Dashboard**: React SPA with KPI analytics, drag-and-drop uploader, one-click sample scenarios, extracted field inspector, validation flag breakdown, manual review queue with analyst sign-off, and filterable SQL audit ledger.

## Architecture

```text
Document Upload (Image / PDF / Text)
        │
        ▼
[1] Preprocessing & OCR (Pillow + Tesseract OCR / pypdf)
        │
        ▼
[2] Structured Field Extraction (Groq Llama JSON mode)
        │
        ▼
[3] Python Validation Engine (Required fields, dates, cross-check rules)
        │
        ▼
[4] Decision Workflow Routing (PASS / FAIL / MANUAL_REVIEW)
        │
        ▼
[5] SQL Storage & Immutable Audit Logs (SQLAlchemy -> SQLite / PostgreSQL)
```

## Project Structure

```text
document-verification-pipeline/
├── backend/
│   ├── app/
│   │   ├── api/routes.py             # FastAPI REST endpoints
│   │   ├── core/config.py            # Environment & settings management
│   │   ├── db/session.py             # SQLAlchemy engine & sessions
│   │   ├── models/document.py        # SQL tables (documents, extracted_fields, outcomes, audit_logs)
│   │   ├── schemas/document.py       # Pydantic v2 response/request schemas
│   │   ├── services/
│   │   │   ├── ocr_service.py        # Pillow preprocessing + Tesseract OCR + PDF extraction
│   │   │   ├── llm_extractor.py      # Groq Llama structured JSON extraction + fallback
│   │   │   ├── validator.py          # Modular Python validation rules
│   │   │   ├── decision_engine.py    # Risk scoring & PASS/FAIL/MANUAL_REVIEW routing
│   │   │   ├── audit_service.py      # Immutable SQL audit logging
│   │   │   ├── pipeline.py           # End-to-end orchestration & manual review handler
│   │   │   └── samples.py            # Built-in identity & financial test scenarios
│   │   └── main.py                   # FastAPI entry point & production SPA serving
│   ├── tests/                        # Unit & integration test suite (pytest)
│   └── requirements.txt
├── frontend/                         # React + TypeScript + Vite + Tailwind dashboard
├── Dockerfile                        # Multi-stage build (Node + Python + Tesseract OCR)
├── render.yaml                       # One-click Render deployment blueprint
└── .env.example
```

## Local Development

### 1. Backend (FastAPI)

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r backend/requirements.txt
cp .env.example .env
# Optional: set GROQ_API_KEY in .env to enable live Groq Llama extraction

uvicorn app.main:app --app-dir backend --reload --port 8000
```

Interactive OpenAPI docs will be available at `http://localhost:8000/docs`.

### 2. Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api/*` requests directly to FastAPI on port `8000`.

### 3. Run Tests

```bash
pytest backend/tests -v
```

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Service health & OCR/LLM engine status |
| `GET` | `/api/v1/stats` | Aggregated pipeline KPIs and pass rate |
| `POST` | `/api/v1/documents/verify` | Upload image/PDF/TXT document through full verification pipeline |
| `POST` | `/api/v1/documents/verify-text` | Submit raw OCR text payload directly |
| `GET` | `/api/v1/documents` | List verification records with status & search filters |
| `GET` | `/api/v1/documents/{id}` | Inspect extracted fields, flags, decision, and audit trail |
| `POST` | `/api/v1/documents/{id}/review` | Submit analyst manual review override (`PASS` / `FAIL`) |
| `DELETE` | `/api/v1/documents/{id}` | Remove a verification record |
| `GET` | `/api/v1/audit-logs` | Query global immutable SQL audit ledger |
| `GET` | `/api/v1/samples` | List built-in demo verification scenarios |
| `POST` | `/api/v1/samples/{id}/run` | Execute a built-in demo scenario end-to-end |

## Deployment

### Deploy with Render (Recommended — Free Tier Ready)

This repository includes a production `Dockerfile` (with **Tesseract OCR** pre-installed and the compiled React frontend bundled into FastAPI) and a `render.yaml` Blueprint:

1. Push this repository to GitHub.
2. Go to [Render](https://render.com) &rarr; **New +** &rarr; **Blueprint** and connect your repository.
3. Add your `GROQ_API_KEY` environment variable (get a free key at [console.groq.com](https://console.groq.com)).
4. Deploy — Render builds the Docker image and serves both the React dashboard and FastAPI backend from one HTTPS URL.

### Deploy with Docker

```bash
docker build -t document-verification-pipeline .
docker run -p 8000:8000 -e GROQ_API_KEY=your_key_here document-verification-pipeline
```
