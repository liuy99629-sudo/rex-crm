# Databricks notebook source
# Runs the Rex CRM analytics job on Databricks serverless (deployed by databricks.yml as a notebook task).
# The rex_analytics package is read from a Unity Catalog volume (CODE_PATH): on Free Edition serverless,
# importing from workspace files can fail with EIO, while volumes read reliably.
import os
import sys

PARAMS = ["SOURCE", "SOURCE_PATH", "SINKS", "DELTA_CATALOG", "DELTA_SCHEMA", "CODE_PATH"]
for name in PARAMS:
    value = dbutils.widgets.get(name)  # noqa: F821 - provided by Databricks
    if value:
        os.environ[name] = value

sys.path.insert(0, os.environ["CODE_PATH"])
for module in [m for m in sys.modules if m.startswith("rex_analytics")]:
    del sys.modules[module]  # pick up a freshly uploaded package in a reused session

from rex_analytics.job import run  # noqa: E402

counts = run()
print(counts)
