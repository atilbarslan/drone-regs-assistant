"""POST /api/ask: answer a question about drone rules, with citations."""

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
from app.search import SearchParams

logger = logging.getLogger(__name__)

router = APIRouter()

QUESTION_MAX_CHARS = 500


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=QUESTION_MAX_CHARS)
    lang: Literal["tr", "en"]

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question is empty")
        return value


class CitationOut(BaseModel):
    n: int
    source_title: str
    section_ref: str
    page: int | None
    excerpt: str
    url: str


class MatchedTermOut(BaseModel):
    text: str
    jurisdiction: Literal["EU", "TR"]


class AskResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    refused: bool
    jurisdiction: Literal["EU", "TR", "both", "none"]
    matched_terms: list[MatchedTermOut]
    # The first line of answer when it names the jurisdiction; clients that show their own
    # label can strip it. None for "none".
    jurisdiction_line: str | None


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


INSERT_LOG = """
INSERT INTO request_log (
    lang, jurisdiction, retrieved_chunks, cited_chunks, embedding_model, generation_model,
    embedding_tokens, prompt_tokens, output_tokens, thinking_tokens, retrieval_ms,
    generation_ms, total_ms, refused, error_type
) VALUES (
    %(lang)s, %(jurisdiction)s, %(retrieved_chunks)s, %(cited_chunks)s, %(embedding_model)s,
    %(generation_model)s, %(embedding_tokens)s, %(prompt_tokens)s, %(output_tokens)s,
    %(thinking_tokens)s, %(retrieval_ms)s, %(generation_ms)s, %(total_ms)s, %(refused)s,
    %(error_type)s
)
"""


async def log_request(request: Request, metrics: Metrics) -> None:
    """Write the request_log row. A failure here is logged and never fails the request."""
    try:
        async with request.app.state.pool.connection() as conn:
            await conn.execute(INSERT_LOG, vars(metrics))
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

        result = await answer_question(
            body.question,
            body.lang,
            pool=state.pool,
            embedder=state.embedder,
            llm=state.llm,
            params=SearchParams.from_settings(state.settings),
            metrics=metrics,
        )
        return AskResponse(
            answer=result.answer,
            citations=[CitationOut(**vars(c)) for c in result.citations],
            refused=result.refused,
            jurisdiction=result.jurisdiction,
            matched_terms=[
                MatchedTermOut(text=t.text, jurisdiction=t.jurisdiction)
                for t in result.matched_terms
            ],
            jurisdiction_line=result.jurisdiction_line,
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
