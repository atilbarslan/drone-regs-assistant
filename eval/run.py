"""Run the evaluation set against the real Gemini API. By hand only; never in CI.

    python -m eval.run --config A                       # baseline: settings as deployed
    python -m eval.run --config B --thinking low
    python -m eval.run --config C --model gemini-3.8-flash --ids tr-03,k-01
    python -m eval.run --config A --dry-run              # count the API calls, make none
    python -m eval.run --config A --resume               # continue a stopped run
    python -m eval.run --config H --questions eval/holdout.yaml

Each question goes through app.answer.answer_question exactly as POST /api/ask sends it (see
ask_like_the_page): same Settings, same search parameters and list/compare rules, mode null,
default_mode from the language (tr → TR, en → EU), no facts. Called directly, so no request
limits apply and nothing is written to request_log.

Gemini calls per question: one embedding (cached in data/eval/, outside git, and reused by later
runs), one generation and one judge call (eval/judge.py). The generation and judge calls are
spaced to stay under the per-minute limit. A daily-quota error stops the run cleanly; --resume
continues it. The count of calls is written at the top of the results and the report.

Results: eval/results/<date>-<config>.json. Report: python -m eval.report <results files>.
DEBUG_RAW=1 also writes each raw model reply to data/debug/ (outside git).
"""

import argparse
import asyncio
import dataclasses
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import yaml

from app import answer as answer_module
from app.answer import Metrics, answer_question
from app.config import Settings
from app.db import create_pool
from app.providers import LLM, Embedder, Embeddings, EmptyResponse, RateLimited, TransientError
from app.search import SearchParams
from eval import score
from eval.judge import JUDGE_SYSTEM, judge

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "eval" / "results"
CACHE_PATH = ROOT / "data" / "eval" / "query-embeddings.json"
DEFAULT_QUESTIONS = ROOT / "eval" / "questions.yaml"
JUDGE_MODEL = "gemini-3.5-flash-lite"
# Free tier per-minute limits (Google AI Studio, 2026-10-06): flash-lite 15, 3.8-flash 5.
CALLS_PER_MINUTE = {"gemini-3.5-flash-lite": 12, "gemini-3.8-flash": 4}


class DailyQuota(Exception):
    """The daily limit of a model is used up: stop and resume tomorrow."""


# --- questions ------------------------------------------------------------------------------


def load_questions(path: Path) -> list[dict]:
    questions = yaml.safe_load(path.read_text(encoding="utf-8"))["questions"]
    for q in questions:
        q["facts"] = [
            {"id": f"{kind[0]}{i}", "kind": kind, "text": text}
            for kind in ("must", "should")
            for i, text in enumerate(q.get(kind) or [], 1)
        ]
    return questions


def default_mode(lang: str) -> str:
    """What the page sends as default_mode before any answer (frontend/render.js)."""
    return "TR" if lang == "tr" else "EU"


async def ask_like_the_page(
    question: str, lang: str, *, settings: Settings, pool, embedder, llm, debug_dir=None
):
    """The same call POST /api/ask makes (app/ask.py), for a first question on the page."""
    metrics = Metrics(lang=lang)
    result = await answer_question(
        question,
        lang,
        mode=None,
        default_mode=default_mode(lang),
        facts=[],
        pool=pool,
        embedder=embedder,
        llm=llm,
        params=SearchParams.from_settings(settings),
        list_top_k=settings.search_top_k_list,
        compare_per_side=settings.search_compare_per_side,
        core_sections=settings.search_core_sections,
        metrics=metrics,
        debug_dir=debug_dir,
    )
    return result, metrics


# --- quota-aware providers ------------------------------------------------------------------


@dataclasses.dataclass
class Calls:
    embedding: int = 0
    embedding_cached: int = 0
    generation: int = 0
    judge: int = 0
    retries: int = 0


