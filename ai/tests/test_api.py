from fastapi.testclient import TestClient

from app.main import Services, create_app

from .conftest import Response, ScriptedLlm, text

GOOD = {"Authorization": "Bearer good-token"}


async def verify(token: str):
    return {"id": 1, "name": "Demo Admin"} if token == "good-token" else None


def client(crm, store, embedder, llm=None) -> TestClient:
    services = Services(
        crm=crm, store=store, embedder=embedder, verify_token=verify, llm=llm, model="claude-opus-5-5", effort="medium"
    )
    return TestClient(create_app(services))


def test_health_is_public_and_reports_llm_status(crm, store, embedder):
    assert client(crm, store, embedder).get("/api/ai/health").json() == {"status": "ok", "llm_configured": False}


def test_ask_requires_a_valid_token(crm, store, embedder):
    c = client(crm, store, embedder, ScriptedLlm())
    body = {"messages": [{"role": "user", "content": "hi"}]}

    assert c.post("/api/ai/ask", json=body).status_code == 401
    assert c.post("/api/ai/ask", json=body, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_unreachable_laravel_is_503_not_401(crm, store, embedder):
    # A 401 makes the frontend log the user out; an outage of the token check must not do that.
    async def down(_: str):
        raise ConnectionError("api:8080 refused")

    services = Services(
        crm=crm, store=store, embedder=embedder, verify_token=down, llm=ScriptedLlm(), model="m", effort="medium"
    )
    r = TestClient(create_app(services)).post("/api/ai/ask", json={"messages": [{"role": "user", "content": "hi"}]}, headers=GOOD)

    assert r.status_code == 503


def test_ask_without_api_key_explains_how_to_configure(crm, store, embedder):
    r = client(crm, store, embedder).post("/api/ai/ask", json={"messages": [{"role": "user", "content": "hi"}]}, headers=GOOD)

    assert r.status_code == 503
    assert "ANTHROPIC_API_KEY" in r.json()["message"]


def test_ask_returns_the_answer(crm, store, embedder):
    llm = ScriptedLlm(Response([text("You have 3 leads.")], "end_turn"))
    r = client(crm, store, embedder, llm).post(
        "/api/ai/ask", json={"messages": [{"role": "user", "content": "How many leads?"}]}, headers=GOOD
    )

    assert r.status_code == 200
    assert r.json() == {"answer": "You have 3 leads.", "tool_calls": [], "model_calls": 1}


def test_ask_validates_the_conversation(crm, store, embedder):
    c = client(crm, store, embedder, ScriptedLlm())

    assert c.post("/api/ai/ask", json={"messages": []}, headers=GOOD).status_code == 422
    last_not_user = {"messages": [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]}
    assert c.post("/api/ai/ask", json=last_not_user, headers=GOOD).status_code == 422


def test_matches_404_for_unknown_records(crm, store, embedder):
    c = client(crm, store, embedder)

    assert c.get("/api/ai/matches/properties/99", headers=GOOD).status_code == 404
    assert c.get("/api/ai/matches/contacts/99", headers=GOOD).status_code == 404
    assert c.get("/api/ai/matches/properties/99").status_code == 401


def test_win_probability_scores_open_deals(crm, store, embedder):
    from datetime import datetime, timedelta

    now = datetime.now()
    crm.deals = [
        {"id": 1, "stage": "offer", "value": 1_000_000, "created_at": now - timedelta(days=10), "last_activity_at": now,
         "note_count": 2, "expected_close_date": None, "closed_at": None, "property_price": 1_000_000,
         "budget_min": None, "budget_max": None, "last_open_stage": None},
        {"id": 2, "stage": "won", "value": 1, "created_at": now, "last_activity_at": None, "note_count": 0,
         "expected_close_date": None, "closed_at": now, "property_price": None, "budget_min": None, "budget_max": None,
         "last_open_stage": None},
    ]
    body = client(crm, store, embedder).get("/api/ai/deals/win-probability", headers=GOOD).json()

    assert body["model"]["trained_on"] == {"simulated": 4000, "real_closed_deals": 0}
    assert [d["deal_id"] for d in body["deals"]] == [1]


def test_reindex_syncs_the_store(crm, store, embedder):
    r = client(crm, store, embedder).post("/api/ai/reindex", headers=GOOD)

    assert r.json() == {"embedded": 3, "deleted": 0, "unchanged": 0}
    assert len(store.rows) == 3
