from datetime import UTC, datetime

import pytest

from app.providers import Document, RateLimited, TransientError
from ingest.embed import Pacer, embed_pending, make_batches, next_daily_reset, sync_source
from tests.conftest import make_settings
from tests.fakes import FakeEmbedder, sample_source

pytestmark = pytest.mark.anyio


def chunks(n: int, prefix: str = "Sample text") -> list[dict]:
    return [
        {
            "section_ref": f"Madde {i + 1}",
            "heading": f"Başlık {i + 1}",
            "page": i + 1,
            "chunk_index": 0,
            "language": "tr",
            "text": f"{prefix} {i}",
        }
        for i in range(n)
    ]


class FakeClock:
    """A clock and sleep that move time forward instead of waiting."""

    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def pacer(clock: FakeClock, tokens: int = 10**9, requests: int = 10**9) -> Pacer:
    return Pacer(tokens, requests, clock=clock, sleep=clock.sleep)


async def count(db, where: str = "TRUE") -> int:
    cur = await db.execute(f"SELECT count(*) FROM chunks WHERE {where}")
    return (await cur.fetchone())[0]


# --- sync ----------------------------------------------------------------------------------------


async def test_sync_inserts_then_keeps_unchanged_chunks(db):
    src = sample_source("tr-sample", "tr", "TR")

    first = await sync_source(db, src, chunks(3))
    second = await sync_source(db, src, chunks(3))

    assert (first.inserted, first.kept, first.deleted) == (3, 0, 0)
    assert (second.inserted, second.kept, second.deleted) == (0, 3, 0)
    assert await count(db) == 3


async def test_sync_replaces_changed_chunks_and_keeps_other_embeddings(db):
    src = sample_source("tr-sample", "tr", "TR")
    await sync_source(db, src, chunks(3))
    await embed_pending(db, FakeEmbedder(), make_settings(), pacer(FakeClock()))
    changed = chunks(3)
    changed[1]["text"] = "Edited text"

    stats = await sync_source(db, src, changed)

    assert (stats.inserted, stats.kept, stats.deleted) == (1, 2, 1)
    assert await count(db, "embedding IS NOT NULL") == 2
    assert await count(db, "embedding IS NULL AND text = 'Edited text'") == 1


# --- embedding -----------------------------------------------------------------------------------


async def test_embeds_in_batches_and_skips_embedded_chunks_on_the_next_run(db):
    await sync_source(db, sample_source("tr-sample", "tr", "TR"), chunks(5))
    embedder = FakeEmbedder()
    settings = make_settings(embed_batch_max_items=2)

    first = await embed_pending(db, embedder, settings, pacer(FakeClock()))
    second = await embed_pending(db, embedder, settings, pacer(FakeClock()))

    assert (first.embedded, first.batches) == (5, 3)
    assert first.tokens > 0
    assert [len(call) for call in embedder.document_calls] == [2, 2, 1]
    # The title passed to the embedder combines reference and heading.
    assert embedder.document_calls[0][0] == Document("Madde 1 Başlık 1", "Sample text 0")
    assert (second.embedded, second.batches) == (0, 0)
    assert await count(db, "embedding_model = 'fake-embedding'") == 5


async def test_reembeds_chunks_from_another_model(db):
    await sync_source(db, sample_source("tr-sample", "tr", "TR"), chunks(2))
    await embed_pending(db, FakeEmbedder(), make_settings(), pacer(FakeClock()))
    other = FakeEmbedder()
    other.model = "another-model"

    stats = await embed_pending(db, other, make_settings(), pacer(FakeClock()))

    assert stats.embedded == 2


async def test_retries_after_per_minute_quota_error(db):
    await sync_source(db, sample_source("tr-sample", "tr", "TR"), chunks(2))
    embedder = FakeEmbedder(failures=[RateLimited("per minute", daily=False, retry_after=7.0)])
    clock = FakeClock()

    stats = await embed_pending(db, embedder, make_settings(), pacer(clock))

    assert (stats.embedded, stats.retries, stats.remaining) == (2, 1, 0)
    # Waited at least as long as the API asked, rather than the shorter backoff.
    assert clock.sleeps == [7.0]


