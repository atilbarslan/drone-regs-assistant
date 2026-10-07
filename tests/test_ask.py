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
from tests.fakes import FakeEmbedder, FakeLLM, section, structured

pytestmark = pytest.mark.anyio


@asynccontextmanager
async def ask_client(
    llm, *, limiter=None, ip="198.51.100.1", embedder="fake", settings=None
) -> AsyncIterator[AsyncClient]:
    app = create_app(
        settings or make_settings(),
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


def passage_sides(prompt: str) -> list[str]:
    """The jurisdiction label of each passage given to the model, in order."""
    lines = [line for line in prompt.splitlines() if line.startswith("[")]
    return [line.split(" | ")[0].split("] ")[1] for line in lines]


async def ask(client, question, lang="tr", **fields):
    return await client.post("/api/ask", json={"question": question, "lang": lang, **fields})


# --- modes ---------------------------------------------------------------------------------


async def test_detected_mode_and_structured_answer(db, loaded, clean_log):
    llm = FakeLLM(
        structured(
            sections=[section("İzin", "Kırmızı bölgede uçuş izne tabidir [1].", citations=[])],
            not_in_sources=["İl bazında ek kural kaynaklarda yok."],
            follow_ups=["Yeşil bölgede ne gerekir?"],
        )
    )

    async with ask_client(llm) as client:
        r = await ask(client, "Türkiye'de kırmızı bölgede uçuş için izin gerekir mi?")

    assert r.status_code == 200
    body = r.json()
    assert (body["mode"], body["mode_source"], body["refused"]) == ("TR", "detected", False)
    assert body["detected"] == {
        "mode": "TR",
        "matched_terms": [
            {"text": "Türkiye", "jurisdiction": "TR"},
            {"text": "kırmızı bölge", "jurisdiction": "TR"},
        ],
    }
    assert body["sections"] == [
        {
            "topic": "İzin",
            "text": "Kırmızı bölgede uçuş izne tabidir.",
            "cases": [],
            "citations": [1],
        }
    ]
    assert body["not_in_sources"] == ["İl bazında ek kural kaynaklarda yok."]
    assert body["follow_ups"] == ["Yeşil bölgede ne gerekir?"]
    assert body["compare"] is None
    [citation] = body["citations"]
    assert citation == {
        "n": 1,
        "source_title": "Sample tr-sample",
        "source_version": "1",
        "jurisdiction": "TR",
        "section_ref": "Madde 12",
        "page": 8,
        # The sentence that supports the section, not simply the start of the passage.
        "excerpt": "Kırmızı bölgede uçuş izne tabidir. Yeşil bölgede izin gerekmez.",
        "url": "https://example.test/tr-sample.pdf#page=8",
    }
    # No jurisdiction sentence in the answer any more; the plain text is the sections.
    assert body["answer"].startswith("İzin\nKırmızı bölgede uçuş izne tabidir. [1]")
    assert "Bu cevap" not in body["answer"]
    assert set(passage_sides(llm.calls[0][1])) == {"Türkiye"}


async def test_explicit_mode_wins_over_the_question(db, loaded, clean_log):
    llm = FakeLLM()

    async with ask_client(llm) as client:
        body = (await ask(client, "Türkiye'de pilot lisansı", mode="EU")).json()

    assert (body["mode"], body["mode_source"]) == ("EU", "explicit")
    assert body["detected"]["mode"] == "TR"  # still reported, for the interface
    assert set(passage_sides(llm.calls[0][1])) == {"European Union"}


@pytest.mark.parametrize(("default_mode", "expected"), [("TR", "TR"), (None, "EU")])
async def test_question_without_jurisdiction_uses_the_default(
    db, loaded, clean_log, default_mode, expected
):
    llm = FakeLLM()

    async with ask_client(llm) as client:
        body = (
            await ask(client, "Pilot için hangi kurallar var?", default_mode=default_mode)
        ).json()

    assert (body["mode"], body["mode_source"]) == (expected, "default")
    assert body["detected"] == {"mode": None, "matched_terms": []}
    side = {"TR": "Türkiye", "EU": "European Union"}[expected]
    assert set(passage_sides(llm.calls[0][1])) == {side}
    assert "does not name a jurisdiction" not in llm.calls[0][0]


async def test_compare_mode_keeps_each_side_to_its_own_passages(db, loaded, clean_log):
    def reply(prompt):
        sides = passage_sides(prompt)
        tr = sides.index("Türkiye") + 1
        eu = sides.index("European Union") + 1
        return structured(
            sections=[],
            compare={
                "key_differences": ["Türkiye lisans seviyesine, AB alt kategoriye bakar."],
                "rows": [
                    {
                        "topic": "Kural",
                        "TR": {"text": "TR kuralı", "citations": [tr, eu]},
                        "EU": {"text": "AB kuralı", "citations": [eu]},
                    }
                ],
            },
        )

    llm = FakeLLM(reply)
    async with ask_client(llm) as client:
        body = (await ask(client, "AB ile Türkiye kurallarını karşılaştır")).json()

    assert (body["mode"], body["mode_source"]) == ("compare", "detected")
    assert 'Fill "compare"' in llm.calls[0][0]
    sides = passage_sides(llm.calls[0][1])
    assert sides[: sides.count("Türkiye")] == ["Türkiye"] * sides.count("Türkiye")  # TR first
    [row] = body["compare"]["rows"]
    tr_cited = [c for c in body["citations"] if c["n"] in row["TR"]["citations"]]
    eu_cited = [c for c in body["citations"] if c["n"] in row["EU"]["citations"]]
    assert {c["jurisdiction"] for c in tr_cited} == {"TR"}
    assert {c["jurisdiction"] for c in eu_cited} == {"EU"}
    assert len(row["TR"]["citations"]) == 1  # the EU passage it also cited was dropped


# --- depends_on and facts ------------------------------------------------------------------


async def test_depends_on_and_facts(db, loaded, clean_log):
    camera = {
        "question": "Kamera var mı?",
        "options": [
            {"label": "Kameralı", "fact": "The drone has a camera"},
            {"label": "Kamerasız", "fact": "The drone has no camera"},
        ],
    }
    cases = [
        {"condition": "Kameralı", "verdict": "KAYIT", "text": "Kayıt gerekir.", "citations": [1]},
        {"condition": "Kamerasız", "verdict": "GEREKMEZ", "text": "Gerekmez.", "citations": [1]},
    ]
    llm = FakeLLM(structured(depends_on=[camera], sections=[section("Kayıt", None, [], cases)]))

    async with ask_client(llm) as client:
        first = (await ask(client, "Türkiye'de 200 g drone için kurallar?")).json()
        second = (
            await ask(
                client, "Türkiye'de 200 g drone için kurallar?", facts=["The drone has a camera"]
            )
        ).json()

    assert first["depends_on"] == [camera]
    assert [c["verdict"] for c in first["sections"][0]["cases"]] == ["KAYIT", "GEREKMEZ"]
    assert "confirmed these facts" not in llm.calls[0][0]
    assert "- The drone has a camera" in llm.calls[1][0]
    # The question the user already answered is not asked again.
    assert second["depends_on"] == []


# --- retrieval size ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("question", "expected"), [("Ticari çekim için hangi belgeler gerekli?", 4), ("Gece uçuşu?", 2)]
)
async def test_list_questions_get_more_passages(db, loaded, clean_log, question, expected):
    settings = make_settings(search_top_k=2, search_top_k_list=4)

    async with ask_client(FakeLLM(), settings=settings) as client:
        await ask(client, question, mode="EU")

    log = await last_log(db)
    assert (log["top_k"], log["retrieved_chunks"]) == (expected, expected)


