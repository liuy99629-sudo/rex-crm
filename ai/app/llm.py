"""Claude client used by the agent (official Anthropic SDK)."""

from typing import Any

import anthropic


class AnthropicLlm:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def create(self, **kwargs: Any) -> Any:
        return await self._client.beta.messages.create(
            # If a safety classifier declines, the API re-runs the request on a suitable model
            # in the same call instead of returning an empty refusal.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            # The system prompt and tool list are identical on every request: cache them.
            cache_control={"type": "ephemeral"},
            **kwargs,
        )
