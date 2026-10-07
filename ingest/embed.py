"""Load the chunks into Postgres and embed the ones that have no embedding yet.

Usage: python -m ingest.embed   (after python -m ingest.build and python -m app.migrate)

1. Sync: for each source, the documents row is upserted and its chunks are matched by content
   hash. New chunks are inserted, chunks that are no longer produced are deleted, unchanged
   chunks keep their embedding.
2. Embed: chunks without an embedding for the configured model are sent in batches. Each batch
   is committed on its own, so an interrupted run resumes where it stopped.

Pacing: requests are spaced so the last 60 seconds stay under the configured tokens and
requests per minute. Tokens are estimated before a call and replaced with the count the API
reports afterwards; the estimate is scaled by the observed ratio of real to estimated tokens.

A per-minute quota error waits (as long as the API asks, or with exponential backoff) and
retries. A daily quota error stops the run and reports what is left; run it again after the
quota resets (midnight Pacific time).
"""

import asyncio
import hashlib
import json
import sys
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg

from app.config import Settings
from app.db import vector_literal
from app.providers import Document, Embedder, RateLimited, TransientError
from ingest.chunk import CHARS_PER_TOKEN
from ingest.sources import Source, load_sources

CHUNKS_DIR = Path(__file__).resolve().parent.parent / "data" / "chunks"
WINDOW_SECONDS = 60.0
HASHED_FIELDS = ("section_ref", "heading", "page", "chunk_index", "language", "text")


# --- sync ----------------------------------------------------------------------------------------


