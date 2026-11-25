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

## Buyer ↔ listing matching

`GET /api/ai/matches/properties/{id}` (buyers for a listing) and `GET /api/ai/matches/contacts/{id}`
(listings for a buyer or investor). Score out of 100 = 55% budget fit + 45% semantic fit:

- **Budget fit**: within budget 1.0, up to 10% over 0.4 ("stretch"), more than 10% over is excluded,
  a little under the minimum 0.7, far under 0.3, unknown 0.5.
- **Semantic fit**: cosine similarity between the client's notes and the listing description, using
  the embeddings already in pgvector (no extra model calls).
- Clients who already lost a deal on the listing are left out; open deals are flagged.
- Every match lists its reasons. The agent can also call it (tools `match_buyers_for_property`,
  `match_listings_for_contact`).

## Win probability (PyTorch)

`GET /api/ai/deals/win-probability` scores every open deal. The model is a logistic regression
(`torch.nn.Linear` + BCE) on 8 features: stage, days open, days since last activity, notes, days past
expected close, budget fit, gap to asking price, and whether a listing is linked. Each score comes with
the three features that move it most, e.g. "No activity for 31 days".

Training data:
1. A **simulated prior** (`scoring.simulate`) built from stated assumptions (`PRIOR_LOGIT`), so the
   model works before the agency has history. These are assumptions, not measured facts.
2. **Real closed deals**, weighted 20×. Each one is rebuilt as it stood when it closed, using the stage
   it left from the CRM's logged stage changes. Deals closed without a logged stage change are skipped.

The model retrains automatically when the number of real closed deals changes. Training takes well under a second.

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
