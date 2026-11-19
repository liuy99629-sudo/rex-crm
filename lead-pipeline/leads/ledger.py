"""DynamoDB ledger: one item per email (key = Message-ID).

- Idempotency: S3 events are delivered at least once and Lambda retries on errors, so an email
  can arrive twice. `claim` is a conditional write; only the first delivery proceeds.
- Audit: what was extracted, what the CRM returned, and why an email was ignored or failed.
Items expire after 90 days (DynamoDB TTL on `expires_at`)."""

import json
import time
from typing import Any

from botocore.exceptions import ClientError

TTL_SECONDS = 90 * 24 * 3600
RETRYABLE = {"failed"}


class Ledger:
    def __init__(self, table: Any) -> None:
        self._table = table  # boto3 DynamoDB Table resource

    def claim(self, message_id: str, s3_key: str) -> bool:
        """True if this delivery should process the email; False if it is already done or in progress."""
        now = int(time.time())
        try:
            self._table.put_item(
                Item={"message_id": message_id, "status": "processing", "s3_key": s3_key, "received_at": now,
                      "expires_at": now + TTL_SECONDS},
                # New email, or a previous attempt that failed (so a retry may take over).
                ConditionExpression="attribute_not_exists(message_id) OR #s IN (:failed)",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":failed": "failed"},
            )
            return True
        except ClientError as err:
            if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def finish(self, message_id: str, status: str, **details: Any) -> None:
        """status: processed | ignored | failed."""
        self._table.update_item(
            Key={"message_id": message_id},
            UpdateExpression="SET #s = :s, finished_at = :t, details = :d",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": status, ":t": int(time.time()), ":d": json.dumps(details, default=str)[:20_000]},
        )

    def get(self, message_id: str) -> dict[str, Any] | None:
        return self._table.get_item(Key={"message_id": message_id}).get("Item")
