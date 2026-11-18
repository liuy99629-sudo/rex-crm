"""The assistant reuses the CRM login: a request is allowed when Laravel accepts its Sanctum token."""

import hashlib
import time
from typing import Any, Awaitable, Callable

import httpx

TokenVerifier = Callable[[str], Awaitable[dict[str, Any] | None]]


class LaravelTokenVerifier:
    """Calls GET /api/auth/me with the caller's token. Results are cached briefly per token."""

    def __init__(self, laravel_url: str, ttl_seconds: int = 60) -> None:
        self._url = f"{laravel_url}/api/auth/me"
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._client = httpx.AsyncClient(timeout=5.0)

    async def __call__(self, token: str) -> dict[str, Any] | None:
        key = hashlib.sha256(token.encode()).hexdigest()
        hit = self._cache.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        resp = await self._client.get(self._url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        if resp.status_code != 200:
            self._cache.pop(key, None)
            return None
        user = resp.json()
        self._cache[key] = (time.monotonic() + self._ttl, user)
        return user

    async def aclose(self) -> None:
        await self._client.aclose()
