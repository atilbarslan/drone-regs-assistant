"""Gemini implementation of the provider interfaces, with google-genai's async client."""

import contextvars
import json
import re

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field

from app.providers import (
    Document,
    Embeddings,
    EmptyResponse,
    Generation,
    RateLimited,
    TransientError,
)

# google-genai does not expose the token count of an embedding call, but the raw response
# carries it (usageMetadata.promptTokenCount). A response hook on the SDK's httpx client reads
# it into this context variable; it runs in the same task as the call, so concurrent calls
# each see their own value.
_last_usage: contextvars.ContextVar[int | None] = contextvars.ContextVar("usage", default=None)


async def _capture_usage(response: httpx.Response) -> None:
    if response.status_code != 200 or not response.url.path.endswith(":batchEmbedContents"):
        return
    await response.aread()
    usage = json.loads(response.content).get("usageMetadata") or {}
    _last_usage.set(usage.get("promptTokenCount"))


def document_prompt(document: Document) -> str:
    # Retrieval document format recommended for gemini-embedding-2
    # (ai.google.dev/gemini-api/docs/embeddings, "Task types with Embeddings 2").
    return f"title: {document.title or 'none'} | text: {document.text}"


def query_prompt(query: str) -> str:
    return f"task: search result | query: {query}"


def classify_error(exc: errors.APIError) -> Exception:
    """Map an API error to RateLimited, TransientError, or the original error."""
    if exc.code == 429:
        details = exc.details if isinstance(exc.details, dict) else {}
        violations = []
        retry_after = None
        for detail in details.get("error", {}).get("details", []):
            violations += detail.get("violations", [])
            if delay := detail.get("retryDelay"):
                match = re.fullmatch(r"([\d.]+)s", delay)
                retry_after = float(match.group(1)) if match else None
        quota_ids = [v.get("quotaId", "") for v in violations]
        daily = any("PerDay" in q for q in quota_ids)
        return RateLimited(
            f"429 {', '.join(quota_ids) or exc.message}", daily=daily, retry_after=retry_after
        )
    if exc.code in (500, 502, 503, 504):
        return TransientError(f"{exc.code} {exc.status}")
    return exc


class GeminiEmbedder:
    def __init__(self, api_key: str, model: str, dimensions: int, timeout_seconds: float):
        self.model = model
        self.dimensions = dimensions
        options = types.HttpOptions(
            timeout=int(timeout_seconds * 1000),
            async_client_args={"event_hooks": {"response": [_capture_usage]}},
        )
        # Retries are handled by the callers (they know about quotas); the SDK's default is to
        # not retry, which is kept.
        self._client = genai.Client(api_key=api_key, http_options=options).aio

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _embed(self, prompts: list[str]) -> Embeddings:
        _last_usage.set(None)
        try:
            response = await self._client.models.embed_content(
                model=self.model,
                # One Content per text: gemini-embedding-2 merges plain strings in one call
                # into a single aggregated embedding.
                contents=[types.Content(parts=[types.Part.from_text(text=p)]) for p in prompts],
                config=types.EmbedContentConfig(output_dimensionality=self.dimensions),
            )
        except errors.APIError as exc:
            raise classify_error(exc) from exc
        except httpx.TransportError as exc:
            raise TransientError(type(exc).__name__) from exc
        vectors = [list(e.values or []) for e in response.embeddings or []]
        if len(vectors) != len(prompts) or any(len(v) != self.dimensions for v in vectors):
            raise ValueError(f"expected {len(prompts)} embeddings of {self.dimensions} dimensions")
        return Embeddings(vectors=vectors, tokens=_last_usage.get())

    async def embed_documents(self, documents: list[Document]) -> Embeddings:
        return await self._embed([document_prompt(d) for d in documents])

    async def embed_query(self, query: str) -> Embeddings:
        return await self._embed([query_prompt(query)])


class _Answer(BaseModel):
    """The JSON shape the model must return (structured output)."""

    answerable: bool = Field(description="False if the passages do not contain the answer.")
    answer: str = Field(description="The answer, with [n] citations.")


class GeminiLLM:
    """Answers with generateContent: one stateless request per question, nothing stored by the
    API between calls (the Interactions API stores requests unless store=false is set)."""

    def __init__(
        self, api_key: str, model: str, timeout_seconds: float, thinking_level: str | None = None
    ):
        self.model = model
        self.thinking_level = thinking_level
        options = types.HttpOptions(timeout=int(timeout_seconds * 1000))
        self._client = genai.Client(api_key=api_key, http_options=options).aio

    async def aclose(self) -> None:
        await self._client.aclose()

    async def generate(self, system: str, prompt: str) -> Generation:
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=_Answer,
            # No tools are passed; disabling automatic function calling also silences the
            # SDK's warning about it.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            # Temperature stays at the default: Google advises against lowering it for
            # Gemini 3 models. Thinking stays at the model default unless configured.
            thinking_config=(
                types.ThinkingConfig(thinking_level=self.thinking_level.upper())
                if self.thinking_level
                else None
            ),
        )
        try:
            response = await self._client.models.generate_content(
                model=self.model, contents=prompt, config=config
            )
        except errors.APIError as exc:
            raise classify_error(exc) from exc
        except httpx.TransportError as exc:
            raise TransientError(type(exc).__name__) from exc
        parsed = response.parsed
        if not isinstance(parsed, _Answer):
            reason = response.candidates[0].finish_reason if response.candidates else None
            raise EmptyResponse(f"no structured answer (finish_reason={reason})")
        usage = response.usage_metadata
        return Generation(
            answerable=parsed.answerable,
            answer=parsed.answer,
            prompt_tokens=usage.prompt_token_count if usage else None,
            output_tokens=usage.candidates_token_count if usage else None,
            thinking_tokens=usage.thoughts_token_count if usage else None,
        )
