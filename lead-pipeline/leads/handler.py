"""AWS Lambda entry point. Triggered by S3 ObjectCreated events under inbox/ (SES writes incoming
mail there). Configuration comes from environment variables set by template.yaml."""

import logging
import os
import urllib.parse
from functools import lru_cache
from typing import Any

import boto3

from .crm import CrmClient
from .extract import ClaudeExtractor, Extractor, RuleExtractor
from .ledger import Ledger
from .pipeline import process_email

logging.getLogger().setLevel(logging.INFO)


@lru_cache(maxsize=1)
def _deps() -> tuple[Any, Ledger, Extractor, CrmClient]:
    """Built once per Lambda container (reused across invocations)."""
    region = os.environ.get("AWS_REGION", "ap-southeast-2")
    endpoint = os.environ.get("AWS_ENDPOINT_URL")  # LocalStack in local runs; unset on AWS
    s3 = boto3.client("s3", region_name=region, endpoint_url=endpoint)
    table = boto3.resource("dynamodb", region_name=region, endpoint_url=endpoint).Table(os.environ["LEDGER_TABLE"])

    token = os.environ.get("CRM_TOKEN")
    if not token:  # on AWS the token lives in SSM Parameter Store (SecureString), not in the template
        ssm = boto3.client("ssm", region_name=region, endpoint_url=endpoint)
        token = ssm.get_parameter(Name=os.environ["CRM_TOKEN_PARAM"], WithDecryption=True)["Parameter"]["Value"]

    extractor: Extractor = (
        ClaudeExtractor(os.environ.get("BEDROCK_REGION", region), os.environ.get("BEDROCK_MODEL", "anthropic.claude-opus-5-5"))
        if os.environ.get("EXTRACTOR", "claude") == "claude"
        else RuleExtractor()
    )
    return s3, Ledger(table), extractor, CrmClient(os.environ["CRM_API_URL"], token)


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    s3, ledger, extractor, crm = _deps()
    results = []
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        raw = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        outcome = process_email(raw, key, ledger, extractor, crm)
        results.append(outcome.__dict__)
    return {"results": results}
