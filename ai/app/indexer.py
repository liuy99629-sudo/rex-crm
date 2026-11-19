"""Keeps the vector store in step with the CRM: embeds new or changed records, drops deleted ones.
Content hashes make each run cheap when nothing changed."""

import asyncio
from dataclasses import dataclass

from .crm import CrmRepository
from .embeddings import Embedder
from .store import VectorStore


@dataclass(frozen=True)
class IndexStats:
    embedded: int
    deleted: int
    unchanged: int


async def sync_index(crm: CrmRepository, store: VectorStore, embedder: Embedder) -> IndexStats:
    docs = await crm.documents()
    existing = await store.hashes()

    changed = [d for d in docs if existing.get((d.kind, d.source_id)) != d.content_hash]
    current = {(d.kind, d.source_id) for d in docs}
    stale = [k for k in existing if k not in current]

    if changed:
        texts = [f"{d.title}. {d.text}" for d in changed]
        # Embedding is CPU-bound: keep the event loop free for requests.
        vectors = await asyncio.to_thread(embedder.embed, texts)
        await store.upsert(changed, vectors)
    if stale:
        await store.delete(stale)

    return IndexStats(embedded=len(changed), deleted=len(stale), unchanged=len(docs) - len(changed))
