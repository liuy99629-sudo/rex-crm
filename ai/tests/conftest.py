from dataclasses import dataclass, field
from typing import Any

import pytest

from app.crm import make_document
from app.embeddings import HashEmbedder
from app.store import Document, InMemoryStore


@dataclass
class Block:
    data: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        return self.data[name]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.data)


@dataclass
class Response:
    content: list[Block]
    stop_reason: str


def text(t: str) -> Block:
    return Block({"type": "text", "text": t})


def tool_use(id_: str, name: str, input_: dict[str, Any]) -> Block:
    return Block({"type": "tool_use", "id": id_, "name": name, "input": input_})


class ScriptedLlm:
    """Returns the scripted responses in order and records every request."""

    def __init__(self, *responses: Response) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Response:
        # Copy: the agent builds new lists, but be safe against later mutation.
        self.requests.append({**kwargs, "messages": [dict(m) for m in kwargs["messages"]]})
        return self.responses.pop(0)


@dataclass
class FakeCrm:
    docs: list[Document] = field(default_factory=list)
    properties: list[dict[str, Any]] = field(default_factory=list)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def documents(self) -> list[Document]:
        return list(self.docs)

    async def search_properties(self, **filters: Any) -> list[dict[str, Any]]:
        self.calls.append(("search_properties", filters))
        return [p for p in self.properties if filters.get("max_price") is None or p["price"] <= filters["max_price"]]

    async def search_contacts(self, **filters: Any) -> list[dict[str, Any]]:
        self.calls.append(("search_contacts", filters))
        return []

    async def get_deal(self, deal_id: int) -> dict[str, Any] | None:
        self.calls.append(("get_deal", {"deal_id": deal_id}))
        return {"id": 1, "title": "Purchase - Smith", "stage": "offer"} if deal_id == 1 else None

    async def pipeline_summary(self) -> list[dict[str, Any]]:
        return [{"stage": "lead", "deals": 3, "total_value": 3_000_000}]


@pytest.fixture
def crm() -> FakeCrm:
    return FakeCrm(
        docs=[
            make_document("property", 1, "Family home in Burwood", "house with a pool and large backyard"),
            make_document("property", 2, "City apartment", "apartment close to the train station, no garden"),
            make_document("contact", 5, "Jane Buyer", "buyer wants a pool for the kids"),
        ],
        properties=[
            {"id": 1, "title": "Family home in Burwood", "price": 1_500_000},
            {"id": 2, "title": "City apartment", "price": 800_000},
        ],
    )


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def embedder() -> HashEmbedder:
    return HashEmbedder()
