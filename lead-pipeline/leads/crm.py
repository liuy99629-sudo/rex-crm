"""Posts a lead to the CRM's integration endpoint with a limited token (leads:write only)."""

import json
import urllib.error
import urllib.request
from dataclasses import asdict
from typing import Any, Callable

from .extract import Lead


class CrmError(Exception):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"CRM returned {status}: {body[:300]}")
        self.status = status

    @property
    def retryable(self) -> bool:
        # 422 = the CRM rejected the data: retrying won't help. 429/5xx/network: try again later.
        return self.status == 0 or self.status == 429 or self.status >= 500


Opener = Callable[[urllib.request.Request, float], Any]


class CrmClient:
    def __init__(self, base_url: str, token: str, opener: Opener | None = None) -> None:
        self._url = base_url.rstrip("/") + "/integrations/leads"
        self._token = token
        self._open = opener or (lambda req, timeout: urllib.request.urlopen(req, timeout=timeout))

    def post_lead(self, lead: Lead, external_id: str) -> dict[str, Any]:
        body = json.dumps({**asdict(lead), "external_id": external_id}).encode()
        req = urllib.request.Request(
            self._url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json", "Authorization": f"Bearer {self._token}"},
        )
        try:
            with self._open(req, 15.0) as res:
                return json.loads(res.read() or b"{}")
        except urllib.error.HTTPError as err:
            raise CrmError(err.code, err.read().decode(errors="replace")) from err
        except urllib.error.URLError as err:
            raise CrmError(0, str(err.reason)) from err
