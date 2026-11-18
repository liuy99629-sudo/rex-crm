import json

from app.indexer import sync_index
from app.tools import TOOL_DEFINITIONS, ToolContext, run_tool


def test_tool_schemas_are_strict_and_require_every_property():
    for tool in TOOL_DEFINITIONS:
        schema = tool["input_schema"]
        assert tool["strict"] is True
        assert schema["additionalProperties"] is False
        assert sorted(schema["required"]) == sorted(schema["properties"])


async def test_semantic_search_ranks_by_meaning(crm, store, embedder):
    await sync_index(crm, store, embedder)
    ctx = ToolContext(crm, store, embedder)

    text, is_error = await run_tool(ctx, "semantic_search", {"query": "house with a pool", "kinds": ["property"]})

    hits = json.loads(text)
    assert not is_error
    assert [h["id"] for h in hits] == [1, 2]
    assert all(h["kind"] == "property" for h in hits)


async def test_filters_are_passed_to_the_crm(crm, store, embedder):
    ctx = ToolContext(crm, store, embedder)
    args = {"suburb": None, "min_price": None, "max_price": 1_000_000, "min_bedrooms": None, "status": None, "type": None}

    text, is_error = await run_tool(ctx, "search_properties", args)

    assert not is_error
    assert [p["id"] for p in json.loads(text)] == [2]
    assert crm.calls == [("search_properties", args)]


async def test_missing_deal_and_unknown_tool_are_reported_as_errors(crm, store, embedder):
    ctx = ToolContext(crm, store, embedder)

    assert (await run_tool(ctx, "get_deal", {"deal_id": 99}))[1] is True
    assert (await run_tool(ctx, "drop_tables", {}))[1] is True


async def test_tool_exceptions_are_returned_not_raised(crm, store, embedder):
    async def boom(**_):
        raise RuntimeError("db down")

    crm.search_contacts = boom
    text, is_error = await run_tool(ToolContext(crm, store, embedder), "search_contacts", {})

    assert is_error and "db down" in text
