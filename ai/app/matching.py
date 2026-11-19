"""Buyer ↔ listing matching.

Score = 0.55 × budget fit + 0.45 × semantic fit, where semantic fit compares the buyer's notes
("needs a pool, good schools near Epping") with the listing description using the RAG embeddings
already stored in pgvector. Every match comes with plain-English reasons an agent can check."""

from dataclasses import asdict, dataclass, field
from typing import Any

from .crm import CrmRepository
from .store import VectorStore, _cosine

BUDGET_WEIGHT = 0.55
SEMANTIC_WEIGHT = 0.45
STRETCH = 0.10  # up to 10% over budget is a "stretch", beyond that is not a match


def _aud(v: int | None) -> str:
    return f"${v:,}" if v is not None else "n/a"


def budget_fit(price: int | None, low: int | None, high: int | None) -> tuple[float | None, str]:
    """(score 0..1 or None when clearly unaffordable, reason)."""
    if price is None:
        return 0.5, "Listing has no price yet"
    if low is None and high is None:
        return 0.5, "No budget recorded for this client"
    if high is not None and price > high * (1 + STRETCH):
        return None, f"{_aud(price)} is well over the {_aud(high)} budget"
    if high is not None and price > high:
        return 0.4, f"{_aud(price)} is a stretch: {round((price / high - 1) * 100)}% over the {_aud(high)} budget"
    if low is not None and price < low * 0.7:
        return 0.3, f"{_aud(price)} is far below the {_aud(low)} minimum; may not suit"
    if low is not None and price < low:
        return 0.7, f"{_aud(price)} is under the {_aud(low)} minimum: room to spare"
    return 1.0, f"{_aud(price)} is within the {_aud(low)}–{_aud(high)} budget"


def semantic_fit(similarity: float) -> float:
    """Map raw cosine similarity (MiniLM: unrelated ≈ 0.1, close ≈ 0.6) to 0..1."""
    return max(0.0, min(1.0, (similarity - 0.15) / 0.45))


@dataclass
class Match:
    id: int
    name: str
    score: float  # 0..100
    budget_score: float
    semantic_score: float
    reasons: list[str] = field(default_factory=list)
    existing_deal: dict[str, Any] | None = None
    detail: dict[str, Any] = field(default_factory=dict)


def _snippet(text: str | None, limit: int = 140) -> str | None:
    """The client's own words, cut at a word boundary."""
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _semantic_reason(similarity: float, about: str | None) -> str | None:
    fit = semantic_fit(similarity)
    if fit >= 0.6 and about:
        return f"Strong fit with what they want: \"{about}\""
    if fit >= 0.3 and about:
        return f"Partly matches: \"{about}\""
    return None


async def buyers_for_property(crm: CrmRepository, store: VectorStore, property_id: int, limit: int = 5) -> dict[str, Any] | None:
    prop = await crm.get_property(property_id)
    if prop is None:
        return None
    prop_vec = await store.vector("property", property_id)
    matches: list[Match] = []
    for c in await crm.buyer_candidates():
        fit, budget_reason = budget_fit(prop["price"], c["budget_min"], c["budget_max"])
        if fit is None:
            continue
        contact_vec = await store.vector("contact", c["id"])
        similarity = _cosine(prop_vec, contact_vec) if prop_vec and contact_vec else 0.0
        sem = semantic_fit(similarity)
        deals = [d for d in c["deals"] if d["property_id"] == property_id]
        existing = deals[0] if deals else None
        if existing and existing["stage"] == "lost":
            continue  # they already passed on it
        reasons = [budget_reason]
        if r := _semantic_reason(similarity, _snippet(c["notes"])):
            reasons.append(r)
        if existing:
            reasons.append(f"Already in deal #{existing['deal_id']} ({existing['stage']})")
        matches.append(
            Match(c["id"], c["name"], round(100 * (BUDGET_WEIGHT * fit + SEMANTIC_WEIGHT * sem), 1), fit, round(sem, 3),
                  reasons, existing, {"type": c["type"], "budget_min": c["budget_min"], "budget_max": c["budget_max"]})
        )
    matches.sort(key=lambda m: m.score, reverse=True)
    return {"property": prop, "matches": [asdict(m) for m in matches[:limit]]}


async def properties_for_contact(crm: CrmRepository, store: VectorStore, contact_id: int, limit: int = 5) -> dict[str, Any] | None:
    contact = await crm.get_contact(contact_id)
    if contact is None:
        return None
    contact_vec = await store.vector("contact", contact_id)
    candidate = next((c for c in await crm.buyer_candidates() if c["id"] == contact_id), None)
    deals = {d["property_id"]: d for d in (candidate or {"deals": []})["deals"] if d["property_id"]}
    matches: list[Match] = []
    for p in await crm.listing_candidates():
        fit, budget_reason = budget_fit(p["price"], contact["budget_min"], contact["budget_max"])
        existing = deals.get(p["id"])
        if fit is None or (existing and existing["stage"] == "lost"):
            continue
        prop_vec = await store.vector("property", p["id"])
        similarity = _cosine(prop_vec, contact_vec) if prop_vec and contact_vec else 0.0
        sem = semantic_fit(similarity)
        reasons = [budget_reason]
        if sem >= 0.3:
            reasons.append(f"{'Strong' if sem >= 0.6 else 'Partial'} fit with their notes")
        if p["status"] != "active":
            reasons.append("Coming soon" if p["status"] == "draft" else "Under offer")
        if existing:
            reasons.append(f"Already in deal #{existing['deal_id']} ({existing['stage']})")
        matches.append(
            Match(p["id"], p["title"], round(100 * (BUDGET_WEIGHT * fit + SEMANTIC_WEIGHT * sem), 1), fit, round(sem, 3),
                  reasons, existing, {"suburb": p["suburb"], "price": p["price"], "status": p["status"], "type": p["type"]})
        )
    matches.sort(key=lambda m: m.score, reverse=True)
    return {"contact": {k: contact[k] for k in ("id", "name", "type", "budget_min", "budget_max")}, "matches": [asdict(m) for m in matches[:limit]]}
