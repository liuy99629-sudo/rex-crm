"""Raw email (as SES stores it in S3) -> the parts the extractor needs."""

import email
import html
import re
from dataclasses import dataclass
from email import policy
from email.utils import parseaddr

MAX_BODY_CHARS = 20_000  # lead emails are short; anything longer is truncated before the model sees it


@dataclass(frozen=True)
class ParsedEmail:
    message_id: str
    from_name: str
    from_email: str
    reply_to: str | None
    subject: str
    body: str


def _html_to_text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style).*?</\1>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", text)).strip()


def parse_email(raw: bytes) -> ParsedEmail:
    msg = email.message_from_bytes(raw, policy=policy.default)
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        body = ""
    elif part.get_content_type() == "text/html":
        body = _html_to_text(part.get_content())
    else:
        body = part.get_content().strip()

    from_name, from_email = parseaddr(str(msg.get("From", "")))
    _, reply_to = parseaddr(str(msg.get("Reply-To", "")))
    message_id = str(msg.get("Message-ID", "")).strip().strip("<>")
    if not message_id:
        # Without a Message-ID, a hash of the content still makes processing idempotent.
        import hashlib

        message_id = "sha256-" + hashlib.sha256(raw).hexdigest()

    return ParsedEmail(
        message_id=message_id,
        from_name=from_name,
        from_email=from_email.lower(),
        reply_to=reply_to.lower() or None,
        subject=str(msg.get("Subject", "")).strip(),
        body=body[:MAX_BODY_CHARS],
    )
