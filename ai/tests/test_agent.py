from app.agent import MAX_MODEL_CALLS, ask, build_agent
from app.tools import ToolContext

from .conftest import Response, ScriptedLlm, text, tool_use

FILTERS = {"suburb": None, "min_price": None, "max_price": 1_000_000, "min_bedrooms": None, "status": None, "type": None}


def make(llm, crm, store, embedder):
    return build_agent(llm, ToolContext(crm, store, embedder), model="claude-opus-5-5", effort="medium")


async def test_runs_a_tool_then_answers(crm, store, embedder):
    llm = ScriptedLlm(
        Response([text("Let me check."), tool_use("tu_1", "search_properties", FILTERS)], "tool_use"),
        Response([text("City apartment (property #2) is $800,000.")], "end_turn"),
    )

    result = await ask(make(llm, crm, store, embedder), [{"role": "user", "content": "Listings under $1m?"}])

    assert result["answer"] == "City apartment (property #2) is $800,000."
    assert result["tool_calls"] == [{"tool": "search_properties", "input": FILTERS, "error": False}]
    assert result["model_calls"] == 2

    second = llm.requests[1]["messages"]
    # Assistant turn is replayed unchanged, then exactly one user message with the tool result.
    assert second[1]["content"][1] == {"type": "tool_use", "id": "tu_1", "name": "search_properties", "input": FILTERS}
    assert second[2]["role"] == "user"
    assert second[2]["content"][0]["tool_use_id"] == "tu_1"
    assert "City apartment" in second[2]["content"][0]["content"]


async def test_parallel_tool_calls_come_back_in_one_message(crm, store, embedder):
    llm = ScriptedLlm(
        Response([tool_use("a", "pipeline_summary", {}), tool_use("b", "get_deal", {"deal_id": 99})], "tool_use"),
        Response([text("Done.")], "end_turn"),
    )

    await ask(make(llm, crm, store, embedder), [{"role": "user", "content": "Status?"}])

    results = llm.requests[1]["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["a", "b"]
    assert "is_error" not in results[0] and results[1]["is_error"] is True


async def test_sends_model_effort_and_strict_tools(crm, store, embedder):
    llm = ScriptedLlm(Response([text("Hi.")], "end_turn"))

    await ask(make(llm, crm, store, embedder), [{"role": "user", "content": "Hello"}])

    req = llm.requests[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["output_config"] == {"effort": "medium"}
    assert "thinking" not in req and "tool_choice" not in req
    assert all(t["strict"] for t in req["tools"])


async def test_refusal_returns_a_polite_answer(crm, store, embedder):
    llm = ScriptedLlm(Response([], "refusal"))

    result = await ask(make(llm, crm, store, embedder), [{"role": "user", "content": "..."}])

    assert result["answer"] == "Sorry, I can't help with that request."


async def test_stops_after_the_model_call_limit(crm, store, embedder):
    llm = ScriptedLlm(*[Response([tool_use(f"t{i}", "pipeline_summary", {})], "tool_use") for i in range(MAX_MODEL_CALLS)])

    result = await ask(make(llm, crm, store, embedder), [{"role": "user", "content": "Loop forever"}])

    assert result["model_calls"] == MAX_MODEL_CALLS
    assert "too many lookups" in result["answer"]


async def test_history_must_start_with_a_user_turn(crm, store, embedder):
    llm = ScriptedLlm(Response([text("Sure.")], "end_turn"))

    await ask(
        make(llm, crm, store, embedder),
        [
            {"role": "assistant", "content": "Hi, I'm Rex."},
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "Answer"},
            {"role": "user", "content": "Follow-up"},
        ],
    )

    sent = llm.requests[0]["messages"]
    assert sent[0] == {"role": "user", "content": "First question"}
    assert sent[-1] == {"role": "user", "content": "Follow-up"}
