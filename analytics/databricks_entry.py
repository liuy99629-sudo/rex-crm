"""Databricks entry point (same as run_job.py; a separate file so the workspace never serves a stale cached copy).

Settings come from the environment (see rex_analytics/job.py). Serverless Databricks jobs cannot set
environment variables, so `--NAME=value` arguments are accepted too and copied into the environment:

    run_job.py --SOURCE=parquet --SOURCE_PATH=/Volumes/workspace/rex_crm/raw --SINKS=delta
"""

import os
import sys

for arg in sys.argv[1:]:
    if arg.startswith("--") and "=" in arg:
        key, value = arg[2:].split("=", 1)
        os.environ[key] = value

# On Databricks the bundle syncs this folder; make the package importable however the file is launched.
# (Databricks executes the file without defining __file__, so fall back to argv[0] and the working dir.)
for candidate in (globals().get("__file__"), sys.argv[0] if sys.argv else None):
    if candidate:
        sys.path.insert(0, os.path.dirname(os.path.abspath(candidate)))
sys.path.insert(0, os.getcwd())
# On Databricks Free Edition serverless, importing from workspace files can fail with EIO; the package
# is also uploaded to a Unity Catalog volume (CODE_PATH), which reads reliably. It takes precedence.
if os.environ.get("CODE_PATH"):
    sys.path.insert(0, os.environ["CODE_PATH"])

from rex_analytics.job import run  # noqa: E402

if __name__ == "__main__":
    run()
