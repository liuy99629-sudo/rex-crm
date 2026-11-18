"""Read-only access to the CRM tables owned by Laravel.

The assistant never writes here: writes must go through the Laravel API so model events
flush the pipeline cache and queued jobs run (see CLAUDE.md)."""

import hashlib
from typing import Any, Protocol

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .store import Document

OPEN_STAGES = ("lead", "contacted", "inspection", "offer", "negotiation")
MAX_ROWS = 25


class CrmRepository(Protocol):
    async def documents(self) -> list[Document]: ...
    async def search_properties(self, **filters: Any) -> list[dict[str, Any]]: ...
    async def search_contacts(self, **filters: Any) -> list[dict[str, Any]]: ...
    async def get_deal(self, deal_id: int) -> dict[str, Any] | None: ...
    async def pipeline_summary(self) -> list[dict[str, Any]]: ...


def make_document(kind: str, source_id: int, title: str, text: str) -> Document:
    digest = hashlib.sha256(f"{title}\n{text}".encode()).hexdigest()
    return Document(kind, source_id, title, text, digest)


def _money(v: int | None) -> str:
    return f"${v:,}" if v is not None else "n/a"


class PgCrmRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def _all(self, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql, params)
                return await cur.fetchall()

    async def documents(self) -> list[Document]:
        docs: list[Document] = []
        for p in await self._all(
            "SELECT id, title, type, status, suburb, state, postcode, price, bedrooms, bathrooms, parking, description "
            "FROM properties"
        ):
            text = (
                f"{p['type']} in {p['suburb']} {p['state']} {p['postcode']}. "
                f"{p['bedrooms']} bed, {p['bathrooms']} bath, {p['parking']} car. "
                f"Status {p['status']}, price {_money(p['price'])}. {p['description'] or ''}"
            )
            docs.append(make_document("property", p["id"], p["title"], text))

        for c in await self._all("SELECT id, name, type, source, budget_min, budget_max, notes FROM contacts"):
            text = (
                f"{c['type']} contact. Budget {_money(c['budget_min'])} to {_money(c['budget_max'])}. "
                f"Lead source: {c['source'] or 'n/a'}. Notes: {c['notes'] or 'none'}"
            )
            docs.append(make_document("contact", c["id"], c["name"], text))

        notes: dict[int, list[str]] = {}
        for a in await self._all(
            "SELECT deal_id, body FROM deal_activities WHERE type = 'note' AND body IS NOT NULL ORDER BY created_at"
        ):
            notes.setdefault(a["deal_id"], []).append(a["body"])
        for d in await self._all("SELECT id, title, stage, value, notes FROM deals"):
            parts = [f"Stage {d['stage']}, value {_money(d['value'])}.", d["notes"] or "", *notes.get(d["id"], [])]
            docs.append(make_document("deal", d["id"], d["title"], " ".join(p for p in parts if p)))
        return docs

    async def search_properties(
        self,
        suburb: str | None = None,
        max_price: int | None = None,
        min_price: int | None = None,
        min_bedrooms: int | None = None,
        status: str | None = None,
        type: str | None = None,
    ) -> list[dict[str, Any]]:
        where, params = ["TRUE"], []
        if suburb:
            where.append("LOWER(suburb) = LOWER(%s)")
            params.append(suburb)
        if max_price is not None:
            where.append("price <= %s")
            params.append(max_price)
        if min_price is not None:
            where.append("price >= %s")
            params.append(min_price)
        if min_bedrooms is not None:
            where.append("bedrooms >= %s")
            params.append(min_bedrooms)
        if status:
            where.append("status = %s")
            params.append(status)
        if type:
            where.append("type = %s")
            params.append(type)
        return await self._all(
            "SELECT id, title, address_line, suburb, type, status, price, bedrooms, bathrooms, parking "
            f"FROM properties WHERE {' AND '.join(where)} ORDER BY price NULLS LAST LIMIT {MAX_ROWS}",
            params,
        )

    async def search_contacts(
        self,
        name: str | None = None,
        type: str | None = None,
        can_afford: int | None = None,
    ) -> list[dict[str, Any]]:
        where, params = ["TRUE"], []
        if name:
            where.append("LOWER(name) LIKE %s")
            params.append(f"%{name.lower()}%")
        if type:
            where.append("type = %s")
            params.append(type)
        if can_afford is not None:
            # Budget range covers the price (open-ended ranges count as covering).
            where.append("(budget_max IS NULL OR budget_max >= %s) AND (budget_min IS NULL OR budget_min <= %s)")
            params += [can_afford, can_afford]
        return await self._all(
            "SELECT id, name, type, email, phone, budget_min, budget_max, source "
            f"FROM contacts WHERE {' AND '.join(where)} ORDER BY name LIMIT {MAX_ROWS}",
            params,
        )

    async def get_deal(self, deal_id: int) -> dict[str, Any] | None:
        rows = await self._all(
            "SELECT d.id, d.title, d.stage, d.value, d.expected_close_date, d.closed_at, d.notes, "
            "c.name AS contact_name, p.title AS property_title, p.suburb AS property_suburb, u.name AS agent_name "
            "FROM deals d JOIN contacts c ON c.id = d.contact_id "
            "LEFT JOIN properties p ON p.id = d.property_id LEFT JOIN users u ON u.id = d.user_id "
            "WHERE d.id = %s",
            [deal_id],
        )
        if not rows:
            return None
        deal = rows[0]
        deal["activities"] = await self._all(
            "SELECT type, body, created_at FROM deal_activities WHERE deal_id = %s ORDER BY created_at DESC LIMIT 10",
            [deal_id],
        )
        return deal

    async def pipeline_summary(self) -> list[dict[str, Any]]:
        return await self._all(
            "SELECT stage, COUNT(*) AS deals, COALESCE(SUM(value), 0) AS total_value FROM deals GROUP BY stage ORDER BY stage"
        )
