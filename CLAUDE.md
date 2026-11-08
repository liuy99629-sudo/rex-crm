# Rex CRM: guide for AI coding agents

Real-estate CRM: contacts (clients), properties (listings), deals (sales pipeline).
Stack: Laravel 11 API (`backend/`), React + TypeScript + Vite (`frontend/`), PostgreSQL, Redis (cache + queue), Docker, GKE.

## Commands
- Whole stack: `docker compose up --build` (web http://localhost:8080, API http://localhost:8000)
- Seed demo data: `docker compose exec api php artisan db:seed` (login `admin@rexcrm.test` / `password`)
- Backend tests: `cd backend && composer install && php artisan test` (SQLite in memory, no services needed)
- Frontend: `cd frontend && npm ci && npm run dev` / `npm test` / `npm run build` (build also type-checks)

## Conventions
- API lives under `/api`, token auth with Sanctum (`Authorization: Bearer ...`). Controllers in `app/Http/Controllers/Api`, output shaped by `app/Http/Resources`.
- Fixed vocabularies (deal stages, contact/property types, property status) are PHP enums in `app/Enums` and mirrored in `frontend/src/api/types.ts`. Change both together.
- Slow or side-effect work goes into a queued job (`app/Jobs`), not the request. Example: `RecordDealStageChange`.
- Pipeline board and dashboard numbers are cached in Redis by `PipelineService`; `Deal` model events flush it. If you add a write path that changes deals, make sure it goes through Eloquent so the cache is flushed.
- Write a feature test for every new endpoint (`backend/tests/Feature`). Keep queries portable between PostgreSQL and SQLite (no `ILIKE`).
- Frontend: server state via TanStack Query, no global store. API calls only through `src/api`. Money is whole AUD dollars (integers).
- Migrations must be backwards compatible: a rolling deploy runs old and new code together.

## Workflow
1. Work on a branch, open a PR using the template. Never push to `main`.
2. CI (`.github/workflows/ci.yml`) must pass: backend tests, frontend tests + build.
3. A human reviews and merges. Merging to `main` builds images and deploys to GKE.

## Never
- Commit secrets or `.env` files. Production secrets live in the `rex-crm-secrets` Kubernetes Secret.
- Edit old migrations that have been merged: add a new one.
