"""Nightly analytics job: read the CRM's tables with Spark, build the marts, write them out.

    python -m rex_analytics.job                     # uses the environment below
    spark-submit rex_analytics/job.py               # same, on a Spark cluster

Environment
- CRM_JDBC_URL, CRM_DB_USER, CRM_DB_PASSWORD   source (and the Postgres sink), e.g. jdbc:postgresql://postgres:5432/rexcrm
- SINKS                     comma list of postgres, parquet, snowflake (default: postgres,parquet)
- PARQUET_PATH              default /data/warehouse
- SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, SNOWFLAKE_WAREHOUSE,
  SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA            enable the Snowflake sink
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

from pyspark.sql import SparkSession

from .sinks import ParquetSink, PostgresSink, Sink, SnowflakeSink
from .transforms import build_marts

log = logging.getLogger("rex.analytics")
SOURCE_TABLES = ["deals", "contacts", "properties", "users", "deal_activities"]
# Only what the marts need: never pull passwords, tokens or free-text notes into the warehouse.
COLUMNS = {
    "deals": "id, contact_id, property_id, user_id, stage, value, created_at, closed_at",
    "contacts": "id, type, source",
    "properties": "id, suburb, type, status, price, bedrooms",
    "users": "id, name",
    "deal_activities": "id, deal_id, type, meta, created_at",
}


def spark_session() -> SparkSession:
    builder = SparkSession.builder.appName("rex-crm-analytics")
    if os.environ.get("SPARK_MASTER") or not os.environ.get("DATABRICKS_RUNTIME_VERSION"):
        builder = (
            builder.master(os.environ.get("SPARK_MASTER", "local[*]"))
            .config("spark.sql.session.timeZone", "UTC")
            # CRM-sized data: Spark's default of 200 shuffle partitions is pure overhead here.
            .config("spark.sql.shuffle.partitions", os.environ.get("SHUFFLE_PARTITIONS", "8"))
            .config("spark.ui.showConsoleProgress", "false")
        )
    return builder.getOrCreate()


def read_tables(spark: SparkSession, url: str, user: str, password: str) -> dict:
    props = {"user": user, "password": password, "driver": "org.postgresql.Driver"}
    return {t: spark.read.jdbc(url, f"(SELECT {COLUMNS[t]} FROM {t}) AS {t}", properties=props) for t in SOURCE_TABLES}


def configured_sinks() -> list[Sink]:
    wanted = {s.strip() for s in os.environ.get("SINKS", "postgres,parquet").split(",") if s.strip()}
    sinks: list[Sink] = []
    if "postgres" in wanted:
        sinks.append(PostgresSink(os.environ["CRM_JDBC_URL"], os.environ["CRM_DB_USER"], os.environ["CRM_DB_PASSWORD"]))
    if "parquet" in wanted:
        sinks.append(ParquetSink(os.environ.get("PARQUET_PATH", "/data/warehouse")))
    if "snowflake" in wanted:
        if not os.environ.get("SNOWFLAKE_ACCOUNT"):
            log.warning("snowflake sink requested but SNOWFLAKE_ACCOUNT is not set: skipping it")
        else:
            keys = ["account", "user", "password", "warehouse", "database", "schema"]
            sinks.append(SnowflakeSink({k: os.environ[f"SNOWFLAKE_{k.upper()}"] for k in keys if os.environ.get(f"SNOWFLAKE_{k.upper()}")}))
    return sinks


def run() -> dict[str, int]:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    started = time.time()
    spark = spark_session()
    spark.sparkContext.setLogLevel("WARN")
    tables = read_tables(spark, os.environ["CRM_JDBC_URL"], os.environ["CRM_DB_USER"], os.environ["CRM_DB_PASSWORD"])
    marts = build_marts(tables)
    sinks = configured_sinks()
    counts = {}
    for name, df in marts.items():
        df = df.cache()
        counts[name] = df.count()
        for sink in sinks:
            sink.write(name, df)
            log.info("%s -> %s (%d rows)", name, sink.name, counts[name])
    # One row describing this run, so readers (the CRM's Insights page) can show how fresh the data is.
    run_info = spark.createDataFrame(
        [(datetime.now(timezone.utc).replace(tzinfo=None), round(time.time() - started, 1), json.dumps(counts))],
        "finished_at timestamp, seconds double, row_counts string",
    )
    for sink in sinks:
        sink.write("run_info", run_info)
    log.info("done in %.1fs: %s", time.time() - started, counts)
    spark.stop()
    return counts


if __name__ == "__main__":
    run()
