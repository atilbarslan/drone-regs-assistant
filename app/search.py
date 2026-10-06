"""Hybrid search over the chunks: vector similarity plus full-text, fused with RRF.

Vector search finds passages by meaning, across languages. Full-text search finds exact terms
such as "UAS.OPEN.020" or "Madde 12" that embeddings blur. Each returns its own top
candidates; Reciprocal Rank Fusion scores a chunk by sum(1 / (k + rank)) over the lists it
appears in, so it needs only ranks, not comparable scores.

A third list holds the sections a question names explicitly ("UAS.OPEN.020", "Article 4",
"12. madde"). Without it, the rule itself and a passage that merely cites it can come out of
the other two lists with swapped ranks and an identical fused score.

Try it: python -m app.search "question"   (one embedding request)
"""

import asyncio
import re
import sys
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from app.config import Settings
from app.db import vector_literal
from app.providers import Embedder

# References a question can name, and how to write them the way section_ref does.
_REFERENCE_PATTERNS = [
    (re.compile(r"\b((?:AMC|GM)\d+(?:bis)?)\s+(UAS\.[A-Z]+(?:-\d+)?\.\d{3}|Article\s+\d+)", re.I),
     lambda m: f"{m.group(1).upper().replace('BIS', 'bis')} {_rule(m.group(2))}"),
    (re.compile(r"\bUAS\.(?:OPEN|SPEC|LUC|STS-\d{2})\.\d{3}\b", re.I),
     lambda m: m.group(0).upper()),
    (re.compile(r"\bArticle\s+(\d+[a-z]?)\b", re.I), lambda m: f"Article {m.group(1)}"),
    (re.compile(r"\b(ge[çc][iİı]c[iİı]\s+)?madde\s+(\d+)\b", re.I),  # İ: no 1-letter lower
     lambda m: f"{'Geçici Madde' if m.group(1) else 'Madde'} {m.group(2)}"),
    # "12. madde", "12 nci madde", "12'nci madde"
    (re.compile(r"\b(\d+)\s*(?:\.|'?\s*(?:nci|inci|ncı|ıncı|ncü|üncü|ncu|uncu))\s*madde", re.I),
     lambda m: f"Madde {m.group(1)}"),
]  # fmt: skip


def _rule(text: str) -> str:
    return text.upper() if text.upper().startswith("UAS.") else f"Article {text.split()[-1]}"


def extract_references(query: str) -> list[str]:
    """Section references named in a question, written the way section_ref writes them."""
    found = []
    for pattern, canonical in _REFERENCE_PATTERNS:
        for match in pattern.finditer(query):
            ref = canonical(match)
            if ref not in found:
                found.append(ref)
    return found


def reference_regex(ref: str) -> str:
    """A Postgres regex matching section_refs that are this reference: "Article 4" matches
    "Article 4 (2019/947)" and "AMC1 UAS.OPEN.020" matches "AMC1 UAS.OPEN.020(1) and (2)", but
    "Madde 1" does not match "Madde 12"."""
    escaped = re.sub(r"([.^$*+?()\[\]{}|\\])", r"\\\1", ref)
    return f"^{escaped}($|[ (])"


