"""Nightly analytics job: read the CRM's tables with Spark, build the marts, write them out.

    python -m rex_analytics.job                     # uses the environment below
    spark-submit rex_analytics/job.py               # same, on a Spark cluster

Environment
- CRM_JDBC_URL, CRM_DB_USER, CRM_DB_PASSWORD   source (and the Postgres sink), e.g. jdbc:postgresql://postgres:5432/rexcrm
- SOURCE                    jdbc (default) or parquet; SOURCE_PATH for parquet (a snapshot written by EXPORT_RAW_PATH)
- EXPORT_RAW_PATH           also write the (column-limited) raw tables there as Parquet
- SINKS                     comma list of postgres, parquet, delta, snowflake (default: postgres,parquet)
- PARQUET_PATH              default /data/warehouse
- DELTA_CATALOG, DELTA_SCHEMA   managed Delta tables (default workspace.rex_crm), e.g. on Databricks
- SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER and SNOWFLAKE_PRIVATE_KEY_FILE (or SNOWFLAKE_PASSWORD); optional
  SNOWFLAKE_ROLE / _WAREHOUSE / _DATABASE / _SCHEMA (default REX_WH / REX_CRM / ANALYTICS, created if missing)
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

from pyspark.sql import SparkSession

from .sinks import DeltaTableSink, ParquetSink, PostgresSink, Sink, SnowflakeSink
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


def read_snapshot(spark: SparkSession, path: str) -> dict:
    """Raw tables exported earlier with EXPORT_RAW_PATH, for runs that cannot reach the CRM database
    (e.g. a cloud workspace reading a snapshot uploaded to a volume)."""
    return {t: spark.read.parquet(f"{path.rstrip('/')}/{t}") for t in SOURCE_TABLES}


def configured_sinks() -> list[Sink]:
    wanted = {s.strip() for s in os.environ.get("SINKS", "postgres,parquet").split(",") if s.strip()}
    sinks: list[Sink] = []
    if "postgres" in wanted:
        sinks.append(PostgresSink(os.environ["CRM_JDBC_URL"], os.environ["CRM_DB_USER"], os.environ["CRM_DB_PASSWORD"]))
    if "parquet" in wanted:
        sinks.append(ParquetSink(os.environ.get("PARQUET_PATH", "/data/warehouse")))
    if "delta" in wanted:
        sinks.append(DeltaTableSink(os.environ.get("DELTA_CATALOG", "workspace"), os.environ.get("DELTA_SCHEMA", "rex_crm")))
    if "snowflake" in wanted:
        if not os.environ.get("SNOWFLAKE_ACCOUNT"):
            log.warning("snowflake sink requested but SNOWFLAKE_ACCOUNT is not set: skipping it")
        else:
            # Key-pair auth (SNOWFLAKE_PRIVATE_KEY_FILE) is preferred over a password; MFA blocks passwords for scripts.
            keys = ["account", "user", "password", "private_key_file", "role", "warehouse", "database", "schema"]
            kwargs = {k: os.environ[f"SNOWFLAKE_{k.upper()}"] for k in keys if os.environ.get(f"SNOWFLAKE_{k.upper()}")}
            kwargs.setdefault("warehouse", "REX_WH")
            kwargs.setdefault("database", "REX_CRM")
            kwargs.setdefault("schema", "ANALYTICS")
            sinks.append(SnowflakeSink(kwargs))
    return sinks


def run() -> dict[str, int]:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    started = time.time()
    spark = spark_session()
    # Databricks serverless (Spark Connect) has no SparkContext, no DataFrame.cache() and a shared session.
    serverless = bool(os.environ.get("DATABRICKS_RUNTIME_VERSION"))
    if not serverless:
        spark.sparkContext.setLogLevel("WARN")
    if os.environ.get("SOURCE", "jdbc") == "parquet":
        tables = read_snapshot(spark, os.environ["SOURCE_PATH"])
    else:
        tables = read_tables(spark, os.environ["CRM_JDBC_URL"], os.environ["CRM_DB_USER"], os.environ["CRM_DB_PASSWORD"])
    if os.environ.get("EXPORT_RAW_PATH"):
        # Only the whitelisted COLUMNS are exported: no client names, contact details or notes.
        for name, df in tables.items():
            df.write.mode("overwrite").parquet(f"{os.environ['EXPORT_RAW_PATH'].rstrip('/')}/{name}")
        log.info("exported raw snapshot to %s", os.environ["EXPORT_RAW_PATH"])
    marts = build_marts(tables, cache=not serverless)
    sinks = configured_sinks()
    counts = {}
    for name, df in marts.items():
        if not serverless:
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
    if not serverless:
        spark.stop()
    return counts


if __name__ == "__main__":
    run()
