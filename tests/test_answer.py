"""Pure parts of the answer step: mode, list questions, prompt, cleaning, rendering, excerpts."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.answer import (
    best_excerpt,
    build_prompt,
    clean_answer,
    is_list_question,
    render_text,
    resolve_mode,
    scrub_internal_terms,
)
from app.jurisdiction import detect
from app.limits import Refusal
from app.messages import limit_message, provider_quota_message
from app.schema import StructuredAnswer
from app.search import SearchHit
from tests.fakes import section, structured


def hit(n: int, jurisdiction: str, text: str = "") -> SearchHit:
    return SearchHit(
        n, "doc", "Doc title", jurisdiction, "https://example.test/doc.pdf", f"Madde {n}",
        "Heading", n, "tr", text or f"Passage text {n}", 1, None, None, 0.1,
    )  # fmt: skip


def choice(question: str, *pairs: tuple[str, str]) -> dict:
    return {"question": question, "options": [{"label": lb, "fact": f} for lb, f in pairs]}


def answer(**fields) -> StructuredAnswer:
    return StructuredAnswer.model_validate(structured(**fields))


# --- mode ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("requested", "question", "default", "expected"),
    [
        ("TR", "Can I fly in Germany?", "EU", ("TR", "explicit")),  # the user's choice wins
        (None, "Can I fly in Germany?", "TR", ("EU", "detected")),
        (None, "AB ile Türkiye kuralları", None, ("compare", "detected")),
        (None, "Gece uçabilir miyim?", "TR", ("TR", "default")),
        (None, "Gece uçabilir miyim?", None, ("EU", "default")),  # last resort
    ],
)
def test_resolve_mode(requested, question, default, expected):
    assert resolve_mode(requested, detect(question), default) == expected


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Ticari çekim için hangi belgeler gerekli?", True),
        ("İzlemem gereken adımlar neler?", True),
        ("Kayıt için neler gerekli?", True),
        ("Ne yapmam gerekiyor?", True),
        ("What do I need to fly commercially?", True),
        ("What are the steps to register?", True),
        ("Gece uçabilir miyim?", False),
        ("What is the maximum height?", False),
    ],
)
def test_is_list_question(question, expected):
    assert is_list_question(question) is expected


# --- schema --------------------------------------------------------------------------------


def test_every_citation_list_is_required_and_non_empty_in_the_schema():
    # A section's citations once had a default, so the schema sent to the model did not
    # require them, and a whole reply came back with none (refused as uncited_answer).
    defs = StructuredAnswer.model_json_schema()["$defs"]
    for name in ("Section", "Case", "Side"):
        assert "citations" in defs[name]["required"], name
        assert defs[name]["properties"]["citations"]["minItems"] == 1, name


def test_section_without_citations_does_not_fit_the_schema():
    with pytest.raises(ValidationError):
        StructuredAnswer.model_validate(
            {"answerable": True, "sections": [{"topic": "Kayıt", "text": "Kayıt gerekir."}]}
        )


# --- prompt --------------------------------------------------------------------------------


def system_for(question, mode="TR", lang="tr", facts=()):
    return build_prompt(question, lang, mode, detect(question), [hit(1, "TR")], list(facts))[0]


def test_prompt_numbers_passages_and_asks_for_the_language():
    system, prompt = build_prompt("Soru?", "tr", "TR", detect("Soru?"), [hit(1, "TR")], [])

    assert "Write every text in Turkish" in system
    assert "Answer for Türkiye" in system
    assert "[1] Türkiye | Doc title | Madde 1 (Heading), page 1\nPassage text 1" in prompt
    assert prompt.endswith("Question: Soru?")


def test_prompt_asks_for_cases_and_forbids_the_old_habits():
    system = system_for("Soru?")

    assert "never assume it silently" in system
    assert "Do not add a sentence about legal advice" in system
    assert "Do not refuse because the product is not named" in system
    assert "does not name a jurisdiction" not in system  # the old opening sentence is gone


def test_compare_prompt_keeps_sides_apart():
    system = system_for("AB ile Türkiye", mode="compare")

    assert 'Fill "compare"' in system
    assert "cites only passages from its own side" in system


def test_place_rule_only_when_a_place_inside_a_jurisdiction_is_named():
    assert "names 'İstanbul'" in system_for("İstanbul'da izin?")
    assert "names 'Germany'" in system_for("Drones in Germany?", mode="EU", lang="en")
    for question in ["AB'de izin?", "Türkiye'de izin?", "SHGM'ye göre lisans?"]:
        assert "That only selects the rules" not in system_for(question), question


def test_facts_are_given_as_confirmed():
    system = system_for("200 g drone?", facts=["The drone has a camera"])

    assert "The user has confirmed these facts" in system
    assert "- The drone has a camera" in system
    assert "confirmed these facts" not in system_for("200 g drone?")


# --- cleaning ------------------------------------------------------------------------------


def test_invalid_citations_and_uncited_parts_are_dropped():
    raw = answer(
        sections=[
            section("Kayıt", "Kayıt gerekir [2].", citations=[1, 9]),
            section("Uydurma", "Kaynaksız iddia.", citations=[7]),
            {
                "topic": "Lisans",
                "text": "Atıfsız giriş.",
                "citations": [],
                "cases": [
                    {
                        "condition": "P0",
                        "verdict": "GEREKİR",
                        "text": "Lisans [1].",
                        "citations": [],
                    },
                    {"condition": "P1", "verdict": "?", "text": "Uydurma.", "citations": [5]},
                ],
            },
        ]
    )

    cleaned, used = clean_answer(raw, [hit(1, "TR"), hit(2, "TR")], "TR", [])

    assert [s.topic for s in cleaned.sections] == ["Kayıt", "Lisans"]
    kayit, lisans = cleaned.sections
    # Inline markers move into the list; numbers outside the passages disappear.
    assert (kayit.text, kayit.citations) == ("Kayıt gerekir.", [1, 2])
    assert lisans.text is None  # no citation for the section text itself
    assert [(c.condition, c.text, c.citations) for c in lisans.cases] == [("P0", "Lisans.", [1])]
    assert used == [1, 2]


def test_compare_cells_cite_only_their_own_side():
    raw = answer(
        sections=[],
        compare={
            "key_differences": ["a", "b", "c", "d"],
            "rows": [
                {
                    "topic": "Kayıt",
                    "TR": {"text": "TR kuralı", "citations": [1, 2]},  # 2 is an EU passage
                    "EU": {"text": "AB kuralı", "citations": [1]},  # 1 is a Turkish passage
                },
                {"topic": "Boş", "TR": {"text": "x", "citations": []}, "EU": None},
            ],
        },
    )

    cleaned, used = clean_answer(raw, [hit(1, "TR"), hit(2, "EU")], "compare", [])

    assert cleaned.compare.key_differences == ["a", "b", "c"]
    [row] = cleaned.compare.rows
    assert (row.TR.text, row.TR.citations, row.EU) == ("TR kuralı", [1], None)
    assert used == [1]


def test_compare_is_dropped_outside_compare_mode():
    raw = answer(
        compare={
            "key_differences": [],
            "rows": [{"topic": "x", "TR": {"text": "t", "citations": [1]}}],
        }
    )

    cleaned, _ = clean_answer(raw, [hit(1, "TR")], "TR", [])

    assert cleaned.compare is None and cleaned.sections


def test_depends_on_is_trimmed_and_drops_what_the_user_confirmed():
    options = [{"label": f"o{i}", "fact": f"fact {i}"} for i in range(6)]
    raw = answer(
        depends_on=[
            choice("Kamera?", ("Var", "The drone has a camera"), ("Yok", "No camera")),
            {"question": "Tek seçenek", "options": options[:1]},
            {"question": "Çok seçenek", "options": options},
            {"question": "Üç", "options": options[:2]},
            {"question": "Dört", "options": options[:2]},
        ]
    )  # fmt: skip

    cleaned, _ = clean_answer(raw, [hit(1, "TR")], "TR", ["the drone has a camera"])

    assert [d.question for d in cleaned.depends_on] == ["Çok seçenek", "Üç", "Dört"]
    assert len(cleaned.depends_on[0].options) == 4


def test_answer_with_nothing_cited_becomes_unanswerable():
    raw = answer(sections=[section(citations=[9])], depends_on=[], not_in_sources=["x"])

    cleaned, used = clean_answer(raw, [hit(1, "TR")], "TR", [])

    assert cleaned.answerable is False
    assert cleaned.sections == [] and used == []
    assert cleaned.not_in_sources == ["x"]


def test_unanswerable_reply_keeps_no_sections():
    raw = answer(answerable=False, sections=[section()], not_in_sources=["Kaynaklarda yok."])

    cleaned, used = clean_answer(raw, [hit(1, "TR")], "TR", [])

    assert (cleaned.answerable, cleaned.sections, used) == (False, [], [])


def test_the_prompts_word_for_the_sources_never_reaches_the_reader():
    raw = StructuredAnswer.model_validate(
        structured(
            sections=[section("Kayıt", "Pasajlarda kayıt şartı var; ilgili pasajı okuyun.", [1])],
            not_in_sources=["Bu bilgi passages metinlerinde yok.", "Yedek parça kuralı yok."],
            follow_ups=["Passenger drones?"],
        )
    )

    tr = scrub_internal_terms(raw, "tr")
    assert tr.sections[0].text == "Kaynaklarda kayıt şartı var; ilgili kaynağı okuyun."
    assert tr.not_in_sources == ["Bu bilgi kaynak metinlerinde yok.", "Yedek parça kuralı yok."]
    assert tr.follow_ups == ["Passenger drones?"]

    en = StructuredAnswer.model_validate(
        structured(not_in_sources=["The passages do not say; this passage is about A1."])
    )
    assert scrub_internal_terms(en, "en").not_in_sources == [
        "The sources do not say; this source is about A1."
    ]


# --- rendering and excerpts ------------------------------------------------------------------


def test_render_text():
    raw = answer(
        depends_on=[choice("Kamera?", ("Var", "a"), ("Yok", "b"))],
        sections=[
            section("Kategori", "A1.", citations=[2]),
            {"topic": "Kayıt", "citations": [], "cases": [
                {"condition": "Kameralı", "verdict": "KAYIT", "text": "Gerekir.", "citations": [1]},
            ]},
        ],
        not_in_sources=["Ulusal sigorta kuralları."],
    )  # fmt: skip

    text = render_text(raw, "tr")

    assert text == (
        "Cevap şunlara bağlı:\n- Kamera? (Var / Yok)\n\n"
        "Kategori\nA1. [2]\n\n"
        "Kayıt\n- Kameralı — KAYIT: Gerekir. [1]\n\n"
        "Kaynaklarda olmayanlar:\n- Ulusal sigorta kuralları."
    )


def test_best_excerpt_picks_the_supporting_sentence():
    passage = (
        "UAS operations shall comply with the following. The remote pilot shall keep the UA "
        "at 120 metres from the surface. Other text follows here."
    )

    assert best_excerpt(passage, ["Azami yükseklik 120 metre."]) == (
        "… The remote pilot shall keep the UA at 120 metres from the surface. "
        "Other text follows here."
    )
    assert best_excerpt(passage, []).startswith("UAS operations")
    assert best_excerpt("x " * 400, []).endswith(" …")


# --- messages ------------------------------------------------------------------------------


def test_daily_limit_message_shows_reset_time_in_each_language():
    reset = datetime(2026, 10, 8, 7, 0, tzinfo=UTC)
    refusal = Refusal("ip_day", 20, 3600, reset)

    assert "08.10.2026 10:00 (Türkiye saati)" in limit_message(refusal, "tr")
    assert "2026-10-08 07:00 UTC" in limit_message(refusal, "en")


def test_minute_limit_message_says_how_long_to_wait():
    refusal = Refusal("ip_minute", 3, 42, None)

    assert "dakikada en fazla 3" in limit_message(refusal, "tr")
    assert "42 saniye" in limit_message(refusal, "tr")
    assert "at most 3 per minute" in limit_message(refusal, "en")


def test_provider_quota_messages():
    reset = datetime(2026, 10, 8, 7, 0, tzinfo=UTC)

    assert "günlük kotası doldu" in provider_quota_message(True, reset, "tr")
    assert "10:00 (Türkiye saati)" in provider_quota_message(True, reset, "tr")
    assert "busy" in provider_quota_message(False, reset, "en")
