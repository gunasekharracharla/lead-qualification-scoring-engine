# AI Lead Qualification & Scoring Engine

An AI-assisted B2B lead qualification application built with FastAPI, SQLAlchemy, and a static HTML/CSS/JavaScript frontend. It combines AI interpretation with deterministic ICP checks and weighted scoring, then returns an explainable qualification result and sales action plan.

> **Project status:** Portfolio project / working prototype. It is not presented as a production-ready, multi-tenant SaaS product. Review the security, privacy, and deployment requirements before using real customer data.

## What it does

- Accepts lead and company details through a browser form or JSON API.
- Optionally researches a company website by fetching the homepage and up to two relevant pages on the same site. Research is bounded and best-effort; some sites may block or not expose readable content.
- Uses an AI provider to interpret supplied lead information and available website text into structured signals.
- Applies deterministic ICP rules and configurable scoring weights; the AI does not choose the final numeric score.
- Classifies results as HOT, WARM, or COLD and provides recommendations and a sales action plan.
- Tracks a lead's sales status and preserves each qualification run with its input snapshot and rules fingerprint.
- Persists lead and qualification data in SQLite by default.
- Provides endpoints to create/update, retrieve, list, and delete leads.

Website research is not comprehensive enrichment, and the application does not scrape LinkedIn profile content.

## How qualification works

```text
Lead input
   ↓
Best-effort website research (when a website is supplied)
   ↓
AI assessment of supplied/researched context
   ↓
Deterministic ICP evaluation and weighted scoring
   ↓
Classification, offer recommendation, and sales action plan
   ↓
Persisted result and browser/API response
```

The scoring weights and classification thresholds are configurable in `backend/rules/scoring_rules.json`. ICP criteria and offers are configured in `backend/rules/icp_rules.json` and `backend/rules/offer_rules.json`.

## Technology

- Python, FastAPI, Pydantic
- SQLAlchemy and SQLite (default)
- HTML, CSS, and vanilla JavaScript
- OpenAI-compatible provider integrations for Groq and OpenAI
- Optional Gemini integration (install `google-generativeai` before selecting Gemini)
- pytest and FastAPI TestClient

## Run locally

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies and configure environment

```bash
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env`. On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

To enable live AI analysis, set `AI_ENABLED=true` and provide a valid key for the selected provider in `.env`. Never commit `.env` or share its contents. With AI disabled, the application uses its fallback assessment.

### 3. Start the application

```bash
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open the UI at <http://127.0.0.1:8000/>. API documentation is available at <http://127.0.0.1:8000/docs>.

## Deploy frontend on Netlify and API on Render

The Netlify site hosts the static UI; the FastAPI API and database run separately.
The Render blueprint in `render.yaml` creates the API service. In Render, provision
a PostgreSQL database and set `DATABASE_URL` to its internal connection URL. Set
`CORS_ORIGINS` to the exact Netlify site origin (for example,
`https://your-site.netlify.app`), with no path or trailing slash. To enable live AI,
set `AI_ENABLED=true` and add the selected provider's credentials in Render.

1. Push the project to a Git provider and deploy the site on Netlify from the
   repository. `netlify.toml` publishes the `frontend` directory.
2. Create a Render Blueprint from the same repository using `render.yaml`,
   provision PostgreSQL, and set `DATABASE_URL` and `CORS_ORIGINS` in the service
   environment. Use the Netlify site origin for `CORS_ORIGINS`.
3. After the Render API is healthy, copy its public service URL (the backend URL)
   into `window.LEAD_SCORING_API_URL` in `frontend/config.js`, without a trailing
   slash, then push that change so Netlify redeploys.

Keep database and AI credentials in Render's environment settings, not in frontend
files or Git. SQLite is intended for local development; use the managed PostgreSQL
database for deployed lead data. This prototype does not include authentication or
tenant isolation, so do not expose it to untrusted users or enter real customer
data without adding appropriate safeguards.

## API overview

The FastAPI application serves the UI and API on the same origin.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Basic service and AI configuration status |
| `POST` | `/qualify-lead` | Qualify a lead and persist its result |
| `GET` | `/leads` | List leads |
| `GET` | `/leads/{lead_id}` | Retrieve a lead and its qualification |
| `PUT` | `/leads/{lead_id}` | Update a lead |
| `PATCH` | `/leads/{lead_id}/status` | Update a lead's sales status (`New`, `Contacted`, `Qualified`, `Disqualified`, or `Converted`) |
| `GET` | `/leads/{lead_id}/qualification` | Retrieve qualification details |
| `GET` | `/leads/{lead_id}/qualification-history` | Retrieve prior qualification runs |
| `DELETE` | `/leads/{lead_id}` | Delete one lead |
| `DELETE` | `/leads` | Delete all leads in the configured database |

Example request:

```json
{
  "name": "Jordan Lee",
  "company": "Example Software",
  "job_title": "Operations Director",
  "country": "United States",
  "industry": "SaaS",
  "company_size": 50,
  "website": "https://example.com",
  "pain_point": "The team spends too much time qualifying inbound leads."
}
```

Use synthetic or explicitly authorized data when experimenting. The delete-all endpoint is destructive and should not be exposed to untrusted users.

## Run tests

```bash
python -m pytest -q
```

The test suite covers API behavior, qualification and scoring rules, AI fallback behavior, website research, sales action plans, caching/fingerprints, validation, and persistence.

## Configuration

See `.env.example` for supported environment variable names. The local default database is `sqlite:///./leads.db`. SQLite is convenient for development; select and validate a production database and migration strategy before a multi-user deployment.

Scoring and ICP criteria are currently configured in repository JSON files. The project does not currently provide a customer-facing scoring-rules administration workflow.

## Current limitations and production work

- No verified authentication or workspace/tenant isolation.
- No lead ownership, CRM connector, billing, or customer-facing team administration workflow.
- Qualification history covers runs recorded after this feature was added; older records have no reconstructed historical snapshots.
- Website research is best-effort and may fail, omit content, or return incomplete context.
- SQLite is the local default, not a production scale recommendation.
- AI output can be incomplete or incorrect; review results before acting on them.
- Production security, privacy, data retention, monitoring, backup/restore, and deployment readiness have not been certified.

Do not use real customer data until appropriate access controls, privacy review, and operational safeguards are in place.

## Resume summary

**Short project description:** AI-assisted B2B lead qualification application combining deterministic ICP scoring, website research, and sales recommendations.

**Resume bullet (edit to match your contribution):**

> Built an AI-assisted B2B lead qualification application with FastAPI and SQLAlchemy, combining deterministic ICP scoring, best-effort website research, explainable qualification results, and sales action plans; added API and service-level tests for scoring, fallback behavior, and persistence.

Only claim work you personally completed. Do not claim production deployment, customer adoption, conversion uplift, or commercial outcomes unless you have measured evidence.
