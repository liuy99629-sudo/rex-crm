"""Rex AI service: "Ask Rex" assistant + RAG index. Served under /api/ai/* (nginx and the
Ingress route that prefix here; everything else under /api goes to Laravel)."""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .agent import LlmClient, ask, build_agent
from .auth import TokenVerifier
from .crm import CrmRepository
from .embeddings import Embedder
from .indexer import sync_index
from .store import VectorStore
from .tools import ToolContext

log = logging.getLogger("rex.ai")


@dataclass
class Services:
    crm: CrmRepository
    store: VectorStore
    embedder: Embedder
    verify_token: TokenVerifier
    llm: LlmClient | None  # None when no API key is configured
    model: str
    effort: str
    reindex_interval: int = 0


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AskRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)


def create_app(
    services: Services, on_startup: list[Any] | None = None, on_shutdown: list[Any] | None = None
) -> FastAPI:
    agent = (
        build_agent(services.llm, ToolContext(services.crm, services.store, services.embedder), services.model, services.effort)
        if services.llm
        else None
    )
    index_lock = asyncio.Lock()

    async def reindex() -> dict[str, int]:
        async with index_lock:
            stats = await sync_index(services.crm, services.store, services.embedder)
        log.info("index sync: %s", stats)
        return stats.__dict__

    async def reindex_loop() -> None:
        while True:
            try:
                await reindex()
            except Exception:  # noqa: BLE001 - keep the loop alive, try again next interval
                log.exception("index sync failed")
            await asyncio.sleep(services.reindex_interval)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        for start in on_startup or []:
            await start()
        task =asyncio.create_task(reindex_loop()) if services.reindex_interval > 0 else None
        yield
        if task:
            task.cancel()
        for close in on_shutdown or []:
            await close()

    app = FastAPI(title="Rex AI", lifespan=lifespan, docs_url="/api/ai/docs", openapi_url="/api/ai/openapi.json")

    @app.exception_handler(HTTPException)
    async def laravel_shaped_errors(_: Request, exc: HTTPException) -> JSONResponse:
        # Same error shape as the Laravel API ({"message": ...}) so the frontend client shows it as-is.
        return JSONResponse({"message": exc.detail}, status_code=exc.status_code)

    async def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Unauthenticated.")
        try:
            user = await services.verify_token(authorization[7:].strip())
        except Exception as exc:  # Laravel unreachable: not the caller's fault, don't log them out
            log.warning("token check failed: %s", exc)
            raise HTTPException(503, "Could not verify your login right now. Try again shortly.") from exc
        if not user:
            raise HTTPException(401, "Unauthenticated.")
        return user

    @app.get("/api/ai/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "llm_configured": agent is not None}

    @app.post("/api/ai/ask")
    async def ask_endpoint(body: AskRequest, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if agent is None:
            raise HTTPException(503, "The AI assistant is not configured: set ANTHROPIC_API_KEY for the ai service.")
        if body.messages[-1].role != "user":
            raise HTTPException(422, "The last message must be from the user.")
        log.info("ask by user %s", user.get("id"))
        return await ask(agent, [m.model_dump() for m in body.messages])

    @app.post("/api/ai/reindex")
    async def reindex_endpoint(_: dict[str, Any] = Depends(current_user)) -> dict[str, int]:
        return await reindex()

    return app


def production_app() -> FastAPI:
    """Wire real dependencies. Used by uvicorn: `uvicorn app.main:production_app --factory`."""
    from psycopg_pool import AsyncConnectionPool

    from .auth import LaravelTokenVerifier
    from .config import load_settings
    from .crm import PgCrmRepository
    from .embeddings import SentenceTransformerEmbedder
    from .llm import AnthropicLlm
    from .store import PgVectorStore

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    pool = AsyncConnectionPool(settings.database_url, min_size=1, max_size=5, open=False)
    embedder = SentenceTransformerEmbedder(settings.embedding_model)
    store = PgVectorStore(pool, embedder.dimensions)
    verifier = LaravelTokenVerifier(settings.laravel_url)
    if not settings.llm_configured:
        log.warning("ANTHROPIC_API_KEY is not set: /api/ai/ask will answer 503 until it is.")

    async def open_pool() -> None:
        await pool.open()
        await store.setup()

    return create_app(
        Services(
            crm=PgCrmRepository(pool),
            store=store,
            embedder=embedder,
            verify_token=verifier,
            llm=AnthropicLlm(settings.anthropic_api_key) if settings.anthropic_api_key else None,
            model=settings.model,
            effort=settings.effort,
            reindex_interval=settings.reindex_interval,
        ),
        on_startup=[open_pool],
        on_shutdown=[verifier.aclose, pool.close],
    )