# Full-text query: the question's lexemes OR-ed together (plainto_tsquery ANDs them, and a
# question rarely contains every word of a passage), built with both language configurations.
# Each chunk is matched with the configuration of its own language.
SEARCH_SQL = """
WITH q AS (
    SELECT
        replace(plainto_tsquery('english', %(query)s)::text, ' & ', ' | ')::tsquery AS en,
        replace(plainto_tsquery('turkish', %(query)s)::text, ' & ', ' | ')::tsquery AS tr
),
vector_hits AS (
    SELECT id, row_number() OVER (ORDER BY distance) AS rank
    FROM (
        SELECT id, embedding <=> %(embedding)s::vector AS distance
        FROM chunks
        WHERE embedding_model = %(model)s
        ORDER BY distance
        LIMIT %(candidates)s
    ) nearest
),
text_hits AS (
    SELECT id, row_number() OVER (ORDER BY score DESC, id) AS rank
    FROM (
        SELECT c.id, ts_rank(c.tsv, CASE c.language WHEN 'tr' THEN q.tr ELSE q.en END) AS score
        FROM chunks c, q
        WHERE (c.language = 'en' AND c.tsv @@ q.en) OR (c.language = 'tr' AND c.tsv @@ q.tr)
        ORDER BY score DESC, c.id
        LIMIT %(candidates)s
    ) matched
),
reference_hits AS (
    SELECT id, row_number() OVER (ORDER BY document_id, ordinal) AS rank
    FROM chunks
    WHERE section_ref ~* ANY (%(reference_patterns)s::text[])
    ORDER BY document_id, ordinal
    LIMIT %(candidates)s
)
SELECT
    c.id, c.document_id, d.title AS document_title, d.citation_url, c.section_ref, c.heading,
    c.page, c.language, c.text,
    v.rank AS vector_rank, t.rank AS text_rank, r.rank AS reference_rank,
    COALESCE(1.0 / (%(rrf_k)s + v.rank), 0)
        + COALESCE(1.0 / (%(rrf_k)s + t.rank), 0)
        + COALESCE(1.0 / (%(rrf_k)s + r.rank), 0) AS score
FROM chunks c
JOIN documents d ON d.id = c.document_id
LEFT JOIN vector_hits v ON v.id = c.id
LEFT JOIN text_hits t ON t.id = c.id
LEFT JOIN reference_hits r ON r.id = c.id
WHERE v.id IS NOT NULL OR t.id IS NOT NULL OR r.id IS NOT NULL
ORDER BY score DESC, c.id
LIMIT %(top_k)s
"""


@dataclass(frozen=True)
class SearchHit:
    id: int
    document_id: str
    document_title: str
    citation_url: str
    section_ref: str
    heading: str
    page: int | None
    language: str
    text: str
    vector_rank: int | None
    text_rank: int | None
    reference_rank: int | None
    score: float


@dataclass(frozen=True)
class SearchResult:
    hits: list[SearchHit]
    embedding_tokens: int | None


async def search(
    conn: psycopg.AsyncConnection,
    embedder: Embedder,
    query: str,
    *,
    top_k: int,
    candidates: int,
    rrf_k: int,
) -> SearchResult:
    embedded = await embedder.embed_query(query)
    params = {
        "query": query,
        "embedding": vector_literal(embedded.vectors[0]),
        "model": embedder.model,
        "reference_patterns": [reference_regex(r) for r in extract_references(query)],
        "candidates": candidates,
        "rrf_k": rrf_k,
        "top_k": top_k,
    }
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(SEARCH_SQL, params)
        rows = await cur.fetchall()
    hits = [SearchHit(**{**row, "score": float(row["score"])}) for row in rows]
    return SearchResult(hits=hits, embedding_tokens=embedded.tokens)


async def main(query: str) -> None:
    from app.gemini import GeminiEmbedder

    settings = Settings()
    if settings.gemini_api_key is None:
        raise SystemExit("GEMINI_API_KEY is not set")
    embedder = GeminiEmbedder(
        settings.gemini_api_key.get_secret_value(),
        settings.gemini_embedding_model,
        settings.gemini_embedding_dimensions,
        settings.gemini_timeout_seconds,
    )
    try:
        async with await psycopg.AsyncConnection.connect(
            settings.database_url.get_secret_value()
        ) as conn:
            result = await search(
                conn,
                embedder,
                query,
                top_k=settings.search_top_k,
                candidates=settings.search_candidates,
                rrf_k=settings.search_rrf_k,
            )
    finally:
        await embedder.aclose()
    print(f"query tokens: {result.embedding_tokens}")
    for n, hit in enumerate(result.hits, 1):
        print(
            f"{n}. {hit.score:.4f} vec={hit.vector_rank} fts={hit.text_rank} "
            f"ref={hit.reference_rank} "
            f"[{hit.document_id}] {hit.section_ref} p.{hit.page} | {hit.heading[:60]}"
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit('usage: python -m app.search "question"')
    asyncio.run(main(sys.argv[1]))
