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


class SnowflakeSink:
    name = "snowflake"

    def __init__(self, connect_kwargs: dict[str, str], connector=None) -> None:
        self._kwargs = connect_kwargs
        self._connector = connector  # injectable for tests

    def write(self, mart: str, df: DataFrame) -> None:
        if self._connector is None:
            import snowflake.connector
            from snowflake.connector.pandas_tools import write_pandas

            self._connector = (snowflake.connector.connect, write_pandas)
        connect, write_pandas = self._connector
        pdf = df.toPandas()
        pdf.columns = [c.upper() for c in pdf.columns]  # Snowflake's unquoted identifiers are upper case
        with connect(**self._kwargs) as conn:
            write_pandas(conn, pdf, f"REX_{mart.upper()}", auto_create_table=True, overwrite=True)
        log.info("snowflake: wrote %d rows to REX_%s", len(pdf), mart.upper())
