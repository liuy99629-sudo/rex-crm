"""PySpark transforms: CRM tables -> analytics marts. Pure functions of DataFrames (unit-tested).

Marts
- fact_deals:        one row per deal, enriched with listing, suburb, lead source, agent, cycle time
- suburb_market:     per suburb and property type: supply, asking prices, sales and time to sell
- lead_funnel:       per lead source: how far deals get, and conversion rates
- agent_performance: per agent per month: new deals, wins, win rate, value, days to close
- stage_velocity:    average days a deal spends in each stage (from the logged stage changes)
"""

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

STAGE_ORDER = {"lead": 0, "contacted": 1, "inspection": 2, "offer": 3, "negotiation": 4, "won": 5, "lost": -1}


def _stage_rank(col: str) -> F.Column:
    expr = F.lit(None).cast("int")
    for stage, rank in STAGE_ORDER.items():
        expr = F.when(F.col(col) == stage, F.lit(rank)).otherwise(expr)
    return expr


def fact_deals(deals: DataFrame, contacts: DataFrame, properties: DataFrame, users: DataFrame, activities: DataFrame) -> DataFrame:
    """One row per deal. For lost deals, `furthest_stage` comes from the stage-change log when present."""
    furthest_logged = (
        activities.where(F.col("type") == "stage_change")
        .select("deal_id", F.get_json_object(F.col("meta"), "$.from").alias("from_stage"))
        .withColumn("rank", _stage_rank("from_stage"))
        .groupBy("deal_id")
        .agg(F.max("rank").alias("max_logged_rank"))
    )
    return (
        deals.alias("d")
        .join(contacts.select(F.col("id").alias("c_id"), F.col("source").alias("lead_source")), F.col("d.contact_id") == F.col("c_id"), "left")
        .join(
            properties.select(
                F.col("id").alias("p_id"), "suburb", F.col("type").alias("property_type"), F.col("price").alias("asking_price"), "bedrooms"
            ),
            F.col("d.property_id") == F.col("p_id"),
            "left",
        )
        .join(users.select(F.col("id").alias("u_id"), F.col("name").alias("agent")), F.col("d.user_id") == F.col("u_id"), "left")
        .join(furthest_logged, F.col("d.id") == furthest_logged.deal_id, "left")
        .select(
            F.col("d.id").alias("deal_id"),
            F.col("d.stage").alias("stage"),
            F.col("d.value").cast("long").alias("value"),
            F.coalesce("lead_source", F.lit("Unknown")).alias("lead_source"),
            F.coalesce("suburb", F.lit("No listing")).alias("suburb"),
            "property_type",
            F.col("asking_price").cast("long").alias("asking_price"),
            "bedrooms",
            F.coalesce("agent", F.lit("Unassigned")).alias("agent"),
            F.col("d.created_at").alias("created_at"),
            F.col("d.closed_at").alias("closed_at"),
            F.date_trunc("month", F.col("d.created_at")).cast("date").alias("created_month"),
            F.when(F.col("d.closed_at").isNotNull(), F.datediff("d.closed_at", "d.created_at")).alias("days_to_close"),
            F.when(F.col("d.stage") == "lost", F.coalesce(F.col("max_logged_rank"), F.lit(0)))
            .otherwise(_stage_rank("d.stage"))
            .alias("furthest_rank"),
        )
    )


def suburb_market(fact: DataFrame, properties: DataFrame) -> DataFrame:
    supply = (
        properties.groupBy("suburb", F.col("type").alias("property_type"))
        .agg(
            F.count("*").alias("listings"),
            F.sum(F.when(F.col("status").isin("active", "under_offer"), 1).otherwise(0)).alias("on_market"),
            F.percentile_approx(F.when(F.col("status").isin("active", "under_offer"), F.col("price")), 0.5).cast("long").alias("median_asking"),
            F.round(F.avg(F.when(F.col("bedrooms") > 0, F.col("price") / F.col("bedrooms"))), 0).cast("long").alias("avg_price_per_bedroom"),
        )
    )
    sales = (
        fact.where(F.col("stage") == "won")
        .groupBy("suburb", "property_type")
        .agg(
            F.count("*").alias("deals_won"),
            F.sum("value").alias("won_value"),
            F.round(F.avg("days_to_close"), 1).alias("avg_days_to_close"),
        )
    )
    return (
        supply.join(sales, ["suburb", "property_type"], "left")
        .fillna({"deals_won": 0, "won_value": 0})
        .orderBy(F.desc("on_market"), "suburb")
    )


