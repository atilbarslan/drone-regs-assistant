"""POST /api/ask: answer a question about drone rules with a structured, cited answer."""

import logging
import time
from datetime import UTC, datetime
from typing import Literal

import psycopg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.answer import Metrics, answer_question
from app.limits import next_daily_reset
from app.messages import (
    limit_message,
    not_configured_message,
    provider_error_message,
    provider_quota_message,
)
from app.providers import EmptyResponse, RateLimited, TransientError
from app.schema import Compare, DependsOn, Section
from app.search import SearchParams

logger = logging.getLogger(__name__)

router = APIRouter()

QUESTION_MAX_CHARS = 500
FACT_MAX_CHARS = 200
MAX_FACTS = 6

ModeName = Literal["EU", "TR", "compare"]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=QUESTION_MAX_CHARS)
    lang: Literal["tr", "en"]
    # The mode the user chose; null means: detect it from the question.
    mode: ModeName | None = None
    # The mode the interface shows now, used when mode is null and the question names no
    # jurisdiction. Without it the server falls back to "EU".
    default_mode: ModeName | None = None
    # Choices the user picked from "depends_on" options, e.g. "The drone has a camera".
    facts: list[str] = Field(default_factory=list, max_length=MAX_FACTS)

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question is empty")
        return value

    @field_validator("facts")
    @classmethod
    def short_facts(cls, values: list[str]) -> list[str]:
        values = [v.strip() for v in values if v.strip()]
        if any(len(v) > FACT_MAX_CHARS for v in values):
            raise ValueError(f"each fact can be at most {FACT_MAX_CHARS} characters")
        return list(dict.fromkeys(values))


class CitationOut(BaseModel):
    n: int
    source_title: str
    source_version: str
    jurisdiction: Literal["EU", "TR"]
    section_ref: str
    page: int | None
    excerpt: str
    url: str


class MatchedTermOut(BaseModel):
    text: str
    jurisdiction: Literal["EU", "TR"]


class DetectedOut(BaseModel):
    # What the question itself points to; null when it names no jurisdiction.
    mode: ModeName | None
    matched_terms: list[MatchedTermOut]


class AskResponse(BaseModel):
    mode: ModeName  # the mode the answer follows
    mode_source: Literal["explicit", "detected", "default"]
    detected: DetectedOut
    refused: bool
    depends_on: list[DependsOn]
    sections: list[Section]
    not_in_sources: list[str]
    compare: Compare | None
    follow_ups: list[str]
    citations: list[CitationOut]
    # The same answer as plain text, for simple clients.
    answer: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    retry_after_seconds: int | None = None
    resets_at: datetime | None = None


def _error(status: int, body: ErrorResponse) -> JSONResponse:
    headers = {"Retry-After": str(body.retry_after_seconds)} if body.retry_after_seconds else None
    return JSONResponse(body.model_dump(mode="json"), status_code=status, headers=headers)


def client_ip(request: Request) -> str:
    # Behind a proxy, uvicorn's --proxy-headers puts the original client address here.
    return request.client.host if request.client else "unknown"


LOG_FIELDS = (
    "lang", "jurisdiction", "mode", "mode_source", "top_k", "facts_count", "retrieved_chunks",
    "cited_chunks", "sections_count", "depends_on_count", "embedding_model", "generation_model",
    "embedding_tokens", "prompt_tokens", "output_tokens", "thinking_tokens", "retrieval_ms",
    "generation_ms", "total_ms", "refused", "error_type",
)  # fmt: skip
INSERT_LOG = (
    f"INSERT INTO request_log ({', '.join(LOG_FIELDS)}) "
    f"VALUES ({', '.join(f'%({f})s' for f in LOG_FIELDS)})"
)


async def log_request(request: Request, metrics: Metrics) -> None:
    """Write the request_log row. A failure here is logged and never fails the request."""
    try:
        async with request.app.state.pool.connection() as conn:
            await conn.execute(INSERT_LOG, {f: getattr(metrics, f) for f in LOG_FIELDS})
    except psycopg.Error as exc:
        logger.warning("request_log insert failed (%s)", type(exc).__name__)


@router.post(
    "/api/ask",
    response_model=AskResponse,
    responses={429: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def ask(body: AskRequest, request: Request):
    state = request.app.state
    started = time.perf_counter()
    metrics = Metrics(lang=body.lang)
    try:
        refusal = state.limiter.check(client_ip(request))
        if refusal is not None:
            metrics.error_type = f"rate_limited:{refusal.scope}"
            return _error(
                429,
                ErrorResponse(
                    error="rate_limited",
                    message=limit_message(refusal, body.lang),
                    retry_after_seconds=refusal.retry_after,
                    resets_at=refusal.resets_at,
                ),
            )
        if state.embedder is None or state.llm is None:
            metrics.error_type = "not_configured"
            message = not_configured_message(body.lang)
            return _error(503, ErrorResponse(error="not_configured", message=message))

        settings = state.settings
        result = await answer_question(
            body.question,
            body.lang,
            mode=body.mode,
            default_mode=body.default_mode,
            facts=body.facts,
            pool=state.pool,
            embedder=state.embedder,
            llm=state.llm,
            params=SearchParams.from_settings(settings),
            list_top_k=settings.search_top_k_list,
            compare_per_side=settings.search_compare_per_side,
            core_sections=settings.search_core_sections,
            metrics=metrics,
            debug_dir=settings.debug_raw_dir if settings.debug_raw else None,
        )
        answer = result.answer
        detected_mode = {"EU": "EU", "TR": "TR", "both": "compare"}.get(
            result.detection.jurisdiction
        )
        return AskResponse(
            mode=result.mode,
            mode_source=result.mode_source,
            detected=DetectedOut(
                mode=detected_mode,
                matched_terms=[
                    MatchedTermOut(text=t.text, jurisdiction=t.jurisdiction)
                    for t in result.detection.matched_terms
                ],
            ),
            refused=result.refused,
            depends_on=answer.depends_on,
            sections=answer.sections,
            not_in_sources=answer.not_in_sources,
            compare=answer.compare,
            follow_ups=answer.follow_ups,
            citations=[CitationOut(**vars(c)) for c in result.citations],
            answer=result.text,
        )
    except RateLimited as exc:
        metrics.error_type = f"provider_quota:{'daily' if exc.daily else 'minute'}"
        resets_at = next_daily_reset(datetime.now(UTC))
        wait = int(resets_at.timestamp() - time.time()) if exc.daily else int(exc.retry_after or 60)
        return _error(
            503,
            ErrorResponse(
                error="provider_quota",
                message=provider_quota_message(exc.daily, resets_at, body.lang),
                retry_after_seconds=max(1, wait),
                resets_at=resets_at if exc.daily else None,
            ),
        )
    except (TransientError, EmptyResponse) as exc:
        metrics.error_type = f"provider_error:{type(exc).__name__}"
        message = provider_error_message(body.lang)
        return _error(503, ErrorResponse(error="provider_error", message=message))
    except psycopg.Error as exc:
        metrics.error_type = f"database:{type(exc).__name__}"
        message = provider_error_message(body.lang)
        return _error(503, ErrorResponse(error="database_error", message=message))
    except Exception as exc:
        metrics.error_type = f"internal:{type(exc).__name__}"
        raise
    finally:
        metrics.total_ms = round((time.perf_counter() - started) * 1000)
        await log_request(request, metrics)
