# Cloud deployment (free tiers)

What runs where, how it was deployed, and how to remove it. No paid services: Claude API and Bedrock
calls are off (the lead pipeline uses the free rule-based extractor) and GKE is not deployed (the Google
Cloud billing account has no free credit, so the cluster would be billed).

| Platform | What | Cost |
|---|---|---|
| AWS (ap-southeast-2) | Lead pipeline: S3 inbox, Lambda, DynamoDB ledger, SQS DLQ, CloudWatch alarm (stack `rex-lead-pipeline`) | Free tier; a US$1 budget alert emails on any charge |
| Databricks Free Edition | Analytics job on serverless: snapshot in volume `workspace.rex_crm.raw`, marts as Delta tables `workspace.rex_crm.*` | Free |
| Snowflake (30-day trial, AWS Sydney) | Analytics marts in `REX_CRM.ANALYTICS.REX_*`, warehouse `REX_WH` (XS, auto-suspends after 60 s) | Trial credits only; the trial ends by itself |

## AWS lead pipeline

```bash
aws login                                   # browser sign-in; short-lived credentials
cd lead-pipeline
sam build && sam deploy --stack-name rex-lead-pipeline --resolve-s3 --capabilities CAPABILITY_IAM \
  --parameter-overrides Extractor=rules CrmApiUrl=none
```

`CrmApiUrl=none` means no CRM is connected yet: each lead is extracted and recorded in the DynamoDB ledger
with status `extracted`. Once the CRM has a public URL, redeploy with `CrmApiUrl=https://…/api` and put an
integration token in SSM (`/rex-crm/lead-pipeline-token`, see lead-pipeline/README.md).
`Extractor=claude` switches extraction to Claude in Amazon Bedrock, which is billed per token.

Try it: copy a `.eml` file to `s3://rex-inbound-mail-<account>-ap-southeast-2/inbox/` and look at the ledger
table. New accounts have a Lambda concurrency limit of 10, so the template does not reserve concurrency by default.

Remove it:

```bash
aws s3 rm s3://rex-inbound-mail-<account>-ap-southeast-2 --recursive
```

```bash
aws cloudformation delete-stack --stack-name rex-lead-pipeline
```

## Databricks analytics

```bash
docker compose --profile analytics run --rm -e EXPORT_RAW_PATH=/data/warehouse/raw -e SINKS=postgres analytics
# copy the snapshot out of the `warehouse` volume, then:
databricks fs cp -r <snapshot>/raw dbfs:/Volumes/workspace/rex_crm/raw --overwrite -p rex
databricks fs cp -r analytics/rex_analytics dbfs:/Volumes/workspace/rex_crm/code/rex_analytics --overwrite -p rex
cd analytics && databricks bundle deploy -p rex && databricks bundle run rex_analytics -p rex
```

On Free Edition serverless, Python files in the workspace sometimes fail to read (EIO), so the job is a small
notebook (`databricks_notebook.py`) that imports the package from the `code` volume.

Remove it:

```bash
databricks bundle destroy -p rex
```

```bash
databricks schemas delete workspace.rex_crm --force -p rex
```

## Snowflake analytics

The job signs in with a key pair (no password). The private key is in `%USERPROFILE%\.rex-secrets\` (never
in the repo). The public key is registered once on the Snowflake user with
`ALTER USER … SET RSA_PUBLIC_KEY = '…'` (see `%USERPROFILE%\.rex-secrets\snowflake_setup.sql`).

```bash
docker compose --profile analytics run --rm \
  -v "%USERPROFILE%\.rex-secrets:/secrets:ro" \
  -e SINKS=postgres,snowflake -e SNOWFLAKE_ACCOUNT=BIQXSYY-QW95202 -e SNOWFLAKE_USER=<user> \
  -e SNOWFLAKE_PRIVATE_KEY_FILE=/secrets/snowflake_rsa_key.p8 analytics
```

The job creates `REX_WH`, `REX_CRM` and `REX_CRM.ANALYTICS` if they are missing.
Remove it with `DROP DATABASE REX_CRM; DROP WAREHOUSE REX_WH;`, or just let the trial expire.
