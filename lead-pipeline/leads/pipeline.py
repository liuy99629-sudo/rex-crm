"""One email through the pipeline: parse -> claim -> extract -> CRM -> record."""

import logging
from dataclasses import asdict, dataclass

from .crm import CrmClient, CrmError
from .email_parse import parse_email
from .extract import Extractor
from .ledger import Ledger

log = logging.getLogger("rex.leads")


@dataclass(frozen=True)
class Outcome:
    message_id: str
    status: str  # processed | ignored | duplicate | rejected
    detail: str = ""
    crm_reference: str | None = None


def process_email(raw: bytes, s3_key: str, ledger: Ledger, extractor: Extractor, crm: CrmClient | None) -> Outcome:
    """crm=None: no CRM connected yet (e.g. a cloud deploy before the CRM is hosted). The lead is
    extracted and recorded in the ledger as `extracted`, ready to replay once a CRM URL is set."""
    mail = parse_email(raw)
    if not ledger.claim(mail.message_id, s3_key):
        log.info("duplicate delivery of %s, skipping", mail.message_id)
        return Outcome(mail.message_id, "duplicate")

    try:
        result = extractor.extract(mail)
        if result.lead is None:
            ledger.finish(mail.message_id, "ignored", reason=result.reason, subject=mail.subject)
            return Outcome(mail.message_id, "ignored", result.reason)

        if crm is None:
            ledger.finish(mail.message_id, "extracted", lead=asdict(result.lead), note="no CRM connected")
            log.info("lead %s extracted (no CRM connected)", mail.message_id)
            return Outcome(mail.message_id, "extracted", "no CRM connected")

        try:
            created = crm.post_lead(result.lead, mail.message_id)
        except CrmError as err:
            if err.retryable:
                raise
            # The CRM refused the data (422): retrying would fail the same way. Record it for a person to look at.
            ledger.finish(mail.message_id, "rejected", error=str(err), lead=asdict(result.lead))
            return Outcome(mail.message_id, "rejected", str(err))

        ledger.finish(mail.message_id, "processed", lead=asdict(result.lead), crm=created)
        log.info("lead %s -> CRM %s", mail.message_id, created.get("reference"))
        return Outcome(mail.message_id, "processed", crm_reference=created.get("reference"))
    except Exception as err:
        # Mark failed (a retry may claim it again) and re-raise so Lambda retries, then dead-letters.
        ledger.finish(mail.message_id, "failed", error=f"{type(err).__name__}: {err}")
        raise
