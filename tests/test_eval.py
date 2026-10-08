"""The evaluation tooling (eval/): no network; fake providers and the test database."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.providers import Embeddings, Generation, RateLimited
from eval import report, score
from eval.run import (
    DEFAULT_QUESTIONS,
    CachedEmbedder,
    Calls,
    DailyQuota,
    PacedLLM,
    QueryCache,
    Spacing,
    ask_like_the_page,
    load_questions,
)
from tests.conftest import make_settings
from tests.fakes import FakeEmbedder, FakeLLM, section, structured

pytestmark = pytest.mark.anyio


# --- the question set -----------------------------------------------------------------------


def test_question_set_shape():
    questions = load_questions(DEFAULT_QUESTIONS)

    assert len(questions) == 36
    assert len({q["id"] for q in questions}) == 36
    for q in questions:
        assert q["lang"] in ("tr", "en")
        assert q["jurisdiction"] and set(q["jurisdiction"]) <= set(score.ACCEPTED_MODE)
        assert isinstance(q["should_refuse"], bool)
        assert [f["id"] for f in q["facts"]] == [f"m{i}" for i in range(1, len(q["must"]) + 1)] + [
            f"s{i}" for i in range(1, len(q["should"]) + 1)
        ]
    assert sum(q["should_refuse"] for q in questions) == 4


# --- the same path as POST /api/ask ---------------------------------------------------------


async def test_ask_like_the_page_matches_the_api(db, loaded):
    reply = structured(
        sections=[section("İzin", "Kırmızı bölgede izin gerekir.", [1])],
        not_in_sources=["Yok."],
    )
    settings = make_settings()
    question = "Türkiye'de kırmızı bölgede uçuş için izin gerekir mi?"

    app = create_app(settings, embedder=FakeEmbedder(), llm=FakeLLM(reply))
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            body = {"question": question, "lang": "tr", "mode": None, "default_mode": "TR"}
            api = (await client.post("/api/ask", json={**body, "facts": []})).json()
        api_llm = app.state.llm
        eval_llm = FakeLLM(reply)
        result, metrics = await ask_like_the_page(
            question,
            "tr",
            settings=settings,
            pool=app.state.pool,
            embedder=FakeEmbedder(),
            llm=eval_llm,
        )

    # Same prompt (so the same passages, in the same order) and the same answer.
    assert eval_llm.calls == api_llm.calls
    assert (result.mode, result.mode_source) == (api["mode"], api["mode_source"])
    assert result.text == api["answer"]
    assert [c.section_ref for c in result.citations] == [c["section_ref"] for c in api["citations"]]
    assert metrics.top_k == settings.search_top_k
    assert [h.section_ref for h in result.hits][:1] == ["Madde 12"]


# --- scoring --------------------------------------------------------------------------------


async def scored(db, loaded, reply, question="Türkiye'de kırmızı bölgede izin gerekir mi?"):
    settings = make_settings()
    app = create_app(settings, embedder=FakeEmbedder(), llm=FakeLLM(reply))
    async with app.router.lifespan_context(app):
        return await ask_like_the_page(
            question,
            "tr",
            settings=settings,
            pool=app.state.pool,
            embedder=FakeEmbedder(),
            llm=FakeLLM(reply),
        )


async def test_detection_retrieval_and_citation_places(db, loaded):
    cases = [{"condition": "Kırmızı", "verdict": "İZİN", "text": "İzin gerekir.", "citations": [1]}]
    reply = structured(sections=[section("Bölge", None, [1], cases), section("Lisans", "P1.", [2])])
    result, _ = await scored(db, loaded, reply)
    expected = [
        {"source_id": "tr-sample", "section_ref": "Madde 12"},
        {"source_id": "tr-sample", "section_ref": "Madde 99"},
    ]

    assert score.detection(result, ["TR"])["ok"] is True
    assert score.detection(result, ["none"])["ok"] is False
    assert score.retrieval(result, expected)["ranks"] == {"Madde 12": 1, "Madde 99": None}
    places = score.citations(result, expected)
    assert places["places"]["Madde 12"] == ["case 'Bölge / Kırmızı'"]
    assert places["any_expected_cited"] is True


async def test_refusal_criteria(db, loaded):
    refused, _ = await scored(db, loaded, structured(answerable=False, sections=[]))
    answered, _ = await scored(db, loaded, structured())

    assert score.refusal(refused, True, explained=False) == {
        "should_refuse": True,
        "refused_flag": True,
        "empty_and_explained": False,
        "false_refusal": False,
    }
    assert score.refusal(refused, True, explained=True)["empty_and_explained"] is True
    assert score.refusal(refused, False, None)["false_refusal"] is True
    assert score.refusal(answered, False, None)["false_refusal"] is False


def test_quotes_must_be_verbatim():
    text = "Azami yükseklik 120 m’dir [1].\n- Kameralı — KAYIT: Kayıt gerekir [2]."
    assert score.quote_in("Azami yükseklik 120 m'dir", text)  # quote marks normalised
    assert score.quote_in("Azami   yükseklik 120 m’dir…", text)  # spaces, trailing ellipsis
    assert not score.quote_in("Azami yükseklik 150 m'dir", text)
    assert not score.quote_in("", text)


async def test_judge_verdicts_are_checked(db, loaded):
    cases = [
        {"condition": "Kameralı", "verdict": "KAYIT", "text": "Kayıt gerekir.", "citations": [1]}
    ]
    reply = structured(sections=[section("Kayıt", None, [1], cases), section("Yaş", "18.", [1])])
    result, _ = await scored(db, loaded, reply)
    facts = [
        {"id": "m1", "kind": "must", "text": "kayıt gerekir"},
        {"id": "m2", "kind": "must", "text": "yaş 18"},
        {"id": "m3", "kind": "must", "text": "yaş 16"},
        {"id": "s1", "kind": "should", "text": "sigorta"},
    ]
    verdicts = [
        {"id": "m1", "status": "present", "quote": "Kayıt gerekir."},
        {"id": "m2", "status": "present", "quote": "Yaş 18 olmalıdır"},  # not in the answer
        {"id": "m3", "status": "contradicted", "quote": "18."},
        {"id": "s1", "status": "absent", "quote": ""},
    ]

    checked = {f["id"]: f for f in score.checked_facts(facts, verdicts, result.text, result.answer)}

    assert (checked["m1"]["status"], checked["m1"]["note"]) == ("present", "case içinde")
    assert checked["m2"]["status"] == "unverified"
    assert checked["m3"]["status"] == "contradicted"
    assert checked["s1"]["status"] == "absent"
    assert score.coverage(list(checked.values()), "must") == score.Coverage(1, 0, 1, 1, 3)


# --- quota handling -------------------------------------------------------------------------


async def test_question_embeddings_are_cached(tmp_path):
    calls = Calls()
    cache = QueryCache(tmp_path / "cache.json")
    embedder = CachedEmbedder(FakeEmbedder(), cache, 768, calls)

    first = await embedder.embed_query("soru")
    again = CachedEmbedder(FakeEmbedder(), QueryCache(tmp_path / "cache.json"), 768, calls)
    second = await again.embed_query("soru")

    assert isinstance(first, Embeddings) and first.vectors == second.vectors
    assert (calls.embedding, calls.embedding_cached) == (1, 1)


class Failing:
    model = "fake"

    def __init__(self, errors):
        self.errors = list(errors)

    async def generate(self, system, prompt, schema):
        if self.errors:
            raise self.errors.pop(0)
        return Generation(data={}, prompt_tokens=1, output_tokens=1, thinking_tokens=None)


async def test_daily_quota_stops_and_minute_limit_retries():
    calls = Calls()
    minute = RateLimited("minute", daily=False, retry_after=0)
    paced = PacedLLM(Failing([minute]), Spacing(10**6), calls, "generation")
    await paced.generate("s", "p", None)
    assert (calls.generation, calls.retries) == (2, 1)

    daily = PacedLLM(
        Failing([RateLimited("day", daily=True, retry_after=None)]), Spacing(10**6), calls, "judge"
    )
    with pytest.raises(DailyQuota):
        await daily.generate("s", "p", None)


# --- report ---------------------------------------------------------------------------------


def fake_result(qid, **overrides):
    base = {
        "id": qid,
        "detection": {"ok": True, "detected_mode": "TR", "mode": "TR"},
        "retrieval": {"ranks": {"Madde 12": 3}, "count": 8, "list_question": False},
        "citations": {"any_expected_cited": True},
        "refusal": {
            "should_refuse": False,
            "refused_flag": False,
            "empty_and_explained": None,
            "false_refusal": False,
        },
        "facts": [
            {"id": "m1", "kind": "must", "text": "x", "status": "present", "quote": "x", "note": ""}
        ],
        "depends_on": {"questions": [], "already_given": []},
        "latency": {"mode": "TR", "generation_ms": 3000, "prompt_tokens": 100, "output_tokens": 10},
    }
    base.update(overrides)
    return base


def test_error_classes():
    assert report.classes(fake_result("ok")) == []
    missing = [
        {"id": "m1", "kind": "must", "text": "x", "status": "absent", "quote": "", "note": ""}
    ]
    not_retrieved = {"ranks": {"Madde 12": None}, "count": 8, "list_question": False}
    assert report.classes(fake_result("a", facts=missing, retrieval=not_retrieved)) == ["getirme"]
    assert report.classes(fake_result("b", facts=missing)) == ["üretim"]
    assert "tespit" in report.classes(fake_result("c", detection={"ok": False}))
    redundant = {"questions": ["Kamera?"], "already_given": [{"number": 1}]}
    assert report.classes(fake_result("d", depends_on=redundant)) == ["depends_on"]


def test_report_renders_a_run():
    run = {
        "config": {"name": "A", "generation_model": "m"},
        "path": "eval/results/x.json",
        "status": "complete",
        "calls": {"embedding": 1, "generation": 2, "judge": 2},
        "results": [fake_result("tr-01"), {"id": "tr-02", "error": "generation: timeout"}],
    }
    text = report.write([run], run)
    assert "| Tespit doğru | 1/1 |" in text
    assert "tr-02 | hata: generation: timeout" in text