async def test_backs_off_exponentially_on_transient_errors(db):
    await sync_source(db, sample_source("tr-sample", "tr", "TR"), chunks(1))
    embedder = FakeEmbedder(failures=[TransientError("503"), TransientError("503")])
    clock = FakeClock()
    settings = make_settings(embed_backoff_base_seconds=2.0)

    stats = await embed_pending(db, embedder, settings, pacer(clock))

    assert stats.embedded == 1
    assert clock.sleeps == [2.0, 4.0]


async def test_gives_up_after_max_retries_and_reports_what_is_left(db):
    await sync_source(db, sample_source("tr-sample", "tr", "TR"), chunks(3))
    embedder = FakeEmbedder(failures=[TransientError("503")] * 3)
    settings = make_settings(embed_max_retries=2, embed_batch_max_items=1)

    stats = await embed_pending(db, embedder, settings, pacer(FakeClock()))

    assert (stats.embedded, stats.remaining) == (0, 3)
    assert stats.errors and "gave up" in stats.errors[0]


async def test_stops_on_daily_quota_and_resumes_on_the_next_run(db):
    await sync_source(db, sample_source("tr-sample", "tr", "TR"), chunks(4))
    settings = make_settings(embed_batch_max_items=1)
    daily = RateLimited("per day", daily=True, retry_after=None)
    # Two batches succeed, the third hits the daily quota.
    embedder = FakeEmbedder()
    original = embedder.embed_documents

    async def fail_on_third(documents):
        if len(embedder.document_calls) == 2:
            embedder.document_calls.append(documents)
            raise daily
        return await original(documents)

    embedder.embed_documents = fail_on_third

    stopped = await embed_pending(db, embedder, settings, pacer(FakeClock()))
    resumed = await embed_pending(db, FakeEmbedder(), settings, pacer(FakeClock()))

    assert stopped.stopped_for_daily_quota
    assert (stopped.embedded, stopped.remaining) == (2, 2)
    assert await count(db, "embedding IS NOT NULL") == 4
    assert (resumed.embedded, resumed.remaining) == (2, 0)


# --- pacing and batching -------------------------------------------------------------------------


async def test_pacer_waits_when_tokens_per_minute_would_be_exceeded():
    clock = FakeClock()
    p = pacer(clock, tokens=1000)

    await p.acquire(600, requests=1)
    clock.now = 10.0
    await p.acquire(600, requests=1)  # 1200 > 1000: wait until the first call is 60 s old

    assert clock.now == pytest.approx(60.05)
    assert p.waited == pytest.approx(50.05)


async def test_pacer_counts_each_text_as_a_request():
    clock = FakeClock()
    p = pacer(clock, requests=90)

    await p.acquire(10, requests=60)
    await p.acquire(10, requests=40)  # 100 > 90

    assert clock.sleeps and clock.now >= 60


async def test_pacer_uses_reported_tokens_for_later_calls():
    clock = FakeClock()
    p = pacer(clock, tokens=1000)

    record = await p.acquire(900, requests=1)
    record[1] = 300  # the API reported fewer tokens than estimated
    await p.acquire(600, requests=1)

    assert clock.sleeps == []


def test_batches_respect_item_and_token_limits():
    rows = [(i, Document("t", "x" * 400)) for i in range(7)]  # ~105 estimated tokens each

    batches = make_batches(rows, max_items=3, max_tokens=250)

    assert [len(b) for b in batches] == [2, 2, 2, 1]
    assert [r[0] for b in batches for r in b] == list(range(7))


@pytest.mark.parametrize(
    ("now", "reset"),
    [
        # 11:22 in California (PDT, UTC-7): next midnight is 07:00 UTC the next day.
        (datetime(2026, 10, 6, 18, 22, tzinfo=UTC), datetime(2026, 10, 7, 7, 0, tzinfo=UTC)),
        # In winter (PST, UTC-8) midnight is 08:00 UTC.
        (datetime(2026, 12, 1, 9, 0, tzinfo=UTC), datetime(2026, 12, 2, 8, 0, tzinfo=UTC)),
    ],
)
def test_next_daily_reset_is_midnight_pacific(now, reset):
    assert next_daily_reset(now) == reset