def lead_funnel(fact: DataFrame) -> DataFrame:
    def reached(rank: int) -> F.Column:
        return F.sum(F.when(F.col("furthest_rank") >= rank, 1).otherwise(0))

    agg = fact.groupBy("lead_source").agg(
        F.count("*").alias("deals"),
        reached(2).alias("reached_inspection"),
        reached(3).alias("reached_offer"),
        F.sum(F.when(F.col("stage") == "won", 1).otherwise(0)).alias("won"),
        F.sum(F.when(F.col("stage") == "lost", 1).otherwise(0)).alias("lost"),
        F.sum(F.when(F.col("stage") == "won", F.col("value")).otherwise(0)).alias("won_value"),
    )
    closed = F.col("won") + F.col("lost")
    return (
        agg.withColumn("win_rate", F.when(closed > 0, F.round(F.col("won") / closed, 3)))
        .withColumn("inspection_rate", F.round(F.col("reached_inspection") / F.col("deals"), 3))
        .orderBy(F.desc("deals"), "lead_source")
    )


def agent_performance(fact: DataFrame) -> DataFrame:
    """Per agent per month; a deal counts as won in the month it closed."""
    created = fact.groupBy("agent", F.col("created_month").alias("month")).agg(F.count("*").alias("new_deals"))
    closed = (
        fact.where(F.col("closed_at").isNotNull())
        .groupBy("agent", F.date_trunc("month", "closed_at").cast("date").alias("month"))
        .agg(
            F.sum(F.when(F.col("stage") == "won", 1).otherwise(0)).alias("won"),
            F.sum(F.when(F.col("stage") == "lost", 1).otherwise(0)).alias("lost"),
            F.sum(F.when(F.col("stage") == "won", F.col("value")).otherwise(0)).alias("won_value"),
            F.round(F.avg(F.when(F.col("stage") == "won", F.col("days_to_close"))), 1).alias("avg_days_to_close"),
        )
    )
    perf = created.join(closed, ["agent", "month"], "full").fillna({"new_deals": 0, "won": 0, "lost": 0, "won_value": 0})
    closed_n = F.col("won") + F.col("lost")
    return perf.withColumn("win_rate", F.when(closed_n > 0, F.round(F.col("won") / closed_n, 3))).orderBy(F.desc("month"), "agent")


def stage_velocity(deals: DataFrame, activities: DataFrame) -> DataFrame:
    """Days spent in each stage: time from entering a stage (its stage change, or deal creation for
    the first stage) to the next stage change. Only stays that have ended are measured."""
    changes = activities.where(F.col("type") == "stage_change").select(
        "deal_id",
        F.get_json_object(F.col("meta"), "$.from").alias("from_stage"),
        F.get_json_object(F.col("meta"), "$.to").alias("to_stage"),
        F.col("created_at").alias("at"),
    )
    w = Window.partitionBy("deal_id").orderBy("at")
    with_prev = changes.withColumn("entered_at", F.lag("at").over(w)).join(
        deals.select(F.col("id").alias("deal_id"), F.col("created_at").alias("deal_created")), "deal_id"
    )
    stays = with_prev.select(
        F.col("from_stage").alias("stage"),
        (F.unix_timestamp("at") - F.unix_timestamp(F.coalesce("entered_at", "deal_created"))).alias("seconds"),
    ).where(F.col("seconds") >= 0)
    return (
        stays.groupBy("stage")
        .agg(F.count("*").alias("transitions"), F.round(F.avg("seconds") / 86400, 1).alias("avg_days"))
        .withColumn("stage_rank", _stage_rank("stage"))
        .orderBy("stage_rank")
        .drop("stage_rank")
    )


def build_marts(tables: dict[str, DataFrame]) -> dict[str, DataFrame]:
    fact = fact_deals(tables["deals"], tables["contacts"], tables["properties"], tables["users"], tables["deal_activities"]).cache()
    return {
        "fact_deals": fact,
        "suburb_market": suburb_market(fact, tables["properties"]),
        "lead_funnel": lead_funnel(fact),
        "agent_performance": agent_performance(fact),
        "stage_velocity": stage_velocity(tables["deals"], tables["deal_activities"]),
    }