class Spacing:
    """At most `per_minute` calls a minute, evenly spaced."""

    def __init__(self, per_minute: int):
        self.interval = 60.0 / per_minute
        self.last = 0.0

    async def wait(self) -> None:
        delay = self.last + self.interval - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        self.last = time.monotonic()


class QueryCache:
    """Question embeddings by model, dimensions and text, kept in a JSON file outside git."""

    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text()) if path.exists() else {}

    @staticmethod
    def key(model: str, dimensions: int, text: str) -> str:
        return f"{model}|{dimensions}|{text}"

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data))


class CachedEmbedder:
    def __init__(self, inner: Embedder, cache: QueryCache, dimensions: int, calls: Calls):
        self.inner, self.cache, self.dimensions, self.calls = inner, cache, dimensions, calls
        self.model = inner.model

    async def embed_documents(self, documents):  # not used by the evaluation
        raise NotImplementedError

    async def embed_query(self, query: str) -> Embeddings:
        key = QueryCache.key(self.model, self.dimensions, query)
        if key in self.cache.data:
            self.calls.embedding_cached += 1
            return Embeddings([self.cache.data[key]], None)
        self.calls.embedding += 1
        try:
            embedded = await self.inner.embed_query(query)
        except RateLimited as exc:
            if exc.daily:
                raise DailyQuota("embedding") from exc
            raise
        self.cache.data[key] = embedded.vectors[0]
        await asyncio.to_thread(self.cache.save)
        return embedded


class PacedLLM:
    """Spaces calls, retries a per-minute 429 and one transient error, stops on a daily 429."""

    def __init__(self, inner: LLM, spacing: Spacing, calls: Calls, field: str):
        self.inner, self.spacing, self.calls, self.field = inner, spacing, calls, field
        self.model = inner.model

    async def generate(self, system, prompt, schema):
        transient_left = 1
        for _ in range(4):
            await self.spacing.wait()
            setattr(self.calls, self.field, getattr(self.calls, self.field) + 1)
            try:
                return await self.inner.generate(system, prompt, schema)
            except RateLimited as exc:
                if exc.daily:
                    raise DailyQuota(self.model) from exc
                self.calls.retries += 1
                await asyncio.sleep(30 if exc.retry_after is None else exc.retry_after)
            except TransientError:
                if not transient_left:
                    raise
                transient_left -= 1
                self.calls.retries += 1
                await asyncio.sleep(15)
        raise TransientError("per-minute limit kept failing")


# --- one question ---------------------------------------------------------------------------


def score_question(q: dict, result, metrics: Metrics, verdict: dict) -> dict:
    facts = score.checked_facts(q["facts"], verdict.get("facts", []), result.text, result.answer)
    depends = [d.question for d in result.answer.depends_on]
    redundant = [v for v in verdict.get("depends_on", []) if v.get("already_given")]
    return {
        "detection": score.detection(result, q["jurisdiction"]),
        "retrieval": {
            **score.retrieval(result, q["expected_sources"]),
            "list_question": answer_module.is_list_question(q["question"]),
            "top_k": metrics.top_k,
        },
        "citations": score.citations(result, q["expected_sources"]),
        "refusal": score.refusal(result, q["should_refuse"], verdict.get("refusal_explained")),
        "facts": facts,
        "depends_on": {"questions": depends, "already_given": redundant},
        "latency": {
            "mode": result.mode,
            "retrieval_ms": metrics.retrieval_ms,
            "generation_ms": metrics.generation_ms,
            "prompt_tokens": metrics.prompt_tokens,
            "output_tokens": metrics.output_tokens,
        },
        "answer": {
            "refused": result.refused,
            "text": result.text,
            "structured": result.answer.model_dump(),
            "citations": [
                {"n": c.n, "section_ref": c.section_ref, "page": c.page} for c in result.citations
            ],
        },
        "judge": verdict,
    }