def content_hash(chunk: dict) -> str:
    payload = json.dumps([chunk[k] for k in HASHED_FIELDS], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_chunks(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@dataclass
class SyncStats:
    inserted: int = 0
    deleted: int = 0
    kept: int = 0


async def sync_source(
    conn: psycopg.AsyncConnection, source: Source, chunks: list[dict]
) -> SyncStats:
    """Make the database hold exactly these chunks for this source, keeping embeddings."""
    stats = SyncStats()
    hashes = [content_hash(c) for c in chunks]
    async with conn.transaction():
        await conn.execute(
            """
            INSERT INTO documents (id, title, jurisdiction, language, version, published,
                                   citation_url, sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                title = excluded.title, jurisdiction = excluded.jurisdiction,
                language = excluded.language, version = excluded.version,
                published = excluded.published, citation_url = excluded.citation_url,
                sha256 = excluded.sha256, updated_at = now()
            """,
            (
                source.id, source.title, source.jurisdiction, source.language, source.version,
                source.published, source.citation_url, source.sha256,
            ),
        )  # fmt: skip
        cur = await conn.execute(
            "DELETE FROM chunks WHERE document_id = %s AND NOT (content_hash = ANY(%s))",
            (source.id, hashes),
        )
        stats.deleted = cur.rowcount
        cur = await conn.execute(
            "SELECT content_hash FROM chunks WHERE document_id = %s", (source.id,)
        )
        existing = {row[0] for row in await cur.fetchall()}
        async with conn.cursor() as cur:
            await cur.executemany(
                """
                INSERT INTO chunks (document_id, ordinal, section_ref, heading, page,
                                    chunk_index, language, text, content_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id, content_hash) DO UPDATE SET ordinal = excluded.ordinal
                """,
                [
                    (
                        source.id, ordinal, c["section_ref"], c["heading"], c["page"],
                        c["chunk_index"], c["language"], c["text"], h,
                    )
                    for ordinal, (c, h) in enumerate(zip(chunks, hashes, strict=True))
                ],
            )  # fmt: skip
        stats.inserted = len(set(hashes) - existing)
        stats.kept = len(set(hashes) & existing)
    return stats


# --- pacing --------------------------------------------------------------------------------------


class Pacer:
    """Keeps the tokens and requests sent in the last 60 seconds under the given limits."""

    def __init__(
        self,
        tokens_per_minute: int,
        requests_per_minute: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.tokens_per_minute = tokens_per_minute
        self.requests_per_minute = requests_per_minute
        self.clock = clock
        self.sleep = sleep
        self.sent: deque[list[float]] = deque()  # [time, tokens, requests]
        self.waited = 0.0

    def _used(self, now: float) -> tuple[float, float]:
        while self.sent and now - self.sent[0][0] >= WINDOW_SECONDS:
            self.sent.popleft()
        return sum(s[1] for s in self.sent), sum(s[2] for s in self.sent)

    async def acquire(self, tokens: float, requests: int) -> list[float]:
        """Wait until the call fits in the window, then record it. Returns the record."""
        while True:
            now = self.clock()
            used_tokens, used_requests = self._used(now)
            fits = (
                used_tokens + tokens <= self.tokens_per_minute
                and used_requests + requests <= self.requests_per_minute
            )
            if fits or not self.sent:
                record = [now, tokens, requests]
                self.sent.append(record)
                return record
            delay = self.sent[0][0] + WINDOW_SECONDS - now + 0.05
            self.waited += delay
            await self.sleep(delay)

    async def pause(self, seconds: float) -> None:
        self.waited += seconds
        await self.sleep(seconds)


# --- embedding -----------------------------------------------------------------------------------


@dataclass
class EmbedStats:
    embedded: int = 0
    batches: int = 0
    tokens: int = 0
    estimated_tokens: int = 0
    retries: int = 0
    remaining: int = 0
    stopped_for_daily_quota: bool = False
    errors: list[str] = field(default_factory=list)


def chunk_title(section_ref: str, heading: str) -> str:
    return section_ref if heading in ("", section_ref) else f"{section_ref} {heading}"


def estimate(document: Document) -> int:
    # Prompt overhead ("title: ... | text: ") included roughly by counting the title too.
    return -(-(len(document.title) + len(document.text) + 16) // CHARS_PER_TOKEN)


def make_batches(rows: list[tuple], max_items: int, max_tokens: int) -> list[list[tuple]]:
    """Group (id, Document) rows into batches within the item and estimated-token limits."""
    batches: list[list[tuple]] = []
    current: list[tuple] = []
    tokens = 0
    for row in rows:
        cost = estimate(row[1])
        if current and (len(current) >= max_items or tokens + cost > max_tokens):
            batches.append(current)
            current, tokens = [], 0
        current.append(row)
        tokens += cost
    if current:
        batches.append(current)
    return batches


async def pending_chunks(conn: psycopg.AsyncConnection, model: str) -> list[tuple[int, Document]]:
    cur = await conn.execute(
        """
        SELECT id, section_ref, heading, text FROM chunks
        WHERE embedding IS NULL OR embedding_model <> %s
        ORDER BY document_id, ordinal
        """,
        (model,),
    )
    return [(row[0], Document(chunk_title(row[1], row[2]), row[3])) for row in await cur.fetchall()]


async def embed_pending(
    conn: psycopg.AsyncConnection, embedder: Embedder, settings: Settings, pacer: Pacer
) -> EmbedStats:
    stats = EmbedStats()
    rows = await pending_chunks(conn, embedder.model)
    batches = make_batches(rows, settings.embed_batch_max_items, settings.embed_batch_max_tokens)
    ratio = 1.0  # observed real tokens / estimated tokens, used to scale the next estimates
    done = 0
    for batch in batches:
        documents = [doc for _, doc in batch]
        estimated = sum(estimate(d) for d in documents)
        attempt = 0
        while True:
            # Each text in a batch counts as one request against the per-minute request quota.
            record = await pacer.acquire(estimated * ratio, requests=len(batch))
            try:
                result = await embedder.embed_documents(documents)
                break
            except RateLimited as exc:
                if exc.daily:
                    stats.stopped_for_daily_quota = True
                    stats.errors.append(str(exc))
                    stats.remaining = len(rows) - done
                    return stats
                error = exc
            except TransientError as exc:
                error = exc
            attempt += 1
            stats.retries += 1
            if attempt > settings.embed_max_retries:
                stats.errors.append(f"gave up after {attempt} attempts: {error}")
                stats.remaining = len(rows) - done
                return stats
            backoff = min(
                settings.embed_backoff_base_seconds * 2 ** (attempt - 1),
                settings.embed_backoff_max_seconds,
            )
            retry_after = getattr(error, "retry_after", None) or 0
            await pacer.pause(max(backoff, retry_after))

        if result.tokens is not None:
            record[1] = result.tokens
            stats.tokens += result.tokens
            stats.estimated_tokens += estimated
            ratio = stats.tokens / stats.estimated_tokens
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.executemany(
                    """
                    UPDATE chunks
                    SET embedding = %s::vector, embedding_model = %s, embedded_at = now()
                    WHERE id = %s
                    """,
                    [
                        (vector_literal(vector), embedder.model, chunk_id)
                        for (chunk_id, _), vector in zip(batch, result.vectors, strict=True)
                    ],
                )
        done += len(batch)
        stats.embedded += len(batch)
        stats.batches += 1
        print(f"  {done}/{len(rows)} chunks embedded", flush=True)
    return stats


def next_daily_reset(now: datetime) -> datetime:
    """Gemini daily quotas reset at midnight Pacific time."""
    pacific = now.astimezone(ZoneInfo("America/Los_Angeles"))
    midnight = (pacific + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(UTC)


async def main() -> int:
    from app.gemini import GeminiEmbedder

    settings = Settings()
    if settings.gemini_api_key is None:
        print("GEMINI_API_KEY is not set", file=sys.stderr)
        return 1
    embedder = GeminiEmbedder(
        settings.gemini_api_key.get_secret_value(),
        settings.gemini_embedding_model,
        settings.gemini_embedding_dimensions,
        settings.gemini_timeout_seconds,
    )
    pacer = Pacer(settings.embed_tokens_per_minute, settings.embed_requests_per_minute)
    started = time.monotonic()
    try:
        async with await psycopg.AsyncConnection.connect(
            settings.database_url.get_secret_value(), autocommit=True
        ) as conn:
            for source in load_sources():
                path = CHUNKS_DIR / f"{source.id}.jsonl"
                if not path.exists():
                    print(f"{path} is missing; run python -m ingest.build first", file=sys.stderr)
                    return 1
                s = await sync_source(conn, source, read_chunks(path))
                print(
                    f"sync {source.id}: {s.inserted} new, {s.kept} unchanged, {s.deleted} removed"
                )
            stats = await embed_pending(conn, embedder, settings, pacer)
    finally:
        await embedder.aclose()

    elapsed = time.monotonic() - started
    print(
        f"embedded {stats.embedded} chunks in {stats.batches} requests, {stats.tokens} tokens "
        f"(estimated {stats.estimated_tokens}), {stats.retries} retries, "
        f"{pacer.waited:.0f}s spent waiting, {elapsed:.0f}s total"
    )
    for error in stats.errors:
        print(f"error: {error}", file=sys.stderr)
    if stats.stopped_for_daily_quota:
        reset = next_daily_reset(datetime.now(UTC))
        print(
            f"Daily quota used up. {stats.remaining} chunks left; run this command again after "
            f"{reset:%Y-%m-%d %H:%M} UTC. Embedded chunks are kept.",
            file=sys.stderr,
        )
        return 2
    return 1 if stats.remaining else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
