"""Deterministic stand-ins for model providers. Nothing here touches the network."""

import hashlib
import math
import re

from app.providers import Document, Embeddings, Generation
from ingest.embed import Pacer
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


def section(topic="Kural", text="Örnek kural.", citations=(1,), cases=()) -> dict:
    return {"topic": topic, "text": text, "citations": list(citations), "cases": list(cases)}


def structured(**fields) -> dict:
    """A model reply in the StructuredAnswer shape; one cited section unless overridden."""
    reply = {"answerable": True, "sections": [section()]}
    reply.update(fields)
    return reply


class FakeLLM:
    """Returns a fixed structured reply (or one computed from the prompt) and records each
    call. failures are raised, in order, by the next calls."""

    def __init__(self, reply=None, failures=None):
        self.model = "fake-llm"
        self.reply = reply if reply is not None else structured()
        self.failures = list(failures or [])
        self.calls: list[tuple[str, str]] = []

    async def generate(self, system: str, prompt: str, schema) -> Generation:
        self.calls.append((system, prompt))
        if self.failures:
            raise self.failures.pop(0)
        data = self.reply(prompt) if callable(self.reply) else self.reply
        return Generation(
            data=data,
            prompt_tokens=len(prompt.split()),
            output_tokens=len(str(data).split()),
            thinking_tokens=None,
        )


class NoWaitPacer(Pacer):
    def __init__(self):
        async def no_sleep(_: float) -> None:
            return None

        super().__init__(10**9, 10**9, sleep=no_sleep)


# Short, self-written stand-ins shaped like the real sources.
def chunk(section_ref: str, heading: str, text: str, language: str, page: int = 1) -> dict:
    return {
        "section_ref": section_ref,
        "heading": heading,
        "page": page,
        "chunk_index": 0,
        "language": language,
        "text": text,
    }


EU_CHUNKS = [
    chunk(
        "UAS.OPEN.020",
        "Operations in subcategory A1",
        "The remote pilot keeps the aircraft away from groups of people.",
        "en",
        page=10,
    ),
    # Mentions UAS.OPEN.020 several times, so a plain word count would favour it.
    chunk(
        "AMC1 UAS.OPEN.030",
        "Operations in subcategory A2",
        "Unlike UAS.OPEN.020, which covers A1, this applies to A2. Read UAS.OPEN.020 and "
        "UAS.OPEN.020 together with the rules for the remote pilot.",
        "en",
        page=11,
    ),
    chunk(
        "UAS.OPEN.030",
        "Operations in subcategory A2",
        "The remote pilot keeps a horizontal distance of 30 metres from uninvolved people.",
        "en",
        page=11,
    ),
    chunk(
        "Article 4 (2019/947)",
        "Open category",
        "Operations are classified in the open category when the aircraft is light.",
        "en",
        page=3,
    ),
    chunk(
        "Article 40 (2019/945)",
        "Requirements for certified aircraft",
        "Aircraft in the certified category need a type certificate.",
        "en",
        page=50,
    ),
]
TR_CHUNKS = [
    chunk(
        "Madde 12",
        "Kısıtlanmış bölgeler",
        "Kırmızı bölgede uçuş izne tabidir. Yeşil bölgede izin gerekmez.",
        "tr",
        page=8,
    ),
    chunk(
        "Madde 15",
        "Pilot yetkinliği",
        "Pilot lisansı P0, P1 ve P2 seviyelerinde verilir; bölgeler için 12 nci maddeye bakınız.",
        "tr",
        page=10,
    ),
]
