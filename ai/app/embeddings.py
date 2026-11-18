"""Text -> vector. Runs locally with a small sentence-transformers model (PyTorch, CPU),
so indexing CRM data costs nothing and the text never leaves the cluster."""

import hashlib
import math
from typing import Protocol

DIMENSIONS = 384  # all-MiniLM-L6-v2


class Embedder(Protocol):
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    dimensions = DIMENSIONS

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # heavy import (torch)

        self._model = SentenceTransformer(model_name, device="cpu")

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return [v.tolist() for v in vectors]


class HashEmbedder:
    """Deterministic bag-of-words embedder for tests: shared words -> similar vectors."""

    dimensions = DIMENSIONS

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        v = [0.0] * self.dimensions
        for word in text.lower().split():
            word = word.strip(".,!?;:()\"'")
            if word:
                v[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dimensions] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]
