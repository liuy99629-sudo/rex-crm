import io
import json
import pathlib
import urllib.error
from types import SimpleNamespace

import boto3
import pytest
from moto import mock_aws

from leads.crm import CrmClient
from leads.email_parse import parse_email
from leads.extract import LEAD_SCHEMA, ClaudeExtractor, Extraction, RuleExtractor, to_extraction
from leads.ledger import Ledger
from leads.pipeline import process_email

SAMPLES = pathlib.Path(__file__).resolve().parent.parent / "samples"
REGION = "ap-southeast-2"


def sample(name: str) -> bytes:
    return (SAMPLES / name).read_bytes()


class FakeCrm:
    """Stands in for urllib: records requests, answers with a scripted status."""

    def __init__(self, status: int = 201):
        self.status = status
        self.requests: list[dict] = []

    def __call__(self, req, timeout):
        self.requests.append({"url": req.full_url, "auth": req.get_header("Authorization"), "body": json.loads(req.data)})
        if self.status >= 400:
            raise urllib.error.HTTPError(req.full_url, self.status, "err", {}, io.BytesIO(b'{"message":"nope"}'))
        n = len(self.requests)
        return io.BytesIO(json.dumps({"deal_id": n, "reference": f"ENQ-{n:05d}", "listing_id": 1}).encode())


@pytest.fixture
def ledger():
    with mock_aws():
        db = boto3.resource("dynamodb", region_name=REGION)
        table = db.create_table(
            TableName="ledger",
            KeySchema=[{"AttributeName": "message_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "message_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield Ledger(table)


# --- parsing and extraction -----------------------------------------------------------------


def test_parses_plain_and_html_emails():
    rea = parse_email(sample("01-rea-epping.eml"))
    assert rea.message_id == "rea-20261119-0001@realestate.com.au"
    assert rea.from_email == "no-reply@realestate.com.au"
    assert "Name: Mia Chen" in rea.body

    dom = parse_email(sample("02-domain-chatswood.eml"))
    assert "<td>" not in dom.body and "Name: Oliver Grant" in dom.body


def test_rule_extractor_reads_labelled_portal_emails():
    lead = RuleExtractor().extract(parse_email(sample("01-rea-epping.eml"))).lead
    assert lead.source == "realestate.com.au"
    assert (lead.name, lead.email, lead.phone) == ("Mia Chen", "mia.chen@example.com", "0421 555 018")
    assert lead.listing_hint == "14 Kent Street, Epping NSW 2121"
    assert (lead.budget_min, lead.budget_max) == (1_700_000, 1_900_000)
    assert "pool heated" in lead.message

    dom = RuleExtractor().extract(parse_email(sample("02-domain-chatswood.eml"))).lead
    assert dom.source == "Domain" and dom.listing_hint == "Pet-friendly apartment near Chatswood station"

    assert RuleExtractor().extract(parse_email(sample("03-newsletter.eml"))).lead is None


def test_validation_never_uses_a_noreply_address():
    mail = parse_email(sample("01-rea-epping.eml"))
    result = to_extraction({"is_lead": True, "source": "realestate.com.au", "name": "X", "email": None}, mail)
    assert result.lead is None and "email" in result.reason


def test_schema_is_strict_and_complete():
    assert LEAD_SCHEMA["additionalProperties"] is False
    assert sorted(LEAD_SCHEMA["required"]) == sorted(LEAD_SCHEMA["properties"])


def test_claude_extractor_request_and_parsing(monkeypatch):
    """No network: the SDK client is replaced, the request shape and parsing are checked."""
    sent = {}

    class FakeMessages:
        def create(self, **kwargs):
            sent.update(kwargs)
            payload = {"is_lead": True, "source": "Domain", "name": "Oliver Grant", "email": "oliver.grant@example.com",
                       "phone": None, "listing_hint": "Chatswood apartment", "message": "Dogs ok?", "budget_min": None, "budget_max": None}
            return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(payload))])

    extractor = ClaudeExtractor.__new__(ClaudeExtractor)
    extractor._client = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages()))
    extractor._model = "anthropic.claude-opus-5-5"

    result = extractor.extract(parse_email(sample("02-domain-chatswood.eml")))

    assert result.lead.email == "oliver.grant@example.com"
    assert sent["model"] == "anthropic.claude-opus-5-5"
    assert sent["output_config"]["format"] == {"type": "json_schema", "schema": LEAD_SCHEMA}
    assert "not instructions" in sent["system"]
    assert "tool_choice" not in sent and "thinking" not in sent


def test_claude_extractor_constructs_bedrock_client_with_fallback():
    with mock_aws():  # fake credentials for SigV4 setup; nothing is sent
        e = ClaudeExtractor(REGION)
    assert type(e._client).__name__ == "AnthropicBedrockMantle"


