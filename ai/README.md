# Rex AI service ("Ask Rex")

Python service that answers agents' questions about the CRM in plain English.

```
Browser ── /api/ai/* ──► FastAPI ──► LangGraph agent ──► Claude (Anthropic API, tool use)
                              │            │
                              │            └─ tools ──► PostgreSQL: SQL filters (read-only)
                              │                     └─► pgvector: semantic search (RAG)
                              └─ every 5 min: re-index CRM text → sentence-transformers (PyTorch, CPU) → pgvector
```

- **Auth**: reuses the CRM login. Each request's Sanctum token is checked against Laravel `GET /api/auth/me`.
- **Read-only**: the assistant never writes CRM tables. Writes belong to Laravel (cache flush, queued jobs).
- **RAG index**: table `ai_documents` (owned by this service) holds one row per property, contact and deal.
  Content hashes mean only changed records are re-embedded; deleted records are dropped.
- **Agent**: a LangGraph graph `agent → tools → agent …` with up to 8 model calls per question.
  Claude is called with the official `anthropic` SDK (default model `claude-opus-5-5`, effort `medium`),
  strict tool schemas, prompt caching and server-side refusal fallback.
- **Data sent to Claude**: the question, the conversation so far, and the CRM rows the tools return
  (names, budgets, prices, notes). Embeddings are computed locally and never leave the cluster.

## Run

```bash
docker compose up --build -d          # from the repo root; ai is on http://localhost:8001
```

Put `ANTHROPIC_API_KEY=...` in a root `.env` file (see `.env.example`). It is a Claude API key from
platform.claude.com, billed per use; a Claude.ai subscription does not cover API calls. Without a key
`POST /api/ai/ask` answers 503 and the rest of the CRM is unaffected.

API docs: http://localhost:8001/api/ai/docs

## Test

```bash
docker compose --profile test run --rm ai-test   # needs no API key: Claude, CRM and embeddings are faked,
                                                 # plus SQL + vector tests on a throwaway pgvector database
```

## Configuration

| Variable | Default | |
|---|---|---|
| `ANTHROPIC_API_KEY` | (none) | Enables `/api/ai/ask` |
| `AI_MODEL` | `claude-opus-5-5` | |
| `AI_EFFORT` | `medium` | `low` … `max` |
| `DATABASE_URL` | compose Postgres | needs the `vector` extension |
| `LARAVEL_URL` | `http://api:8080` | for token checks |
| `REINDEX_INTERVAL` | `300` | seconds, `0` disables |
