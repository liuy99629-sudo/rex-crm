"""Vector store for RAG. Production: the CRM's own PostgreSQL with the pgvector extension
(no extra database to run). Tests: an in-memory store with the same interface."""

import math
from dataclasses import dataclass
from typing import Protocol

from psycopg_pool import AsyncConnectionPool


@dataclass(frozen=True)
class Document:
    kind: str  # property | contact | deal_note
    source_id: int
    title: str
    text: str
    content_hash: str


@dataclass(frozen=True)
class Hit:
    kind: str
    source_id: int
    title: str
    text: str
    score: float  # cosine similarity, 1 = identical


class VectorStore(Protocol):
    async def hashes(self) -> dict[tuple[str, int], str]: ...
    async def upsert(self, docs: list[Document], vectors: list[list[float]]) -> None: ...
    async def delete(self, keys: list[tuple[str, int]]) -> None: ...
    async def search(self, vector: list[float], limit: int, kinds: list[str] | None = None) -> list[Hit]: ...


class PgVectorStore:
    """Table ai_documents is owned by this service (created on start, never touched by Laravel)."""

    def __init__(self, pool: AsyncConnectionPool, dimensions: int) -> None:
        self._pool = pool
        self._dimensions = dimensions

    async def setup(self) -> None:
        async with self._pool.connection() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS ai_documents (
                    kind text NOT NULL,
                    source_id bigint NOT NULL,
                    title text NOT NULL,
                    body text NOT NULL,
                    content_hash text NOT NULL,
                    embedding vector({self._dimensions}) NOT NULL,
                    updated_at timestamptz NOT NULL DEFAULT now(),
                    PRIMARY KEY (kind, source_id)
                )
                """
            )

    async def hashes(self) -> dict[tuple[str, int], str]:
        async with self._pool.connection() as conn:
            rows = await (await conn.execute("SELECT kind, source_id, content_hash FROM ai_documents")).fetchall()
        return {(r[0], r[1]): r[2] for r in rows}

    async def upsert(self, docs: list[Document], vectors: list[list[float]]) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(
                    """
                    INSERT INTO ai_documents (kind, source_id, title, body, content_hash, embedding, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s::vector, now())
                    ON CONFLICT (kind, source_id) DO UPDATE SET
                        title = EXCLUDED.title, body = EXCLUDED.body, content_hash = EXCLUDED.content_hash,
                        embedding = EXCLUDED.embedding, updated_at = now()
                    """,
                    [(d.kind, d.source_id, d.title, d.text, d.content_hash, _literal(v)) for d, v in zip(docs, vectors)],
                )

    async def delete(self, keys: list[tuple[str, int]]) -> None:
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.executemany("DELETE FROM ai_documents WHERE kind = %s AND source_id = %s", keys)

    async def search(self, vector: list[float], limit: int, kinds: list[str] | None = None) -> list[Hit]:
        sql = "SELECT kind, source_id, title, body, 1 - (embedding <=> %s::vector) AS score FROM ai_documents"
        params: list[object] = [_literal(vector)]
        if kinds:
            sql += " WHERE kind = ANY(%s)"
            params.append(kinds)
        sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
        params += [_literal(vector), limit]
        async with self._pool.connection() as conn:
            rows = await (await conn.execute(sql, params)).fetchall()
        return [Hit(r[0], r[1], r[2], r[3], float(r[4])) for r in rows]


def _literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


class InMemoryStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, int], tuple[Document, list[float]]] = {}

    async def hashes(self) -> dict[tuple[str, int], str]:
        return {k: d.content_hash for k, (d, _) in self.rows.items()}

    async def upsert(self, docs: list[Document], vectors: list[list[float]]) -> None:
        for d, v in zip(docs, vectors):
            self.rows[(d.kind, d.source_id)] = (d, v)

    async def delete(self, keys: list[tuple[str, int]]) -> None:
        for k in keys:
            self.rows.pop(k, None)

    async def search(self, vector: list[float], limit: int, kinds: list[str] | None = None) -> list[Hit]:
        scored = [
            Hit(d.kind, d.source_id, d.title, d.text, _cosine(vector, v))
            for d, v in self.rows.values()
            if not kinds or d.kind in kinds
        ]
        return sorted(scored, key=lambda h: h.score, reverse=True)[:limit]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