# --- refusals ------------------------------------------------------------------------------


async def test_nothing_related_is_refused_with_what_is_missing(db, loaded, clean_log):
    reply = structured(answerable=False, sections=[], not_in_sources=["Sigorta tutarı yok."])

    async with ask_client(FakeLLM(reply)) as client:
        body = (await ask(client, "SHGM'ye göre sigorta yıllık kaç lira?")).json()

    assert body["refused"] is True
    assert (body["sections"], body["citations"]) == ([], [])
    assert body["not_in_sources"] == ["Sigorta tutarı yok."]


async def test_answer_without_valid_citation_is_not_shown(db, loaded, clean_log):
    reply = structured(sections=[section("Kural", "Kesinlikle serbest.", citations=[12])])

    async with ask_client(FakeLLM(reply)) as client:
        body = (await ask(client, "Türkiye'de gece uçuşu serbest mi?")).json()

    assert body["refused"] is True
    assert body["sections"] == []
    assert "dayandırılamadığı için gösterilmiyor" in body["not_in_sources"][0]
    assert (await last_log(db))["error_type"] == "uncited_answer"


async def test_reply_that_does_not_fit_the_schema_is_a_provider_error(db, loaded, clean_log):
    async with ask_client(FakeLLM({"sections": "not a list"})) as client:
        r = await ask(client, "Türkiye'de lisans")

    assert r.status_code == 503
    assert r.json()["error"] == "provider_error"


