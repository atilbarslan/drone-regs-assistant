"""POST /api/ask end to end: fake embedder and LLM, the real test database. No network."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.limits import Limits, RateLimiter
from app.main import create_app
from app.providers import RateLimited, TransientError
from tests.conftest import make_settings
from tests.fakes import FakeEmbedder, FakeLLM

pytestmark = pytest.mark.anyio


@asynccontextmanager
async def ask_client(
    llm, *, limiter=None, ip="198.51.100.1", embedder="fake"
) -> AsyncIterator[AsyncClient]:
    app = create_app(
        make_settings(),
        embedder=FakeEmbedder() if embedder == "fake" else embedder,
        llm=llm,
        limiter=limiter,
    )
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app, client=(ip, 50000))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def last_log(db) -> dict:
    cur = await db.execute("SELECT row_to_json(r) FROM request_log r ORDER BY id DESC LIMIT 1")
    return (await cur.fetchone())[0]


@pytest.fixture
async def clean_log(db):
    await db.execute("TRUNCATE request_log")


async def test_answer_with_checked_citations(db, loaded, clean_log):
    llm = FakeLLM("Kırmızı bölgede uçuş izne tabidir [1]. Uydurma bir iddia [9].")
    question = "Türkiye'de kırmızı bölgede uçuş için izin gerekir mi?"

    async with ask_client(llm) as client:
        response = await client.post("/api/ask", json={"question": question, "lang": "tr"})

    assert response.status_code == 200
    body = response.json()
    assert body["refused"] is False
    assert body["jurisdiction"] == "TR"
    assert body["matched_terms"] == [
        {"text": "Türkiye", "jurisdiction": "TR"},
        {"text": "kırmızı bölge", "jurisdiction": "TR"},
    ]
    assert body["answer"] == (
        "Bu cevap Türkiye mevzuatına göredir (sorudaki 'Türkiye', 'kırmızı bölge' ifadelerinden)."
        "\n\nKırmızı bölgede uçuş izne tabidir [1]. Uydurma bir iddia."
    )
    [citation] = body["citations"]
    assert citation["n"] == 1
    assert citation["section_ref"] == "Madde 12"
    assert citation["page"] == 8
    assert citation["url"] == "https://example.test/tr-sample.pdf#page=8"
    assert citation["source_title"] == "Sample tr-sample"
    assert citation["excerpt"].startswith("Kırmızı bölgede uçuş izne tabidir.")
    # Only Turkish passages were sent to the model.
    system, prompt = llm.calls[0]
    assert "about Turkish rules" in system
    assert "European Union |" not in prompt and "Türkiye |" in prompt


async def test_eu_question_in_english_uses_only_eu_passages(db, loaded, clean_log):
    llm = FakeLLM("The remote pilot keeps away from people [1].")

    async with ask_client(llm) as client:
        response = await client.post(
            "/api/ask", json={"question": "Can I fly over people in Germany?", "lang": "en"}
        )

    body = response.json()
    assert body["jurisdiction"] == "EU"
    assert body["answer"].startswith(
        "This answer is based on EU rules (from 'Germany' in your question).\n\n"
    )
    assert "Türkiye |" not in llm.calls[0][1]


async def test_question_without_jurisdiction_searches_both_sides(db, loaded, clean_log):
    llm = FakeLLM("Soruda yetki alanı yok. Türkiye'de: ... [1]. AB'de: ... [5].")

    async with ask_client(llm) as client:
        response = await client.post(
            "/api/ask", json={"question": "Pilot için hangi kurallar var?", "lang": "tr"}
        )

    body = response.json()
    assert body["jurisdiction"] == "none"
    assert body["matched_terms"] == []
    assert not body["answer"].startswith("Bu cevap")  # the model says it, not a fixed line
    system, prompt = llm.calls[0]
    assert "does not say whether it is about the EU or Türkiye" in system
    # Balanced: both Turkish passages first, then EU passages fill the remaining places.
    lines = [line for line in prompt.splitlines() if line.startswith("[")]
    sides = [line.split(" | ")[0].split("] ")[1] for line in lines]
    assert sides[:2] == ["Türkiye", "Türkiye"] and set(sides[2:]) == {"European Union"}
    assert [c["n"] for c in body["citations"]] == [1, 5]


async def test_both_jurisdictions(db, loaded, clean_log):
    async with ask_client(FakeLLM("Karşılaştırma [1][3].")) as client:
        response = await client.post(
            "/api/ask", json={"question": "AB ile Türkiye kurallarını karşılaştır", "lang": "tr"}
        )

    body = response.json()
    assert body["jurisdiction"] == "both"
    assert body["answer"].startswith("Bu cevap AB ve Türkiye mevzuatına göredir")


async def test_not_answerable_is_refused_without_citations(db, loaded, clean_log):
    llm = FakeLLM("Verilen kaynaklarda bu sorunun cevabı yok [1].", answerable=False)

    async with ask_client(llm) as client:
        response = await client.post(
            "/api/ask", json={"question": "SHGM'ye göre drone sigortası ne kadar?", "lang": "tr"}
        )

    body = response.json()
    assert body["refused"] is True
    assert body["citations"] == []
    assert body["answer"].endswith("Verilen kaynaklarda bu sorunun cevabı yok.")


async def test_answer_without_valid_citation_is_not_shown(db, loaded, clean_log):
    llm = FakeLLM("Kesinlikle serbest, hiçbir kural yok [12].")

    async with ask_client(llm) as client:
        response = await client.post(
            "/api/ask", json={"question": "Türkiye'de gece uçuşu serbest mi?", "lang": "tr"}
        )

    body = response.json()
    assert body["refused"] is True
    assert body["citations"] == []
    assert "dayandırılamadığı için gösterilmiyor" in body["answer"]
    assert "Kesinlikle serbest" not in body["answer"]
    assert (await last_log(db))["error_type"] == "uncited_answer"


async def test_no_passages_skips_the_model(db, clean_log):
    # The database has no chunks: nothing to answer from, so no generation request is made.
    llm = FakeLLM()

    async with ask_client(llm) as client:
        response = await client.post(
            "/api/ask", json={"question": "Türkiye'de lisans", "lang": "tr"}
        )

    assert response.json()["refused"] is True
    assert llm.calls == []


async def test_request_log_has_figures_but_no_question_or_address(db, loaded, clean_log):
    question = "Türkiye'de kırmızı bölge için gizli-ifade-123 nedir?"

    async with ask_client(FakeLLM("Cevap [1].")) as client:
        await client.post("/api/ask", json={"question": question, "lang": "tr"})

    row = await last_log(db)
    assert row["lang"] == "tr" and row["jurisdiction"] == "TR"
    assert row["retrieved_chunks"] == 2 and row["cited_chunks"] == 1
    assert row["embedding_model"] == "fake-embedding" and row["generation_model"] == "fake-llm"
    assert row["embedding_tokens"] > 0 and row["prompt_tokens"] > 0
    assert row["retrieval_ms"] is not None and row["generation_ms"] is not None
    assert row["total_ms"] >= 0 and row["refused"] is False and row["error_type"] is None
    serialized = json.dumps(row, ensure_ascii=False)
    assert "gizli-ifade-123" not in serialized
    assert "198.51.100.1" not in serialized


# --- limits and errors ---------------------------------------------------------------------


async def test_per_ip_minute_limit(db, loaded, clean_log):
    async with ask_client(FakeLLM("Cevap [1].")) as client:
        statuses = []
        for _ in range(4):
            r = await client.post("/api/ask", json={"question": "Türkiye'de lisans", "lang": "tr"})
            statuses.append(r.status_code)

    assert statuses == [200, 200, 200, 429]
    body = r.json()
    assert body["error"] == "rate_limited"
    assert "dakikada en fazla 3 soru" in body["message"]
    assert int(r.headers["Retry-After"]) == body["retry_after_seconds"] > 0
    assert (await last_log(db))["error_type"] == "rate_limited:ip_minute"


async def test_global_minute_limit_counts_all_addresses(db, loaded, clean_log):
    limiter = RateLimiter(Limits(2, 300, 3, 20))
    statuses = []
    for i in range(3):
        async with ask_client(FakeLLM("Cevap [1]."), limiter=limiter, ip=f"203.0.113.{i}") as c:
            r = await c.post("/api/ask", json={"question": "EU pilot age", "lang": "en"})
            statuses.append(r.status_code)

    assert statuses == [200, 200, 429]
    assert "too many questions" in r.json()["message"]


async def test_daily_limit_message_shows_reset_time(db, loaded, clean_log):
    noon = datetime(2026, 10, 7, 12, 0, tzinfo=UTC).timestamp()
    limiter = RateLimiter(Limits(12, 300, 3, 1), clock=lambda: noon)

    async with ask_client(FakeLLM("Cevap [1]."), limiter=limiter) as client:
        await client.post("/api/ask", json={"question": "EU pilot", "lang": "tr"})
        r = await client.post("/api/ask", json={"question": "EU pilot", "lang": "tr"})

    assert r.status_code == 429
    body = r.json()
    assert "Bugünkü soru hakkınız doldu (günde 1 soru)" in body["message"]
    assert "08.10.2026 10:00 (Türkiye saati)" in body["message"]
    assert body["resets_at"] == "2026-10-08T07:00:00Z"


@pytest.mark.parametrize(
    ("lang", "daily", "expected"),
    [
        ("tr", True, "Yapay zekâ servisinin günlük kotası doldu"),
        ("en", True, "The AI service's daily quota is used up"),
        ("tr", False, "Yapay zekâ servisi şu anda yoğun"),
        ("en", False, "The AI service is busy right now"),
    ],
)
async def test_gemini_quota_error_gives_a_clear_message(
    db, loaded, clean_log, lang, daily, expected
):
    llm = FakeLLM(failures=[RateLimited("429", daily=daily, retry_after=None if daily else 30)])

    async with ask_client(llm) as client:
        r = await client.post("/api/ask", json={"question": "EU pilot", "lang": lang})

    assert r.status_code == 503
    assert r.json()["error"] == "provider_quota"
    assert r.json()["message"].startswith(expected)
    kind = "daily" if daily else "minute"
    assert (await last_log(db))["error_type"] == f"provider_quota:{kind}"


async def test_provider_error_is_503(db, loaded, clean_log):
    llm = FakeLLM(failures=[TransientError("503 UNAVAILABLE")])

    async with ask_client(llm) as client:
        r = await client.post("/api/ask", json={"question": "EU pilot", "lang": "en"})

    assert r.status_code == 503
    assert r.json()["error"] == "provider_error"


async def test_not_configured_without_providers(db, clean_log):
    async with ask_client(None, embedder=None) as client:
        r = await client.post("/api/ask", json={"question": "EU pilot", "lang": "tr"})

    assert r.status_code == 503
    assert r.json()["error"] == "not_configured"


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "", "lang": "tr"},
        {"question": "   ", "lang": "tr"},
        {"question": "x" * 501, "lang": "tr"},
        {"question": "Soru", "lang": "de"},
        {"lang": "tr"},
    ],
)
async def test_invalid_requests_are_rejected(db, payload):
    async with ask_client(FakeLLM()) as client:
        r = await client.post("/api/ask", json=payload)

    assert r.status_code == 422