async def run_question(q, settings, pool, embedder, llm, judge_llm, debug_dir) -> dict:
    base = {"id": q["id"], "lang": q["lang"], "question": q["question"]}
    try:
        result, metrics = await ask_like_the_page(
            q["question"],
            q["lang"],
            settings=settings,
            pool=pool,
            embedder=embedder,
            llm=llm,
            debug_dir=debug_dir,
        )
    except (EmptyResponse, TransientError) as exc:
        return {**base, "error": f"generation: {type(exc).__name__}: {exc}"}
    depends = [d.question for d in result.answer.depends_on]
    try:
        verdict, _ = await judge(
            judge_llm, q["question"], result.text, q["facts"], depends, q["should_refuse"]
        )
    except (EmptyResponse, TransientError) as exc:
        verdict = {"facts": [], "error": f"judge: {type(exc).__name__}: {exc}"}
    return {**base, **score_question(q, result, metrics, verdict)}


# --- run ------------------------------------------------------------------------------------


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def prompt_fingerprint() -> str:
    parts = [answer_module.SYSTEM_PROMPT, *answer_module.MODE_RULES.values()]
    parts += [answer_module.PLACE_RULE, answer_module.FACTS_RULE]
    return sha("\n".join(parts))


def git_commit() -> str:
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain", "app"], capture_output=True, text=True)
    return head.stdout.strip() + ("+dirty(app)" if dirty.stdout.strip() else "")


def run_config(args, settings: Settings, questions_path: Path) -> dict:
    return {
        "name": args.config,
        "generation_model": settings.gemini_generation_model,
        "thinking_level": settings.gemini_thinking_level or "default (minimal)",
        "judge_model": JUDGE_MODEL,
        "top_k": settings.search_top_k,
        "list_top_k": settings.search_top_k_list,
        "compare_per_side": settings.search_compare_per_side,
        "core_sections": settings.search_core_sections,
        "candidates": settings.search_candidates,
        "rrf_k": settings.search_rrf_k,
        "timeout_s": settings.gemini_timeout_seconds,
        "prompt_sha": prompt_fingerprint(),
        "judge_prompt_sha": sha(JUDGE_SYSTEM),
        "questions": str(questions_path.relative_to(ROOT)),
        "questions_sha": sha(questions_path.read_text(encoding="utf-8")),
        "git": git_commit(),
        "note": args.note or "",
    }


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--config", required=True, help="name for this configuration (A, B, C, H1 …)")
    p.add_argument("--model", help="generation model (default: the app's setting)")
    p.add_argument("--thinking", help="thinking level: minimal, low, medium, high")
    p.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE",
                   help="any other Settings field, e.g. search_compare_per_side=4")  # fmt: skip
    p.add_argument("--ids", help="comma-separated question ids (default: all)")
    p.add_argument("--questions", default=str(DEFAULT_QUESTIONS))
    p.add_argument("--resume", action="store_true", help="continue the latest run of this config")
    p.add_argument("--dry-run", action="store_true", help="count the calls, make none")
    p.add_argument("--note", help="free text stored with the configuration")
    return p.parse_args(argv)


def build_settings(args) -> Settings:
    overrides = {}
    if args.model:
        overrides["gemini_generation_model"] = args.model
    if args.thinking:
        overrides["gemini_thinking_level"] = args.thinking
    for item in args.set:
        field, _, value = item.partition("=")
        overrides[field] = value
    return Settings(**overrides)


def results_path(name: str, resume: bool) -> Path:
    existing = sorted(RESULTS_DIR.glob(f"*-{name}.json"))
    if resume and existing:
        return existing[-1]
    return RESULTS_DIR / f"{datetime.now(UTC):%Y-%m-%dT%H%M}-{name}.json"


