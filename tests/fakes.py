"""Deterministic stand-ins for model providers. Nothing here touches the network."""

import hashlib
import math
import re

from app.providers import Document, Embeddings
from ingest.sources import Source


def bag_of_words_vector(text: str, dimensions: int) -> list[float]:
    """Hash each word to a signed position; texts sharing words end up close together."""
    vector = [0.0] * dimensions
    for word in re.findall(r"\w+", text.lower()):
        digest = hashlib.sha256(word.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += 1.0 if digest[4] % 2 else -1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector] if any(vector) else [1.0] + [0.0] * (dimensions - 1)


class FakeEmbedder:
    """Bag-of-words embeddings. failures are raised, in order, by the next embed_documents calls."""

    def __init__(self, dimensions: int = 768, failures: list[Exception] | None = None):
        self.model = "fake-embedding"
        self.dimensions = dimensions
        self.failures = list(failures or [])
        self.document_calls: list[list[Document]] = []

    @staticmethod
    def tokens(text: str) -> int:
        return len(re.findall(r"\w+", text))

    async def embed_documents(self, documents: list[Document]) -> Embeddings:
        self.document_calls.append(documents)
        if self.failures:
            raise self.failures.pop(0)
        texts = [f"{d.title} {d.text}" for d in documents]
        return Embeddings(
            vectors=[bag_of_words_vector(t, self.dimensions) for t in texts],
            tokens=sum(self.tokens(t) for t in texts),
        )

    async def embed_query(self, query: str) -> Embeddings:
        return Embeddings([bag_of_words_vector(query, self.dimensions)], self.tokens(query))


def sample_source(source_id: str, language: str, jurisdiction: str) -> Source:
    return Source(
        id=source_id,
        title=f"Sample {source_id}",
        jurisdiction=jurisdiction,
        language=language,
        version="1",
        published="2026-01",
        url=f"https://example.test/{source_id}",
        format="pdf",
        sha256="0" * 64,
        parser="shgm_pdf",
        citation_url=f"https://example.test/{source_id}.pdf",
    )