# --- the pipeline -----------------------------------------------------------------------------


def test_lead_goes_to_the_crm_once_even_if_delivered_twice(ledger):
    fake = FakeCrm()
    crm = CrmClient("http://crm.test/api", "tok", opener=fake)

    first = process_email(sample("01-rea-epping.eml"), "inbox/01", ledger, RuleExtractor(), crm)
    again = process_email(sample("04-duplicate-of-01.eml"), "inbox/04", ledger, RuleExtractor(), crm)

    assert first.status == "processed" and first.crm_reference == "ENQ-00001"
    assert again.status == "duplicate"
    assert len(fake.requests) == 1
    req = fake.requests[0]
    assert req["url"] == "http://crm.test/api/integrations/leads" and req["auth"] == "Bearer tok"
    assert req["body"]["external_id"] == "rea-20261119-0001@realestate.com.au"
    item = ledger.get("rea-20261119-0001@realestate.com.au")
    assert item["status"] == "processed" and "ENQ-00001" in item["details"]


def test_non_leads_are_recorded_as_ignored(ledger):
    crm = CrmClient("http://crm.test/api", "tok", opener=FakeCrm())
    out = process_email(sample("03-newsletter.eml"), "inbox/03", ledger, RuleExtractor(), crm)
    assert out.status == "ignored"
    assert ledger.get("news-8812@propertyweekly.example")["status"] == "ignored"


def test_rejected_data_is_not_retried(ledger):
    crm = CrmClient("http://crm.test/api", "tok", opener=FakeCrm(status=422))
    out = process_email(sample("01-rea-epping.eml"), "inbox/01", ledger, RuleExtractor(), crm)
    assert out.status == "rejected"
    assert ledger.get("rea-20261119-0001@realestate.com.au")["status"] == "rejected"


def test_crm_outage_fails_and_a_retry_can_succeed(ledger):
    down = CrmClient("http://crm.test/api", "tok", opener=FakeCrm(status=503))
    with pytest.raises(Exception, match="503"):
        process_email(sample("01-rea-epping.eml"), "inbox/01", ledger, RuleExtractor(), down)
    assert ledger.get("rea-20261119-0001@realestate.com.au")["status"] == "failed"

    up = CrmClient("http://crm.test/api", "tok", opener=FakeCrm())
    assert process_email(sample("01-rea-epping.eml"), "inbox/01", ledger, RuleExtractor(), up).status == "processed"


def test_extractor_error_marks_failed(ledger):
    class Broken:
        def extract(self, mail) -> Extraction:
            raise RuntimeError("bedrock throttled")

    crm = CrmClient("http://crm.test/api", "tok", opener=FakeCrm())
    with pytest.raises(RuntimeError):
        process_email(sample("02-domain-chatswood.eml"), "inbox/02", ledger, Broken(), crm)
    assert ledger.get("dom-20261119-0042@domain.com.au")["status"] == "failed"


def test_lambda_handler_reads_s3_and_ssm(monkeypatch):
    from leads import handler

    with mock_aws():
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket="inbound", CreateBucketConfiguration={"LocationConstraint": REGION})
        s3.put_object(Bucket="inbound", Key="inbox/a b.eml", Body=sample("01-rea-epping.eml"))
        boto3.resource("dynamodb", region_name=REGION).create_table(
            TableName="ledger",
            KeySchema=[{"AttributeName": "message_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "message_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        boto3.client("ssm", region_name=REGION).put_parameter(Name="/rex/crm-token", Value="secret-tok", Type="SecureString")
        for k, v in {"AWS_REGION": REGION, "LEDGER_TABLE": "ledger", "CRM_TOKEN_PARAM": "/rex/crm-token",
                     "CRM_API_URL": "http://crm.test/api", "EXTRACTOR": "rules"}.items():
            monkeypatch.setenv(k, v)
        monkeypatch.delenv("CRM_TOKEN", raising=False)
        handler._deps.cache_clear()
        fake = FakeCrm()
        monkeypatch.setattr("leads.crm.urllib.request.urlopen", lambda req, timeout: fake(req, timeout))

        event = {"Records": [{"s3": {"bucket": {"name": "inbound"}, "object": {"key": "inbox/a+b.eml"}}}]}
        out = handler.lambda_handler(event, None)

    assert out["results"][0]["status"] == "processed"
    assert fake.requests[0]["auth"] == "Bearer secret-tok"
    handler._deps.cache_clear()


def test_without_a_crm_the_lead_is_extracted_and_recorded(ledger):
    out = process_email(sample("01-rea-epping.eml"), "inbox/01", ledger, RuleExtractor(), None)

    assert out.status == "extracted"
    item = ledger.get("rea-20261119-0001@realestate.com.au")
    assert item["status"] == "extracted" and "mia.chen@example.com" in item["details"]
