"""Score stored answers again after an answer key changed: no new answer, one judge call each.

    python -m eval.rescore eval/results/<run>.json --ids j-01 --reason "j-01 key changed (8 Oct)"

The stored answer (text and structure) is judged against the current key; retrieval ranks and
citation places are recomputed from the stored passages. The result is written back into the
same file, with the old scores kept under "before_key_change" and "key_changed" set.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.config import Settings
from app.schema import StructuredAnswer
from eval import score
from eval.judge import judge
from eval.run import DEFAULT_QUESTIONS, JUDGE_MODEL, Calls, PacedLLM, Spacing, load_questions


def rescored(record: dict, q: dict, verdict: dict) -> dict:
    answer = StructuredAnswer.model_validate(record["answer"]["structured"])
    text = record["answer"]["text"]
    passages = record["retrieval"]["passages"]

    def rank(ref: str) -> int | None:
        return next((n for n, given in enumerate(passages, 1) if given == ref), None)

    ranks = {s["section_ref"]: rank(s["section_ref"]) for s in q["expected_sources"]}
    places = {}
    for s in q["expected_sources"]:
        numbers = {n for n, ref in enumerate(passages, 1) if ref == s["section_ref"]}
        places[s["section_ref"]] = [
            place for place, cited in score.answer_parts(answer) if numbers & set(cited)
        ]
    redundant = [v for v in verdict.get("depends_on", []) if v.get("already_given")]
    return {
        **record,
        "retrieval": {**record["retrieval"], "ranks": ranks},
        "citations": {"places": places, "any_expected_cited": any(places.values()) or None},
        "facts": score.checked_facts(q["facts"], verdict.get("facts", []), text, answer),
        "depends_on": {**record["depends_on"], "already_given": redundant},
        "judge": verdict,
    }


async def rescore_records(data: dict, ids: list[str], reason: str, questions: dict) -> int:
    """Judge the chosen records again, in place. Returns the number of judge calls."""
    from app.gemini import GeminiLLM

    settings = Settings()
    if settings.gemini_api_key is None:
        raise SystemExit("GEMINI_API_KEY is not set")
    calls = Calls()
    raw = GeminiLLM(settings.gemini_api_key.get_secret_value(), JUDGE_MODEL, 60, None)
    llm = PacedLLM(raw, Spacing(12), calls, "judge")
    try:
        for i, record in enumerate(data["results"]):
            if record["id"] not in ids or "error" in record:
                continue
            q = questions[record["id"]]
            depends = record["depends_on"]["questions"]
            verdict, _ = await judge(
                llm,
                q["question"],
                record["answer"]["text"],
                q["facts"],
                depends,
                q["should_refuse"],
            )
            old = {k: record[k] for k in ("retrieval", "citations", "facts", "judge")}
            new = rescored(record, q, verdict)
            new["before_key_change"] = old
            new["key_changed"] = reason
            data["results"][i] = new
    finally:
        await raw.aclose()
    return calls.judge


def main(argv) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("results", nargs="+")
    p.add_argument("--ids", required=True)
    p.add_argument("--reason", required=True)
    args = p.parse_args(argv)
    questions = {q["id"]: q for q in load_questions(DEFAULT_QUESTIONS)}
    for name in args.results:
        path = Path(name)
        data = json.loads(path.read_text(encoding="utf-8"))
        judged = asyncio.run(rescore_records(data, args.ids.split(","), args.reason, questions))
        data.setdefault("rescore_calls", []).append({"reason": args.reason, "judge": judged})
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(path, {"judge_calls": judged})


if __name__ == "__main__":
    main(sys.argv[1:])
