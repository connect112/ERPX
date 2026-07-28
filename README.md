# ERPX — Enterprise ERP + LMS + CRM + Accounting + Pentrix Platform

ERPX is a modular enterprise platform for GIR Technologies combining ERP,
LMS, CRM, Accounting, HR/Payroll, and a cybersecurity training range
("Pentrix") in a single system.

## Status

**Module 1: Foundation — complete.**

This is the infrastructure and application skeleton every other module
builds on: monorepo layout, Docker orchestration, the FastAPI backend
core (config, async DB session, JWT/password primitives, structured
logging, global exception handling, request-context middleware, Celery,
health/readiness checks, Alembic migrations), and the React frontend core
(Vite + TS + Tailwind + ShadCN tokens, TanStack Query, Axios client with
token-refresh interceptor, Zustand auth store, theming, routing with a
route guard). Both sides have been installed, type-checked, and built
successfully.

Modules are being built next in the order defined in the project spec:
Authentication → Authorization → Database → Dashboard → CRM → Students →
Courses → LMS → Examinations → Pentrix → Accounting → HR → Payroll →
Inventory → Corporate Services → Marketing → AI → Reports → Deployment →
Testing → Production Optimization.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS, ShadCN UI, React Router, TanStack Query, React Hook Form, Zod, Axios, Recharts |
| Backend | FastAPI, Python 3.12, SQLAlchemy 2 (async), Alembic, JWT + refresh tokens, Redis, Celery |
| Database | PostgreSQL 16 |
| Storage | MinIO (S3-compatible) |
| Search | Elasticsearch |
| Deployment | Docker, Docker Compose, Kubernetes-ready, Nginx, GitHub Actions |
| Monitoring | Prometheus, Grafana (wired in as the Monitoring module lands) |
| Testing | Pytest, React Testing Library, Playwright |

## Project structure

```
ERPX/
├── apps/          # web, student-portal, trainer-portal, corporate-portal, mobile-api, api (FastAPI)
├── packages/       # shared cross-module libraries (auth, permissions, notifications, storage, ...)
├── modules/        # business modules (crm, students, courses, lms, pentrix, accounting, hr, ...)
├── database/       # migrations, seeds, scripts
├── infrastructure/ # docker, kubernetes, nginx, terraform, monitoring, ci-cd
├── docs/
├── tests/
└── docker-compose.yml
```

## Getting started

1. Copy the environment template and fill in real secrets:

   ```bash
   cp .env.example .env
   ```

2. Start the full stack:

   ```bash
   make up
   ```

   This brings up Postgres, Redis, MinIO, Elasticsearch, the FastAPI API,
   Celery worker + beat, the React dev server, and Nginx.

3. Run the initial database migration:

   ```bash
   make migrate
   ```

4. Open the app:

   - Web app: http://localhost:5173 (or http://localhost via Nginx)
   - API docs (Swagger): http://localhost:8000/api/docs
   - API health: http://localhost:8000/api/v1/health
   - MinIO console: http://localhost:9001

## Running without Docker (local dev)

**Backend**

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend**

```bash
cd apps/web
npm install
npm run dev
```

## Development conventions

- Every ORM model extends `TimestampedBase` in `apps/api/app/db/base_model.py`.
- Every API error is raised as a subclass of `ERPXException`
  (`apps/api/app/core/exceptions.py`) — never a raw `HTTPException` — so
  the error envelope stays consistent across the whole API.
- Every module registers its router in `apps/api/app/api/v1/router.py`
  and its models in `apps/api/alembic/env.py` as it's built.
- Frontend components use the shared `cn()` utility
  (`apps/web/src/lib/utils.ts`) for class merging and the shared
  `apiClient` (`apps/web/src/api/client.ts`) for all HTTP calls.

## License

Proprietary — GIR Technologies. See `LICENSE`.
