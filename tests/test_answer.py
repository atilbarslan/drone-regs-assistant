"""Pure parts of the answer step: citation checks, prompt, excerpt, user-facing lines."""

from datetime import UTC, datetime

import pytest

from app.answer import build_prompt, check_citations, excerpt
from app.jurisdiction import detect
from app.limits import Refusal
from app.messages import jurisdiction_line, limit_message, provider_quota_message
from app.search import SearchHit


@pytest.mark.parametrize(
    ("text", "passages", "expected_text", "expected_used"),
    [
        ("Allowed [1]. Also [2].", 3, "Allowed [1]. Also [2].", [1, 2]),
        # A citation of a passage that was not given is removed, with its space.
        ("Allowed [1]. Invented [9].", 3, "Allowed [1]. Invented.", [1]),
        ("Mixed [2, 9] and [3].", 3, "Mixed [2] and [3].", [2, 3]),
        ("A range [1-3].", 3, "A range [1][2][3].", [1, 2, 3]),
        ("Repeated [2][2] then [1].", 3, "Repeated [2] then [1].", [2, 1]),
        ("No citations at all.", 3, "No citations at all.", []),
        ("Only invalid [0] [4].", 3, "Only invalid.", []),
    ],
)
def test_check_citations(text, passages, expected_text, expected_used):
    assert check_citations(text, passages) == (expected_text, expected_used)


def test_excerpt_cuts_at_a_word():
    text = "word " * 100

    short = excerpt(text, limit=30)

    assert short.endswith(" …")
    assert len(short) <= 32
    assert excerpt("short text") == "short text"


def hit(n: int, jurisdiction: str) -> SearchHit:
    return SearchHit(
        n, "doc", "Doc title", jurisdiction, "https://example.test/doc.pdf", f"Madde {n}",
        "Heading", n, "tr", f"Passage text {n}", 1, None, None, 0.1,
    )  # fmt: skip


def test_prompt_numbers_passages_and_asks_for_the_interface_language():
    system, prompt = build_prompt("Soru?", "tr", detect("Türkiye'de izin"), [hit(1, "TR")])

    assert "Write the answer in Turkish" in system
    assert "about Turkish rules" in system
    assert "[1] Türkiye | Doc title | Madde 1 (Heading), page 1\nPassage text 1" in prompt
    assert prompt.endswith("Question: Soru?")


def test_prompt_for_an_unknown_jurisdiction_asks_for_two_labelled_parts():
    system_tr, _ = build_prompt("Gece uçuşu?", "tr", detect("Gece uçuşu?"), [hit(1, "TR")])
    system_en, _ = build_prompt("Night flight?", "en", detect("Night flight?"), [hit(1, "EU")])

    assert "does not say whether it is about the EU or Türkiye" in system_tr
    assert "Sorunuz AB'yi mi Türkiye'yi mi" in system_tr
    assert "'Türkiye'de' and 'AB'de'" in system_tr
    assert "'In the EU' and 'In Türkiye'" in system_en


@pytest.mark.parametrize(
    ("question", "lang", "expected"),
    [
        (
            "Almanya'da uçabilir miyim?",
            "tr",
            "Bu cevap AB mevzuatına göredir (sorudaki 'Almanya' ifadesinden).",
        ),
        (
            "SHGM'ye göre P1 lisansı",
            "tr",
            "Bu cevap Türkiye mevzuatına göredir (sorudaki 'SHGM', 'P1' ifadelerinden).",
        ),
        (
            "Compare EASA and SHGM",
            "en",
            "This answer is based on EU and Turkish rules (from 'EASA', 'SHGM' in your question).",
        ),
        ("Can I fly at night?", "en", None),
    ],
)
def test_jurisdiction_line(question, lang, expected):
    assert jurisdiction_line(detect(question), lang) == expected


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
