"""Retrieval only, without any Gemini call: where do the expected sections rank?

    python -m eval.retrieval --label base
    python -m eval.retrieval --label per-side-4 --set search_compare_per_side=4

Uses the question embeddings cached by eval/run.py (run it first) and the same path as
POST /api/ask (eval.run.ask_like_the_page); the model is replaced by a stub that answers
nothing, so only the passages are looked at. Writes eval/results/retrieval-<label>.json.
"""

import argparse
import asyncio
import json
import sys

from app.config import Settings
from app.db import create_pool
from app.providers import Generation
from eval import score
from eval.run import (
    CACHE_PATH,
    DEFAULT_QUESTIONS,
    RESULTS_DIR,
    ROOT,
    CachedEmbedder,
    Calls,
    QueryCache,
    ask_like_the_page,
    load_questions,
)


class NoModel:
    model = "none"

    async def generate(self, system, prompt, schema) -> Generation:
        return Generation({"answerable": False}, None, None, None)


class CacheOnly:
    """Fails instead of calling the API when a question is not cached."""

    model = ""

    async def embed_query(self, query):
        raise SystemExit(f"not in the embedding cache (run eval.run first): {query!r}")


async def ranks(settings: Settings, questions: list[dict]) -> list[dict]:
    cache = QueryCache(CACHE_PATH)
    stub = CacheOnly()
    stub.model = settings.gemini_embedding_model
    embedder = CachedEmbedder(stub, cache, settings.gemini_embedding_dimensions, Calls())
    pool = create_pool(settings)
    await pool.open(wait=True)
    out = []
    try:
        for q in questions:
            result, metrics = await ask_like_the_page(
                q["question"],
                q["lang"],
                settings=settings,
                pool=pool,
                embedder=embedder,
                llm=NoModel(),
            )
            out.append(
                {
                    "id": q["id"],
                    "mode": result.mode,
                    "top_k": metrics.top_k,
                    **score.retrieval(result, q["expected_sources"]),
                }
            )
    finally:
        await pool.close()
    return out


def main(argv) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
    p.add_argument("--questions", default=str(DEFAULT_QUESTIONS))
    args = p.parse_args(argv)
    settings = Settings(**dict(item.partition("=")[::2] for item in args.set))
    questions = load_questions((ROOT / args.questions).resolve())
    rows = asyncio.run(ranks(settings, questions))
    found = sum(1 for r in rows for rank in r["ranks"].values() if rank)
    total = sum(len(r["ranks"]) for r in rows)
    for r in rows:
        if r["ranks"]:
            ranks_text = ", ".join(f"{k}: {v or '-'}" for k, v in r["ranks"].items())
            print(f"{r['id']:6} {r['mode']:8} top_k={r['top_k']:2}  {ranks_text}")
    print(f"expected sections retrieved: {found}/{total}")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"retrieval-{args.label}.json"
    path.write_text(json.dumps({"settings": args.set, "rows": rows}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
