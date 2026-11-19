# Analytics (PySpark → Postgres / Parquet / Snowflake, runs on Databricks too)

A nightly batch job that turns CRM activity into the numbers an agency principal asks for:
- Which suburbs are moving, and at what prices?
- Which lead sources actually convert?
- How are agents tracking month to month?
- Where do deals stall?

```
CRM PostgreSQL ──(Spark JDBC, needed columns only)──► PySpark transforms ──► marts
                                                                         ├─► Postgres analytics_* tables → CRM "Insights" page
                                                                         ├─► Parquet (local volume, dbfs:/, s3://, abfss://)
                                                                         └─► Snowflake REX_* tables (optional)
```

| Mart | Grain | Answers |
|---|---|---|
| `fact_deals` | deal | Deal facts with suburb, type, lead source, agent, days to close, furthest stage reached |
| `suburb_market` | suburb × type | Listings on the market, median asking, price per bedroom, our sales, days to sell |
| `lead_funnel` | lead source | Deals, % reaching inspection/offer, won/lost, win rate, won value |
| `agent_performance` | agent × month | New deals, wins in the month they closed, win rate, value, days to close |
| `stage_velocity` | stage | Average days spent in each stage (from the CRM's stage-change log) |
| `run_info` | run | When it finished, how long it took, row counts (shown as "Updated … ago") |

**Privacy:** only the columns the marts need are read. That excludes names of clients, emails, phones, notes and passwords. Agent names are the only personal data in the output.

## Run

```bash
docker compose --profile analytics run --rm analytics      # then open the CRM's Insights page
```

- In Kubernetes, `k8s/analytics.yaml` is a CronJob that runs nightly at 3–4am Sydney time and writes to Postgres.
- On Databricks, `databricks.yml` is an Asset Bundle with the same code and a scheduled job cluster:
  ```bash
  databricks bundle deploy
  ```
  It is not exercised in CI because that needs a workspace.

**Snowflake:** add `snowflake` to `SINKS` (or `ANALYTICS_SINKS` in `.env`) and set the `SNOWFLAKE_*` variables. The marts are small (one row per suburb, source or agent-month), so they are written with `write_pandas` and `auto_create_table`. That needs no Spark connector jars.

## Test

```bash
docker compose --profile test run --rm analytics-test    # local Spark on hand-made tables (Java 21 in the image)
```