def main(argv) -> int:
    """Prepare (files, plan) here; only the API work runs in the event loop."""
    args = parse_args(argv)
    settings = build_settings(args)
    questions_path = Path(args.questions).resolve()
    questions = load_questions(questions_path)
    order = {q["id"]: i for i, q in enumerate(questions)}
    if args.ids:
        wanted = args.ids.split(",")
        questions = [q for q in questions if q["id"] in wanted]
        missing = set(wanted) - {q["id"] for q in questions}
        if missing:
            raise SystemExit(f"unknown ids: {sorted(missing)}")

    path = results_path(args.config, args.resume)
    previous = json.loads(path.read_text()) if args.resume and path.exists() else None
    done = {r["id"]: r for r in previous["results"] if "error" not in r} if previous else {}
    todo = [q for q in questions if q["id"] not in done]

    cache = QueryCache(CACHE_PATH)
    model, dims = settings.gemini_embedding_model, settings.gemini_embedding_dimensions
    to_embed = sum(1 for q in todo if QueryCache.key(model, dims, q["question"]) not in cache.data)
    plan = {"embedding": to_embed, "generation": len(todo), "judge": len(todo)}
    print(f"config {args.config}: {len(todo)} questions to run ({len(done)} already done)")
    print(f"planned Gemini calls (retries not counted): {plan}")
    if args.dry_run:
        return 0
    if settings.gemini_api_key is None:
        raise SystemExit("GEMINI_API_KEY is not set")

    record = {
        "config": run_config(args, settings, questions_path),
        "started": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": "running",
        "calls": {},
        "results": list(done.values()),
    }
    if previous:
        record["calls_before"] = previous.get("calls_total", previous.get("calls", {}))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.run(execute(settings, todo, cache, record, path, order))
    print(f"{path.relative_to(ROOT)}  calls: {record['calls']}")
    return 0


async def execute(settings, todo, cache, record, path, order) -> None:
    from app.gemini import GeminiEmbedder, GeminiLLM

    key = settings.gemini_api_key.get_secret_value()
    calls = Calls()
    gen_model = settings.gemini_generation_model
    flash_lite = Spacing(CALLS_PER_MINUTE.get(JUDGE_MODEL, 12))
    gen_spacing = (
        flash_lite if gen_model == JUDGE_MODEL else Spacing(CALLS_PER_MINUTE.get(gen_model, 4))
    )
    raw_embedder = GeminiEmbedder(
        key,
        settings.gemini_embedding_model,
        settings.gemini_embedding_dimensions,
        settings.gemini_timeout_seconds,
    )
    raw_llm = GeminiLLM(
        key, gen_model, settings.gemini_timeout_seconds, settings.gemini_thinking_level
    )
    raw_judge = GeminiLLM(key, JUDGE_MODEL, settings.gemini_timeout_seconds, None)
    embedder = CachedEmbedder(raw_embedder, cache, settings.gemini_embedding_dimensions, calls)
    llm = PacedLLM(raw_llm, gen_spacing, calls, "generation")
    judge_llm = PacedLLM(raw_judge, flash_lite, calls, "judge")
    debug_dir = settings.debug_raw_dir if settings.debug_raw else None

    def save(status: str) -> None:
        record["status"] = status
        record["calls"] = dataclasses.asdict(calls)
        before = record.get("calls_before", {})
        record["calls_total"] = {
            k: v + before.get(k, 0) for k, v in dataclasses.asdict(calls).items()
        }
        record["results"].sort(key=lambda r: order.get(r["id"], 999))
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1))

    pool = create_pool(settings)
    await pool.open(wait=True)
    status = "complete"
    try:
        for i, q in enumerate(todo, 1):
            started = time.monotonic()
            outcome = await run_question(q, settings, pool, embedder, llm, judge_llm, debug_dir)
            record["results"] = [r for r in record["results"] if r["id"] != q["id"]] + [outcome]
            save("running")
            flag = outcome.get("error") or ""
            print(f"[{i}/{len(todo)}] {q['id']} {time.monotonic() - started:.1f}s {flag}")
    except DailyQuota as exc:
        status = f"stopped: daily quota ({exc})"
        print(status, "- run again with --resume after the reset (midnight Pacific time)")
    finally:
        save(status)
        await pool.close()
        for client in (raw_embedder, raw_llm, raw_judge):
            await client.aclose()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
