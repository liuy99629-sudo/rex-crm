"""Settings read from the environment (see compose.yaml and k8s/ai.yaml)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    # Laravel API, used to check the caller's Sanctum token.
    laravel_url: str
    anthropic_api_key: str | None
    model: str
    effort: str
    embedding_model: str
    # Seconds between background re-index runs (0 disables the loop).
    reindex_interval: int

    @property
    def llm_configured(self) -> bool:
        return bool(self.anthropic_api_key)


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("DATABASE_URL", "postgresql://rexcrm:secret@postgres:5432/rexcrm"),
        laravel_url=os.environ.get("LARAVEL_URL", "http://api:8080").rstrip("/"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        model=os.environ.get("AI_MODEL", "claude-opus-5-5"),
        effort=os.environ.get("AI_EFFORT", "medium"),
        embedding_model=os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        reindex_interval=int(os.environ.get("REINDEX_INTERVAL", "300")),
    )
