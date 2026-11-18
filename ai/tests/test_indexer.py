from app.crm import make_document
from app.indexer import sync_index


class CountingEmbedder:
    def __init__(self, inner):
        self.inner = inner
        self.dimensions = inner.dimensions
        self.texts: list[str] = []

    def embed(self, texts):
        self.texts += texts
        return self.inner.embed(texts)


async def test_first_run_embeds_everything(crm, store, embedder):
    stats = await sync_index(crm, store, embedder)

    assert (stats.embedded, stats.deleted, stats.unchanged) == (3, 0, 0)
    assert set(store.rows) == {("property", 1), ("property", 2), ("contact", 5)}


async def test_second_run_only_embeds_what_changed_and_drops_deleted(crm, store, embedder):
    await sync_index(crm, store, embedder)
    counting = CountingEmbedder(embedder)

    crm.docs = [
        crm.docs[0],  # unchanged
        make_document("property", 2, "City apartment", "apartment with a new rooftop pool"),  # edited
        # contact 5 deleted
    ]
    stats = await sync_index(crm, store, counting)

    assert (stats.embedded, stats.deleted, stats.unchanged) == (1, 1, 1)
    assert counting.texts == ["City apartment. apartment with a new rooftop pool"]
    assert ("contact", 5) not in store.rows


async def test_nothing_changed_embeds_nothing(crm, store, embedder):
    await sync_index(crm, store, embedder)
    counting = CountingEmbedder(embedder)

    stats = await sync_index(crm, store, counting)

    assert stats.embedded == 0 and counting.texts == []
