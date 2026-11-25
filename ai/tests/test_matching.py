import pytest

from app.crm import make_document
from app.indexer import sync_index
from app.matching import budget_fit, buyers_for_property, properties_for_contact

from .conftest import FakeCrm


@pytest.mark.parametrize(
    ("price", "low", "high", "score"),
    [
        (1_000_000, 900_000, 1_200_000, 1.0),  # within
        (1_250_000, 900_000, 1_200_000, 0.4),  # stretch (<= 10% over)
        (1_400_000, 900_000, 1_200_000, None),  # well over: not a match
        (850_000, 900_000, 1_200_000, 0.7),  # a bit under the minimum
        (500_000, 900_000, 1_200_000, 0.3),  # far under
        (1_000_000, None, None, 0.5),  # no budget recorded
        (None, 900_000, 1_200_000, 0.5),  # no price
    ],
)
def test_budget_fit(price, low, high, score):
    assert budget_fit(price, low, high)[0] == score


def buyer(id_, name, low, high, notes, deals=()):
    return {"id": id_, "name": name, "type": "buyer", "budget_min": low, "budget_max": high, "notes": notes, "deals": list(deals)}


@pytest.fixture
async def market(store, embedder):
    crm = FakeCrm(
        listings=[
            {"id": 1, "title": "Family home with pool", "suburb": "Epping", "type": "house", "status": "active", "price": 1_800_000, "bedrooms": 4},
            {"id": 2, "title": "City studio", "suburb": "Sydney", "type": "apartment", "status": "active", "price": 700_000, "bedrooms": 1},
            {"id": 3, "title": "Sold cottage", "suburb": "Epping", "type": "house", "status": "sold", "price": 1_700_000, "bedrooms": 3},
        ],
        buyers=[
            buyer(10, "Pool family", 1_600_000, 1_900_000, "Family needs a pool and good schools near Epping."),
            buyer(11, "Budget fits, no pool", 1_600_000, 1_900_000, "Wants a quiet apartment with city views."),
            buyer(12, "Too poor", 500_000, 900_000, "Family needs a pool and good schools near Epping."),
            buyer(13, "Passed already", 1_600_000, 1_900_000, "Family needs a pool.", [{"deal_id": 5, "property_id": 1, "stage": "lost"}]),
            buyer(14, "In a deal", 1_700_000, 1_850_000, "Pool family home schools Epping.", [{"deal_id": 6, "property_id": 1, "stage": "offer"}]),
        ],
    )
    crm.docs = [
        make_document("property", 1, "Family home with pool", "Family home in Epping with a pool, near good schools."),
        make_document("property", 2, "City studio", "Studio apartment with city views."),
        *[make_document("contact", b["id"], b["name"], b["notes"]) for b in crm.buyers],
    ]
    await sync_index(crm, store, embedder)
    return crm


async def test_buyers_for_property_ranks_by_budget_and_fit(market, store):
    result = await buyers_for_property(market, store, 1)

    names = [m["name"] for m in result["matches"]]
    assert names.index("Pool family") < names.index("Budget fits, no pool")
    assert "Too poor" not in names  # $1.8m is well over a $900k budget
    assert "Passed already" not in names  # lost deal on this listing
    in_deal = next(m for m in result["matches"] if m["name"] == "In a deal")
    assert in_deal["existing_deal"]["deal_id"] == 6
    assert any("Already in deal #6" in r for r in in_deal["reasons"])
    top = result["matches"][0]
    assert 0 <= top["score"] <= 100 and top["reasons"][0].startswith("$1,800,000 is within")


async def test_properties_for_contact_skips_sold_and_unaffordable(market, store):
    result = await properties_for_contact(market, store, 10)

    assert result["contact"]["name"] == "Pool family"
    assert [m["id"] for m in result["matches"]] == [1, 2]  # sold cottage excluded; studio is far under budget but possible
    assert result["matches"][0]["detail"]["suburb"] == "Epping"


async def test_unknown_ids_return_none(market, store):
    assert await buyers_for_property(market, store, 999) is None
    assert await properties_for_contact(market, store, 999) is None
