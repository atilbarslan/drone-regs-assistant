"""Interfaces the app uses for model providers, so tests can swap in deterministic fakes."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Document:
    """A text to embed for retrieval, with the title the embedding prompt can use."""

    title: str
    text: str


@dataclass(frozen=True)
class Embeddings:
    vectors: list[list[float]]
    tokens: int | None  # input tokens as reported by the provider, if it reports them


class Embedder(Protocol):
    model: str
    dimensions: int

    async def embed_documents(self, documents: list[Document]) -> Embeddings: ...

    async def embed_query(self, query: str) -> Embeddings: ...


class ProviderError(Exception):
    """A provider call failed in a way the caller may want to handle."""


class RateLimited(ProviderError):
    """The provider refused the call because a quota is used up.

    daily: the per-day quota (wait for the reset) rather than a per-minute one (retry soon).
    retry_after: seconds the provider asked to wait, if it said.
    """

    def __init__(self, message: str, *, daily: bool, retry_after: float | None):
        super().__init__(message)
        self.daily = daily
        self.retry_after = retry_after


class TransientError(ProviderError):
    """A temporary failure (server error, timeout) that is worth retrying."""


@dataclass(frozen=True)
class Generation:
    answerable: bool  # the model's judgement that the passages contain the answer
    answer: str
    prompt_tokens: int | None
    output_tokens: int | None
    thinking_tokens: int | None


class LLM(Protocol):
    model: str

    async def generate(self, system: str, prompt: str) -> Generation: ...


class EmptyResponse(ProviderError):
    """The model returned no usable answer (blocked, cut off, or not the expected JSON)."""
