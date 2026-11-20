"""Where the marts go.

- PostgresSink: tables analytics_<mart> in the CRM database, read by the CRM's Insights page.
- ParquetSink:  files under a directory (local disk, or s3:// / abfss:// / dbfs:/ on a cluster).
- SnowflakeSink: the agency's warehouse, when SNOWFLAKE_ACCOUNT is set. Marts are small
  (one row per suburb / source / agent-month), so they are collected and written with
  write_pandas rather than through the Spark connector.
"""

import logging
from typing import Protocol

from pyspark.sql import DataFrame

log = logging.getLogger("rex.analytics")


class Sink(Protocol):
    name: str

    def write(self, mart: str, df: DataFrame) -> None: ...


class PostgresSink:
    name = "postgres"

    def __init__(self, jdbc_url: str, user: str, password: str, prefix: str = "analytics_") -> None:
        self._url, self._props, self._prefix = jdbc_url, {"user": user, "password": password, "driver": "org.postgresql.Driver"}, prefix

    def write(self, mart: str, df: DataFrame) -> None:
        # truncate keeps the table (and anything granted on it); the CRM never sees a missing table mid-run.
        df.write.option("truncate", "true").jdbc(self._url, self._prefix + mart, mode="overwrite", properties=self._props)


class ParquetSink:
    name = "parquet"

    def __init__(self, base_path: str) -> None:
        self._base = base_path.rstrip("/")

    def write(self, mart: str, df: DataFrame) -> None:
        df.write.mode("overwrite").parquet(f"{self._base}/{mart}")


def load_private_key(path: str) -> bytes:
    """PEM key file -> DER bytes for the connector's `private_key` argument. Passing the key itself
    (not the file) avoids the connector's file-permission check, which every Windows folder mounted
    into Docker fails (it always looks group/world-writable there)."""
    from cryptography.hazmat.primitives import serialization

    with open(path, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


class SnowflakeSink:
    name = "snowflake"

    def __init__(self, connect_kwargs: dict, connector=None) -> None:
        connect_kwargs = dict(connect_kwargs)
        if "private_key_file" in connect_kwargs:
            connect_kwargs["private_key"] = load_private_key(connect_kwargs.pop("private_key_file"))
        self._kwargs = connect_kwargs
        self._connector = connector  # injectable for tests
        self._ready = False

    def _bootstrap(self, conn) -> None:
        """Create the (tiny, auto-suspending) warehouse, database and schema on first use."""
        wh, db, schema = self._kwargs["warehouse"], self._kwargs["database"], self._kwargs["schema"]
        cur = conn.cursor()
        for sql in (
            f"CREATE WAREHOUSE IF NOT EXISTS {wh} WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE",
            f"CREATE DATABASE IF NOT EXISTS {db}",
            f"CREATE SCHEMA IF NOT EXISTS {db}.{schema}",
            f"USE WAREHOUSE {wh}",
            f"USE SCHEMA {db}.{schema}",
        ):
            cur.execute(sql)
        self._ready = True

    def write(self, mart: str, df: DataFrame) -> None:
        if self._connector is None:
            import snowflake.connector
            from snowflake.connector.pandas_tools import write_pandas

            self._connector = (snowflake.connector.connect, write_pandas)
        connect, write_pandas = self._connector
        pdf = df.toPandas()
        pdf.columns = [c.upper() for c in pdf.columns]  # Snowflake's unquoted identifiers are upper case
        with connect(**self._kwargs) as conn:
            if not self._ready:
                self._bootstrap(conn)
            # use_logical_type keeps pandas timestamps as Snowflake timestamps (not raw integers).
            write_pandas(conn, pdf, f"REX_{mart.upper()}", auto_create_table=True, overwrite=True, use_logical_type=True)
        log.info("snowflake: wrote %d rows to REX_%s", len(pdf), mart.upper())


class DeltaTableSink:
    """Managed Delta tables in a lakehouse catalog (Databricks Unity Catalog): <catalog>.<schema>.<mart>."""

    name = "delta"

    def __init__(self, catalog: str, schema: str) -> None:
        self._prefix = f"{catalog}.{schema}"
        self._schema_ready = False

    def write(self, mart: str, df: DataFrame) -> None:
        if not self._schema_ready:
            df.sparkSession.sql(f"CREATE SCHEMA IF NOT EXISTS {self._prefix}")
            self._schema_ready = True
        df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{self._prefix}.{mart}")
