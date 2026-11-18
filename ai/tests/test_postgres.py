"""Integration tests against a real PostgreSQL with pgvector (CI starts one; locally:
TEST_DATABASE_URL=postgresql://... pytest). Skipped when TEST_DATABASE_URL is not set.

The CRM tables are created here with only the columns this service reads, matching
backend/database/migrations."""

import os

import pytest
from psycopg_pool import AsyncConnectionPool

from app.crm import PgCrmRepository
from app.embeddings import HashEmbedder
from app.indexer import sync_index
from app.store import PgVectorStore

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")

SCHEMA = """
DROP TABLE IF EXISTS ai_documents, deal_activities, deals, properties, contacts, users CASCADE;
CREATE TABLE users (id bigserial PRIMARY KEY, name text NOT NULL);
CREATE TABLE contacts (id bigserial PRIMARY KEY, name text NOT NULL, email text, phone text, type text NOT NULL,
  source text, budget_min bigint, budget_max bigint, notes text, created_at timestamp DEFAULT now());
CREATE TABLE properties (id bigserial PRIMARY KEY, title text NOT NULL, address_line text NOT NULL, suburb text NOT NULL,
  state text NOT NULL, postcode text NOT NULL, type text NOT NULL, status text NOT NULL, price bigint,
  bedrooms int, bathrooms int, parking int, description text);
CREATE TABLE deals (id bigserial PRIMARY KEY, title text NOT NULL, contact_id bigint NOT NULL REFERENCES contacts,
  property_id bigint REFERENCES properties, user_id bigint REFERENCES users, stage text NOT NULL, value bigint NOT NULL,
  expected_close_date date, closed_at timestamp, notes text);
CREATE TABLE deal_activities (id bigserial PRIMARY KEY, deal_id bigint NOT NULL REFERENCES deals, type text NOT NULL,
  body text, created_at timestamp DEFAULT now());
INSERT INTO users (name) VALUES ('Demo Agent');
INSERT INTO contacts (name, type, budget_min, budget_max, notes) VALUES
  ('Jane Buyer', 'buyer', 900000, 1600000, 'Wants a pool for the kids'),
  ('Open Budget', 'investor', NULL, NULL, NULL),
  ('Small Budget', 'buyer', 300000, 500000, NULL);
INSERT INTO properties (title, address_line, suburb, state, postcode, type, status, price, bedrooms, bathrooms, parking, description)
VALUES ('Family home in Burwood', '1 Park Ave', 'Burwood', 'NSW', '2134', 'house', 'active', 1500000, 4, 2, 2, 'Pool and big yard'),
       ('City apartment', '2 George St', 'Sydney', 'NSW', '2000', 'apartment', 'active', 800000, 2, 1, 1, 'Near the station');
INSERT INTO deals (title, contact_id, property_id, user_id, stage, value) VALUES ('Purchase - Jane', 1, 1, 1, 'offer', 1450000);
INSERT INTO deal_activities (deal_id, type, body) VALUES (1, 'note', 'Finance approval pending'), (1, 'stage_change', 'Lead to Offer');
"""


@pytest.fixture
async def pool():
    async with AsyncConnectionPool(URL, min_size=1, max_size=2) as p:
        async with p.connection() as conn:
            await conn.execute(SCHEMA)
        yield p


async def test_crm_queries(pool):
    crm = PgCrmRepository(pool)

    burwood = await crm.search_properties(suburb="burwood", max_price=2_000_000)
    assert [p["title"] for p in burwood] == ["Family home in Burwood"]

    affordable = await crm.search_contacts(can_afford=1_500_000)
    assert sorted(c["name"] for c in affordable) == ["Jane Buyer", "Open Budget"]

    deal = await crm.get_deal(1)
    assert deal["contact_name"] == "Jane Buyer" and deal["agent_name"] == "Demo Agent"
    assert sorted(a["type"] for a in deal["activities"]) == ["note", "stage_change"]

    assert await crm.get_deal(999) is None
    assert await crm.pipeline_summary() == [{"stage": "offer", "deals": 1, "total_value": 1450000}]


async def test_index_and_vector_search(pool):
    embedder = HashEmbedder()
    store = PgVectorStore(pool, embedder.dimensions)
    await store.setup()
    crm = PgCrmRepository(pool)

    stats = await sync_index(crm, store, embedder)
    assert stats.embedded == 6  # 2 properties + 3 contacts + 1 deal

    deal_doc = next(d for d in await crm.documents() if d.kind == "deal")
    assert "Finance approval pending" in deal_doc.text and "Lead to Offer" not in deal_doc.text

    [query] = embedder.embed(["finance approval pending"])
    hits = await store.search(query, limit=3, kinds=["deal"])
    assert hits[0].source_id == 1 and hits[0].kind == "deal"

    async with pool.connection() as conn:
        await conn.execute("DELETE FROM contacts WHERE name = 'Small Budget'")
    stats = await sync_index(crm, store, embedder)
    assert (stats.embedded, stats.deleted) == (0, 1)
