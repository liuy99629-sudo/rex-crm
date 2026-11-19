"""Run the pipeline locally against LocalStack (S3 + DynamoDB), without deploying a Lambda.

    python -m leads.local          # create bucket/table if needed, then poll inbox/ every few seconds
    python -m leads.local --seed   # also upload the sample emails in samples/ to inbox/

It calls the same `process_email` the Lambda does, then moves each object to processed/ (or
failed/), standing in for the S3 event notification. LocalStack has no Bedrock, so the default
extractor here is the rule-based one (set EXTRACTOR=claude with real AWS credentials to use Claude)."""

import argparse
import logging
import os
import pathlib
import time

import boto3

from .crm import CrmClient
from .extract import ClaudeExtractor, RuleExtractor
from .ledger import Ledger
from .pipeline import process_email

log = logging.getLogger("rex.leads.local")
SAMPLES = pathlib.Path(__file__).resolve().parent.parent / "samples"


def ensure_resources(s3, dynamodb, bucket: str, table_name: str) -> None:
    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    if bucket not in existing:
        s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": s3.meta.region_name})
    if table_name not in dynamodb.meta.client.list_tables()["TableNames"]:
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "message_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "message_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        ).wait_until_exists()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="upload samples/*.eml to inbox/")
    parser.add_argument("--once", action="store_true", help="process what is there and exit")
    args = parser.parse_args()

    region = os.environ.get("AWS_REGION", "ap-southeast-2")
    endpoint = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
    bucket = os.environ.get("INBOUND_BUCKET", "rex-inbound-mail")
    s3 = boto3.client("s3", region_name=region, endpoint_url=endpoint)
    dynamodb = boto3.resource("dynamodb", region_name=region, endpoint_url=endpoint)
    ensure_resources(s3, dynamodb, bucket, os.environ.get("LEDGER_TABLE", "rex-lead-ledger"))

    ledger = Ledger(dynamodb.Table(os.environ.get("LEDGER_TABLE", "rex-lead-ledger")))
    extractor = ClaudeExtractor(region) if os.environ.get("EXTRACTOR") == "claude" else RuleExtractor()
    crm = CrmClient(os.environ["CRM_API_URL"], os.environ["CRM_TOKEN"])

    if args.seed:
        for path in sorted(SAMPLES.glob("*.eml")):
            s3.put_object(Bucket=bucket, Key=f"inbox/{path.name}", Body=path.read_bytes())
            log.info("uploaded %s", path.name)

    while True:
        for obj in s3.list_objects_v2(Bucket=bucket, Prefix="inbox/").get("Contents", []):
            key = obj["Key"]
            raw = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            try:
                outcome = process_email(raw, key, ledger, extractor, crm)
                log.info("%s -> %s %s %s", key, outcome.status, outcome.crm_reference or "", outcome.detail)
                target = "processed/"
            except Exception:
                log.exception("%s failed", key)
                target = "failed/"
            s3.copy_object(Bucket=bucket, Key=target + key.removeprefix("inbox/"), CopySource={"Bucket": bucket, "Key": key})
            s3.delete_object(Bucket=bucket, Key=key)
        if args.once:
            return
        time.sleep(3)


if __name__ == "__main__":
    main()
