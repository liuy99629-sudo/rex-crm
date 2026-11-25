# Rex CRM

**English** | [中文](README.zh-CN.md)

A CRM for real-estate agencies: **contacts** (clients), **properties** (listings) and the **sales pipeline**,
with an AI assistant, a public listings website, automatic lead intake from email, and analytics.

## Architecture

```
                       ┌──────────── Browser ────────────┐
                       │                                 │
            Agents: CRM  :8080                 Buyers: listings  :3000
                       │                                 │
             ┌─────────▼─────────┐             ┌─────────▼─────────┐
             │ web (React)       │             │ portal (Next.js)  │
             │ + nginx proxy     │             │ public website    │
             └───┬───────────┬───┘             └─────────┬─────────┘
           /api/ │           │ /api/ai/                  │ GraphQL
                 │           │                 ┌─────────▼─────────┐
                 │           │                 │ gateway (GraphQL) │
                 │           │                 └─────────┬─────────┘
                 ▼           ▼                           │ /api/public/*
       ┌──────────────┐  ┌──────────────────┐            │
       │ api (Laravel)│◄─┤ ai (Python)      │            │
       │ core business│◄─┼──────────────────┼────────────┘
       └──┬────────┬──┘  │ assistant, match,│
          │        │     │ win probability  │
          │        │     └────────┬─────────┘
          │        └─► worker (queued jobs)
          ▼                       ▼
   PostgreSQL (data + pgvector)       Redis (cache + queue)

  Into the CRM:  email lead pipeline (AWS Lambda), MCP server (Claude operates the CRM)
  Out of the CRM: PySpark analytics → Postgres / Parquet / Databricks / Snowflake
```

## Modules

| Folder | Tech | What it does |
|---|---|---|
| [`backend/`](backend/) | Laravel 11, Sanctum, PostgreSQL, Redis | Core API: contacts, properties, deals, pipeline board, dashboard; public listing and enquiry endpoints; lead integration endpoint (limited tokens) |
| [`frontend/`](frontend/) | React 19, TypeScript, Vite, TanStack Query | Agent UI: dashboard, drag-and-drop pipeline, contacts, properties, buyer matches, Ask Rex assistant, Insights |
| [`ai/`](ai/) | FastAPI, LangGraph, Claude, pgvector, PyTorch | Ask Rex agent (calls tools to query the CRM), RAG semantic search, buyer ↔ listing matching, explained deal win probability |
| [`mcp/`](mcp/) | TypeScript, MCP SDK | Lets Claude Code / Claude Desktop query and update the CRM in plain language (9 tools) |
| [`portal/`](portal/), [`gateway/`](gateway/) | Next.js 16, GraphQL Yoga | Public listings website: browse, filter, similar listings, inspection enquiries (become CRM leads) |
| [`lead-pipeline/`](lead-pipeline/) | AWS SAM, Lambda, S3, DynamoDB, SQS, Bedrock | Portal enquiry emails → extracted lead → CRM; idempotent, retried, with a dead-letter queue |
| [`analytics/`](analytics/) | PySpark, Delta, Databricks, Snowflake | Nightly marts: deal facts, suburb market, lead-source funnel, agent performance, stage velocity |
| [`k8s/`](k8s/) | Kubernetes, kustomize | GKE manifests |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | GitHub Actions | Tests and builds for every module → push images → deploy to GKE and the AWS lead pipeline |

More detail: [ai](ai/README.md), [mcp](mcp/README.md), [portal + gateway](portal/README.md), [lead-pipeline](lead-pipeline/README.md), [analytics](analytics/README.md).

## Quick start (needs Docker Desktop)

> Setting up a new computer from scratch (tools, line endings, `.env`, modules, cloud sign-in):
> see [SETUP-ON-NEW-PC.md](SETUP-ON-NEW-PC.md) (in Chinese).

```bash
docker compose up --build -d                    # first build takes 10–20 minutes
docker compose exec api php artisan db:seed     # load demo data
```

| URL | What |
|---|---|
| http://localhost:8080 | CRM, sign in as `admin@rexcrm.test` / `password` |
| http://localhost:3000 | Public listings website |
| http://localhost:4000/graphql | GraphQL gateway |
| http://localhost:8000/api/health | Laravel API |
| http://localhost:8001/api/ai/health | AI service |

- The Ask Rex assistant needs `ANTHROPIC_API_KEY` in `.env` (billed per use). Matching and win probability do not.
- VS Code: `Ctrl+Shift+P` → `Tasks: Run Task` has up / down / seed / test tasks.
- Frontend only: `cd frontend && npm install && npm run dev` (http://localhost:5173, proxies `/api` to `localhost:8000`).

Optional services:

```bash
docker compose --profile aws up -d                     # local email lead pipeline (LocalStack for S3 + DynamoDB)
docker compose --profile analytics run --rm analytics  # PySpark analytics, shown on the Insights page
```

## Tests

```bash
docker compose --profile test run --rm test                 # backend
docker compose --profile test run --rm ai-test              # AI service
docker compose --profile test run --rm lead-pipeline-test   # email lead pipeline
docker compose --profile test run --rm analytics-test       # analytics
cd frontend && npm test     # same for gateway, portal, mcp
```

## API overview

Everything is under `/api`. All routes except login, health and `/public/*` need `Authorization: Bearer <token>`.

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/login` | Sign in, returns a token |
| GET / POST | `/auth/me`, `/auth/logout` | Current user / sign out |
| CRUD | `/contacts`, `/properties`, `/deals` | Contacts, properties, deals (search and filters) |
| PATCH | `/deals/{id}/stage` | Change stage (saved immediately; history recorded by a queued job) |
| POST / DELETE | `/deals/{id}/notes` | Add / delete a note |
| GET | `/pipeline`, `/dashboard` | Board and dashboard (cached in Redis, flushed when deals change) |
| GET | `/insights` | Analytics marts |
| GET | `/public/listings`, `/public/listings/{id}` | Public listings (no sign-in, rate limited) |
| POST | `/public/enquiries` | Website inspection enquiry |
| POST | `/integrations/leads` | External leads (limited token with `leads:write`) |
| * | `/ai/*` | AI service: `ask`, `matches/...`, `deals/win-probability` |

Deal stages: `lead → contacted → inspection → offer → negotiation → won / lost`.

## Deployment

- **Cloud (free tiers)**: the AWS lead pipeline, Databricks and Snowflake are deployed. What runs where and how to remove it: [docs/CLOUD-DEPLOY.md](docs/CLOUD-DEPLOY.md).
- **GKE**: manifests in [`k8s/`](k8s/); one-time GCP setup in [docs/ai-workflow.md](docs/ai-workflow.md). Not deployed, because it would be billed.
- **Claude API / Bedrock**: billed per use, off by default.

## How we work

Conventions are in [CLAUDE.md](CLAUDE.md) and the workflow in [docs/ai-workflow.md](docs/ai-workflow.md). Work on a branch, open a PR, and a human merges once CI passes. Never push to `main`.

## Known limitations

- No role-based permissions yet: every signed-in user can see and change all data (`users.role` is reserved for this).
- Listing photo uploads and email / SMS reminders are not built yet.