async def test_no_passages_skips_the_model(db, clean_log):
    llm = FakeLLM()

    async with ask_client(llm) as client:
        body = (await ask(client, "Türkiye'de lisans")).json()

    assert body["refused"] is True
    assert llm.calls == []


# --- request log ---------------------------------------------------------------------------


async def test_request_log_has_figures_but_no_question_facts_or_address(db, loaded, clean_log):
    question = "Türkiye'de kırmızı bölge için gizli-ifade-123 nedir?"

    async with ask_client(FakeLLM()) as client:
        await ask(client, question, facts=["gizli-bilgi-456"])

    row = await last_log(db)
    assert (row["lang"], row["jurisdiction"], row["mode"], row["mode_source"]) == (
        "tr", "TR", "TR", "detected",
    )  # fmt: skip
    assert (row["top_k"], row["facts_count"], row["sections_count"], row["depends_on_count"]) == (
        8, 1, 1, 0,
    )  # fmt: skip
    assert row["retrieved_chunks"] == 2 and row["cited_chunks"] == 1
    assert row["embedding_model"] == "fake-embedding" and row["generation_model"] == "fake-llm"
    assert row["embedding_tokens"] > 0 and row["prompt_tokens"] > 0
    assert row["refused"] is False and row["error_type"] is None
    serialized = json.dumps(row, ensure_ascii=False)
    for secret in ("gizli-ifade-123", "gizli-bilgi-456", "198.51.100.1"):
        assert secret not in serialized


async def test_debug_raw_writes_passages_and_raw_reply(db, loaded, clean_log, tmp_path):
    reply = structured(sections=[section("İzin", "Kırmızı bölgede izin gerekir.", [7])])
    settings = make_settings(debug_raw=True, debug_raw_dir=tmp_path / "debug")

    async with ask_client(FakeLLM(reply), settings=settings) as client:
        r = await ask(client, "Türkiye'de kırmızı bölgede izin gerekir mi?")

    assert r.status_code == 200
    (path,) = (tmp_path / "debug").iterdir()
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["question"] == "Türkiye'de kırmızı bölgede izin gerekir mi?"
    assert record["mode"] == "TR"
    assert [(p["n"], p["section_ref"], p["document_id"]) for p in record["passages"]] == [
        (1, "Madde 12", "tr-sample"),
        (2, "Madde 15", "tr-sample"),
    ]
    # The reply as the model sent it, before the server dropped the invalid citation.
    assert record["raw"]["sections"][0]["citations"] == [7]


async def test_debug_raw_is_off_by_default(db, loaded, clean_log, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    async with ask_client(FakeLLM()) as client:
        await ask(client, "Türkiye'de kırmızı bölgede izin gerekir mi?")

    assert not (tmp_path / "data").exists()


# --- limits and errors ---------------------------------------------------------------------


async def test_per_ip_minute_limit(db, loaded, clean_log):
    async with ask_client(FakeLLM()) as client:
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
        async with ask_client(FakeLLM(), limiter=limiter, ip=f"203.0.113.{i}") as c:
            r = await c.post("/api/ask", json={"question": "EU pilot age", "lang": "en"})
            statuses.append(r.status_code)

    assert statuses == [200, 200, 429]
    assert "too many questions" in r.json()["message"]


async def test_daily_limit_message_shows_reset_time(db, loaded, clean_log):
    noon = datetime(2026, 10, 7, 12, 0, tzinfo=UTC).timestamp()
    limiter = RateLimiter(Limits(12, 300, 3, 1), clock=lambda: noon)

    async with ask_client(FakeLLM(), limiter=limiter) as client:
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
        {"question": "Soru", "lang": "tr", "mode": "both"},
        {"question": "Soru", "lang": "tr", "facts": ["x" * 201]},
        {"question": "Soru", "lang": "tr", "facts": [f"f{i}" for i in range(7)]},
    ],
)
async def test_invalid_requests_are_rejected(db, payload):
    async with ask_client(FakeLLM()) as client:
        r = await client.post("/api/ask", json=payload)

    assert r.status_code == 422
