"""Transforms on small, hand-made tables with a local SparkSession (needs Java; runs in Docker/CI)."""

import json
from datetime import datetime

import pandas as pd
import pytest
from pyspark.sql import SparkSession

from rex_analytics.sinks import SnowflakeSink
from rex_analytics.transforms import build_marts


@pytest.fixture(scope="session")
def spark():
    s = SparkSession.builder.master("local[1]").appName("tests").config("spark.sql.session.timeZone", "UTC").config(
        "spark.ui.enabled", "false"
    ).getOrCreate()
    yield s
    s.stop()


def d(day: int) -> datetime:
    return datetime(2026, 10, day, 9, 0)


@pytest.fixture(scope="session")
def marts(spark):
    users = spark.createDataFrame([(1, "Amy"), (2, "Ben")], "id long, name string")
    contacts = spark.createDataFrame(
        [(1, "buyer", "Domain"), (2, "buyer", "Domain"), (3, "buyer", "Website"), (4, "buyer", None)],
        "id long, type string, source string",
    )
    properties = spark.createDataFrame(
        [
            (10, "Epping", "house", "active", 1_800_000, 4),
            (11, "Epping", "house", "sold", 1_600_000, 4),
            (12, "Epping", "house", "under_offer", 2_000_000, 5),
            (13, "Bondi", "apartment", "active", 1_200_000, 2),
            (14, "Bondi", "apartment", "draft", 900_000, 1),
        ],
        "id long, suburb string, type string, status string, price long, bedrooms int",
    )
    deals = spark.createDataFrame(
        [
            # id, contact, property, agent, stage, value, created, closed
            (1, 1, 11, 1, "won", 1_600_000, d(1), d(21)),  # 20 days
            (2, 2, 10, 1, "lost", 1_700_000, d(2), d(12)),
            (3, 3, 13, 2, "offer", 1_150_000, d(3), None),
            (4, 4, None, 2, "lead", 0, d(4), None),
            (5, 2, 12, 2, "won", 1_950_000, d(5), d(15)),  # 10 days
        ],
        "id long, contact_id long, property_id long, user_id long, stage string, value long, created_at timestamp, closed_at timestamp",
    )
    sc = lambda f, t: json.dumps({"from": f, "to": t})  # noqa: E731
    activities = spark.createDataFrame(
        [
            (1, 2, "stage_change", sc("lead", "inspection"), d(4)),  # 2 days in lead
            (2, 2, "stage_change", sc("inspection", "lost"), d(12)),  # 8 days in inspection
            (3, 3, "stage_change", sc("lead", "offer"), d(7)),  # 4 days in lead
            (4, 3, "note", None, d(8)),
        ],
        "id long, deal_id long, type string, meta string, created_at timestamp",
    )
    tables = {"deals": deals, "contacts": contacts, "properties": properties, "users": users, "deal_activities": activities}
    return {k: v.toPandas() for k, v in build_marts(tables).items()}


def row(df: pd.DataFrame, **match):
    m = df
    for k, v in match.items():
        m = m[m[k] == v]
    assert len(m) == 1, f"expected one row for {match}, got {len(m)}"
    return m.iloc[0]


def test_fact_deals(marts):
    f = marts["fact_deals"]
    assert len(f) == 5
    assert row(f, deal_id=1)["days_to_close"] == 20
    assert row(f, deal_id=4)["suburb"] == "No listing" and row(f, deal_id=4)["lead_source"] == "Unknown"
    assert row(f, deal_id=2)["furthest_rank"] == 2  # lost, but reached inspection (from the stage log)
    assert row(f, deal_id=3)["agent"] == "Ben"


def test_suburb_market(marts):
    m = marts["suburb_market"]
    epping = row(m, suburb="Epping", property_type="house")
    assert (epping["listings"], epping["on_market"]) == (3, 2)  # sold one is not on the market
    assert epping["deals_won"] == 2 and epping["won_value"] == 3_550_000
    assert epping["avg_days_to_close"] == 15.0
    bondi = row(m, suburb="Bondi", property_type="apartment")
    assert bondi["on_market"] == 1 and bondi["median_asking"] == 1_200_000  # draft excluded from asking prices
    assert bondi["deals_won"] == 0


def test_lead_funnel(marts):
    f = marts["lead_funnel"]
    domain = row(f, lead_source="Domain")
    assert domain["deals"] == 3
    assert domain["reached_inspection"] == 3  # 2 wins + 1 lost that reached inspection
    assert (domain["won"], domain["lost"]) == (2, 1)
    assert domain["win_rate"] == pytest.approx(0.667)
    website = row(f, lead_source="Website")
    assert website["reached_offer"] == 1 and pd.isna(website["win_rate"])  # nothing closed yet


def test_agent_performance(marts):
    a = marts["agent_performance"]
    amy = row(a, agent="Amy")
    assert (amy["new_deals"], amy["won"], amy["lost"]) == (2, 1, 1)
    assert amy["win_rate"] == 0.5 and amy["avg_days_to_close"] == 20.0
    ben = row(a, agent="Ben")
    assert (ben["new_deals"], ben["won"], ben["won_value"]) == (3, 1, 1_950_000)


def test_stage_velocity(marts):
    v = marts["stage_velocity"]
    lead = row(v, stage="lead")
    # deal 2: created d2, left lead d4 (2 days); deal 3: created d3, left lead d7 (4 days)
    assert lead["transitions"] == 2 and lead["avg_days"] == 3.0
    assert row(v, stage="inspection")["avg_days"] == 8.0
    assert list(v["stage"]) == ["lead", "inspection"]


def test_snowflake_sink_uppercases_and_overwrites(spark):
    calls = {}

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def connect(**kwargs):
        calls["connect"] = kwargs
        return Conn()

    def write_pandas(conn, pdf, table, auto_create_table, overwrite):
        calls.update(table=table, columns=list(pdf.columns), rows=len(pdf), auto=auto_create_table, overwrite=overwrite)

    sink = SnowflakeSink({"account": "acme"}, connector=(connect, write_pandas))
    sink.write("lead_funnel", spark.createDataFrame([("Domain", 3)], "lead_source string, deals long"))

    assert calls == {"connect": {"account": "acme"}, "table": "REX_LEAD_FUNNEL", "columns": ["LEAD_SOURCE", "DEALS"], "rows": 1, "auto": True, "overwrite": True}
