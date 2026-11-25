"""Tools the assistant can call. All read-only. Schemas are strict so inputs always validate."""

import asyncio
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from .crm import CrmRepository
from .embeddings import Embedder
from .matching import buyers_for_property, properties_for_contact
from .store import VectorStore

# Mirrors backend/app/Enums (keep in sync, like frontend/src/api/types.ts).
CONTACT_TYPES = ["buyer", "seller", "investor", "tenant", "landlord"]
PROPERTY_TYPES = ["house", "apartment", "townhouse", "land", "commercial"]
PROPERTY_STATUSES = ["draft", "active", "under_offer", "sold", "withdrawn"]


def _nullable(schema: dict[str, Any], description: str | None = None) -> dict[str, Any]:
    """Optional filter: strict mode wants every property required, so 'not set' is null."""
    out: dict[str, Any] = {"anyOf": [schema, {"type": "null"}]}
    if description:
        out["description"] = description
    return out


def _tool(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
    }


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    _tool(
        "semantic_search",
        "Search CRM records by meaning: property descriptions, contact notes and deal notes. "
        "Use for fuzzy questions (e.g. 'buyers who want a pool', 'deals where finance is a worry').",
        {
            "query": {"type": "string", "description": "What to look for, in plain words."},
            "kinds": _nullable(
                {"type": "array", "items": {"type": "string", "enum": ["property", "contact", "deal"]}},
                "Limit to these record kinds, or null for all.",
            ),
        },
    ),
    _tool(
        "search_properties",
        "Filter listings by exact criteria. Prices are whole AUD dollars. Null means no filter.",
        {
            "suburb": _nullable({"type": "string"}),
            "min_price": _nullable({"type": "integer"}),
            "max_price": _nullable({"type": "integer"}),
            "min_bedrooms": _nullable({"type": "integer"}),
            "status": _nullable({"type": "string", "enum": PROPERTY_STATUSES}),
            "type": _nullable({"type": "string", "enum": PROPERTY_TYPES}),
        },
    ),
    _tool(
        "search_contacts",
        "Filter contacts. can_afford returns contacts whose budget range covers that price (AUD).",
        {
            "name": _nullable({"type": "string"}),
            "type": _nullable({"type": "string", "enum": CONTACT_TYPES}),
            "can_afford": _nullable({"type": "integer"}),
        },
    ),
    _tool(
        "get_deal",
        "Full detail of one deal: stage, value, contact, property, agent and the latest activity.",
        {"deal_id": {"type": "integer"}},
    ),
    _tool("pipeline_summary", "Number of deals and total value per pipeline stage.", {}),
    _tool(
        "match_buyers_for_property",
        "Rank buyers and investors for a listing by budget fit and how well their notes match the description. "
        "Use for 'who should I call about property X'. Each match includes the reasons.",
        {"property_id": {"type": "integer"}},
    ),
    _tool(
        "match_listings_for_contact",
        "Rank active and coming-soon listings for a buyer or investor by budget fit and how well they match the "
        "client's notes. Each match includes the reasons.",
        {"contact_id": {"type": "integer"}},
    ),
]


@dataclass
class ToolContext:
    crm: CrmRepository
    store: VectorStore
    embedder: Embedder


def _json(value: Any) -> str:
    def default(o: Any) -> Any:
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        if isinstance(o, Decimal):
            return int(o) if o == o.to_integral_value() else float(o)
        raise TypeError(type(o).__name__)

    return json.dumps(value, default=default, ensure_ascii=False)


async def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> tuple[str, bool]:
    """Returns (result text, is_error). Errors go back to the model instead of failing the request."""
    try:
        if name == "semantic_search":
            [vector] = await asyncio.to_thread(ctx.embedder.embed, [args["query"]])
            hits = await ctx.store.search(vector, limit=8, kinds=args.get("kinds"))
            return _json(
                [
                    {"kind": h.kind, "id": h.source_id, "title": h.title, "text": h.text[:600], "score": round(h.score, 3)}
                    for h in hits
                ]
            ), False
        if name == "search_properties":
            return _json(await ctx.crm.search_properties(**args)), False
        if name == "search_contacts":
            return _json(await ctx.crm.search_contacts(**args)), False
        if name == "get_deal":
            deal = await ctx.crm.get_deal(int(args["deal_id"]))
            return (_json(deal), False) if deal else (f"No deal with id {args['deal_id']}.", True)
        if name == "pipeline_summary":
            return _json(await ctx.crm.pipeline_summary()), False
        if name == "match_buyers_for_property":
            found = await buyers_for_property(ctx.crm, ctx.store, int(args["property_id"]))
            return (_json(found), False) if found else (f"No property with id {args['property_id']}.", True)
        if name == "match_listings_for_contact":
            found = await properties_for_contact(ctx.crm, ctx.store, int(args["contact_id"]))
            return (_json(found), False) if found else (f"No contact with id {args['contact_id']}.", True)
        return f"Unknown tool: {name}", True
    except Exception as exc:  # noqa: BLE001 - report any tool failure to the model
        return f"Tool {name} failed: {type(exc).__name__}: {exc}", True
