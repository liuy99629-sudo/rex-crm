"""Script entry point for spark-submit and Databricks spark_python_task (they run a file, not a module)."""

from rex_analytics.job import run

if __name__ == "__main__":
    run()
