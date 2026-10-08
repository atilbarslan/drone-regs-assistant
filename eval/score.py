"""Scoring one answer against its key. Pure functions: no network, no database.

The judge's verdicts are checked here too: a "present" or "contradicted" verdict must quote the
answer word for word, or it becomes "unverified".
"""

import re
import unicodedata
from dataclasses import dataclass

from app.answer import AnswerResult
from app.schema import StructuredAnswer

# The question set's jurisdiction values and the detected mode each one means.
ACCEPTED_MODE = {"TR": "TR", "EU": "EU", "both": "compare", "none": None}
DETECTED_MODE = {"EU": "EU", "TR": "TR", "both": "compare", "none": None}


def detection(result: AnswerResult, accepted: list[str]) -> dict:
    detected = DETECTED_MODE[result.detection.jurisdiction]
    return {
        "detected_mode": detected,
        "mode": result.mode,
        "mode_source": result.mode_source,
        "accepted": accepted,
        "ok": detected in {ACCEPTED_MODE[a] for a in accepted},
        "matched_terms": [t.text for t in result.detection.matched_terms],
    }


def retrieval(result: AnswerResult, expected: list[dict]) -> dict:
    """1-based rank of each expected section among the passages given to the model."""
    refs = [hit.section_ref for hit in result.hits]
    ranks = {}
    for source in expected:
        ref = source["section_ref"]
        rank = next(
            (
                n
                for n, hit in enumerate(result.hits, 1)
                if hit.section_ref == ref and hit.document_id == source["source_id"]
            ),
            None,
        )
        ranks[ref] = rank
    return {"passages": refs, "count": len(refs), "ranks": ranks}


def answer_parts(answer: StructuredAnswer):
    """(place, citations) for every part of an answer that cites passages."""
    for section in answer.sections:
        if section.text:
            yield f"section '{section.topic}'", section.citations
        for case in section.cases:
            yield f"case '{section.topic} / {case.condition}'", case.citations
    if answer.compare:
        for row in answer.compare.rows:
            for side in ("TR", "EU"):
                cell = getattr(row, side)
                if cell:
                    yield f"compare '{row.topic}' {side}", cell.citations


def citations(result: AnswerResult, expected: list[dict]) -> dict:
    """Where each expected section is cited ([n] in a section, case or comparison cell)."""
    places: dict[str, list[str]] = {}
    for source in expected:
        numbers = {
            n
            for n, hit in enumerate(result.hits, 1)
            if hit.section_ref == source["section_ref"] and hit.document_id == source["source_id"]
        }
        places[source["section_ref"]] = [
            place for place, cited in answer_parts(result.answer) if numbers & set(cited)
        ]
    cited = [ref for ref, where in places.items() if where]
    return {"places": places, "any_expected_cited": bool(cited) if expected else None}


def refusal(result: AnswerResult, should_refuse: bool, explained: bool | None) -> dict:
    """Two separate criteria for a question that should be refused, and false refusals."""
    empty = not result.answer.sections and not result.answer.compare
    if should_refuse:
        return {
            "should_refuse": True,
            "refused_flag": result.refused,
            # No sections or comparison, and not_in_sources says the asked thing is missing.
            "empty_and_explained": empty and bool(explained),
            "false_refusal": False,
        }
    return {
        "should_refuse": False,
        "refused_flag": result.refused,
        "empty_and_explained": None,
        "false_refusal": result.refused or empty,
    }


# --- judge quotes ---------------------------------------------------------------------------

_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text).translate(_QUOTES)
    return re.sub(r"\s+", " ", text).strip()


def quote_in(quote: str, text: str) -> bool:
    """True if the quote appears in the text word for word (spaces, quote marks and dashes
    normalised; a trailing "..." or punctuation is ignored)."""
    q = normalise(quote).strip(" .…,;:")
    return bool(q) and q in normalise(text)


def case_texts(answer: StructuredAnswer) -> list[str]:
    return [
        f"{case.condition} {case.verdict} {case.text}"
        for section in answer.sections
        for case in section.cases
    ]


def checked_facts(facts: list[dict], verdicts: list[dict], text: str, answer) -> list[dict]:
    """Merge the judge's verdicts into the facts. Verdicts without a verbatim quote become
    "unverified"; a fact found only inside a case is marked."""
    by_id = {v["id"]: v for v in verdicts}
    cases = case_texts(answer)
    out = []
    for fact in facts:
        verdict = by_id.get(fact["id"])
        status = verdict["status"] if verdict else "missing_verdict"
        quote = (verdict or {}).get("quote") or ""
        note = ""
        if status in ("present", "contradicted"):
            if not quote_in(quote, text):
                status, note = "unverified", f"judge said {verdict['status']}; quote not found"
            elif status == "present" and any(quote_in(quote, c) for c in cases):
                if not quote_in(quote, _without_case_lines(text, answer)):
                    note = "case içinde"
        out.append({**fact, "status": status, "quote": quote, "note": note})
    return out


def _without_case_lines(text: str, answer: StructuredAnswer) -> str:
    # render_text writes a case as "- {condition} — {verdict}: {text} [n]".
    starts = tuple(
        f"- {case.condition} — {case.verdict}:"
        for section in answer.sections
        for case in section.cases
    )
    lines = text.splitlines()
    return "\n".join(line for line in lines if not starts or not line.startswith(starts))


@dataclass(frozen=True)
class Coverage:
    present: int
    absent: int
    contradicted: int
    unverified: int
    total: int


def coverage(facts: list[dict], kind: str) -> Coverage:
    chosen = [f for f in facts if f["kind"] == kind]
    count = lambda s: sum(1 for f in chosen if f["status"] == s)  # noqa: E731
    return Coverage(
        count("present"), count("absent"), count("contradicted"), count("unverified"), len(chosen)
    )
