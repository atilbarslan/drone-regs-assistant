"""Hybrid search over the chunks: vector similarity plus full-text, fused with RRF.

Vector search finds passages by meaning, across languages. Full-text search finds exact terms
such as "UAS.OPEN.020" or "Madde 12" that embeddings blur. Each returns its own top
candidates; Reciprocal Rank Fusion scores a chunk by sum(1 / (k + rank)) over the lists it
appears in, so it needs only ranks, not comparable scores.

A third list holds the sections a question names explicitly ("UAS.OPEN.020", "Article 4",
"12. madde"). Without it, the rule itself and a passage that merely cites it can come out of
the other two lists with swapped ranks and an identical fused score.

Jurisdiction: a question about one side (see app/jurisdiction.py) is searched only in that
side's sources. A question about both, or about neither, is searched on each side separately
and the results are balanced, so a Turkish question still reaches the English EU text.

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
from app.jurisdiction import Jurisdiction, detect
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


# Every list is restricted to one jurisdiction when %(jurisdiction)s is set.
# Full-text query: the question's lexemes OR-ed together (plainto_tsquery ANDs them, and a
# question rarely contains every word of a passage), built with both language configurations.
# Each chunk is matched with the configuration of its own language.
SEARCH_SQL = """
WITH q AS (
    SELECT
        replace(plainto_tsquery('english', %(query)s)::text, ' & ', ' | ')::tsquery AS en,
        replace(plainto_tsquery('turkish', %(query)s)::text, ' & ', ' | ')::tsquery AS tr
),
scope AS (
    SELECT id FROM documents
    WHERE %(jurisdiction)s::text IS NULL OR jurisdiction = %(jurisdiction)s::text
),
vector_hits AS (
    SELECT id, row_number() OVER (ORDER BY distance) AS rank
    FROM (
        SELECT id, embedding <=> %(embedding)s::vector AS distance
        FROM chunks
        WHERE embedding_model = %(model)s AND document_id IN (SELECT id FROM scope)
        ORDER BY distance
        LIMIT %(candidates)s
    ) nearest
),
text_hits AS (
    SELECT id, row_number() OVER (ORDER BY score DESC, id) AS rank
    FROM (
        SELECT c.id, ts_rank(c.tsv, CASE c.language WHEN 'tr' THEN q.tr ELSE q.en END) AS score
        FROM chunks c, q
        WHERE ((c.language = 'en' AND c.tsv @@ q.en) OR (c.language = 'tr' AND c.tsv @@ q.tr))
          AND c.document_id IN (SELECT id FROM scope)
        ORDER BY score DESC, c.id
        LIMIT %(candidates)s
    ) matched
),
reference_hits AS (
    SELECT id, row_number() OVER (ORDER BY document_id, ordinal) AS rank
    FROM chunks
    WHERE section_ref ~* ANY (%(reference_patterns)s::text[])
      AND document_id IN (SELECT id FROM scope)
    ORDER BY document_id, ordinal
    LIMIT %(candidates)s
)
SELECT
    c.id, c.document_id, d.title AS document_title, d.jurisdiction, d.citation_url,
    c.section_ref, c.heading, c.page, c.language, c.text,
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
    jurisdiction: str
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
class SearchParams:
    top_k: int
    candidates: int
    rrf_k: int

    @classmethod
    def from_settings(cls, settings: Settings) -> "SearchParams":
        return cls(settings.search_top_k, settings.search_candidates, settings.search_rrf_k)


async def rank_chunks(
    conn: psycopg.AsyncConnection,
    *,
    query: str,
    embedding: list[float],
    model: str,
    jurisdiction: str | None,
    top_k: int,
    params: SearchParams,
) -> list[SearchHit]:
    """One fused ranking, optionally restricted to the sources of one jurisdiction."""
    values = {
        "query": query,
        "embedding": vector_literal(embedding),
        "model": model,
        "jurisdiction": jurisdiction,
        "reference_patterns": [reference_regex(r) for r in extract_references(query)],
        "candidates": params.candidates,
        "rrf_k": params.rrf_k,
        "top_k": top_k,
    }
    async with conn.transaction():
        # HNSW applies the WHERE filter after scanning the index, so a filter on the smaller
        # source could leave few candidates; iterative scans keep scanning until enough are
        # found (pgvector >= 0.8.0).
        await conn.execute("SET LOCAL hnsw.iterative_scan = strict_order")
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(SEARCH_SQL, values)
            rows = await cur.fetchall()
    return [SearchHit(**{**row, "score": float(row["score"])}) for row in rows]


def balance(by_side: dict[str, list[SearchHit]], order: list[str], top_k: int) -> list[SearchHit]:
    """Half of top_k from each side (the first side gets the odd one); a side with fewer
    results leaves its places to the other. Results stay grouped by side, in order."""
    quota = {order[0]: top_k - top_k // 2, order[1]: top_k // 2}
    take = {side: min(len(by_side[side]), quota[side]) for side in order}
    spare = top_k - sum(take.values())
    for side in order:
        extra = min(spare, len(by_side[side]) - take[side])
        take[side] += extra
        spare -= extra
    return [hit for side in order for hit in by_side[side][: take[side]]]


async def retrieve(
    conn: psycopg.AsyncConnection,
    *,
    query: str,
    embedding: list[float],
    model: str,
    jurisdiction: Jurisdiction,
    first: str,
    params: SearchParams,
) -> list[SearchHit]:
    """Search for a question whose jurisdiction has been detected.

    "EU"/"TR": only that side's sources. "both"/"none": each side separately, balanced, with
    the side named by first (the one matching the interface language) listed first.
    """
    if jurisdiction in ("EU", "TR"):
        return await rank_chunks(
            conn, query=query, embedding=embedding, model=model, jurisdiction=jurisdiction,
            top_k=params.top_k, params=params,
        )  # fmt: skip
    order = [first, "EU" if first == "TR" else "TR"]
    by_side = {}
    for side in order:
        by_side[side] = await rank_chunks(
            conn, query=query, embedding=embedding, model=model, jurisdiction=side,
            top_k=params.top_k, params=params,
        )  # fmt: skip
    return balance(by_side, order, params.top_k)


# Core sections: the articles most questions about "what applies" turn on, per jurisdiction,
# chosen from the structure of the texts (registration, class, licence, zones, technical
# requirements; operating categories, pilot age, registration, the A1 subcategory). Added to
# the passages of list questions when they were not retrieved. No API call.
CORE_SECTIONS = {
    "TR": ["Madde 11", "Madde 8", "Madde 15", "Madde 12", "Madde 23"],
    "EU": [
        "Article 4 (2019/947)",
        "Article 9 (2019/947)",
        "Article 14 (2019/947)",
        "UAS.OPEN.020",
    ],
}

CORE_SQL = """
SELECT DISTINCT ON (c.section_ref)
    c.id, c.document_id, d.title AS document_title, d.jurisdiction, d.citation_url,
    c.section_ref, c.heading, c.page, c.language, c.text,
    NULL::bigint AS vector_rank, NULL::bigint AS text_rank, NULL::bigint AS reference_rank,
    0.0 AS score
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.jurisdiction = %(jurisdiction)s AND c.section_ref = ANY(%(refs)s)
ORDER BY c.section_ref, c.ordinal
"""


async def with_core_sections(
    conn: psycopg.AsyncConnection, hits: list[SearchHit], sides: list[str]
) -> list[SearchHit]:
    """Append the first passage of each core section of these sides that is not among the
    hits yet, right after that side's passages (so a comparison stays grouped by side)."""
    have = {(h.jurisdiction, h.section_ref) for h in hits}
    out: list[SearchHit] = []
    for side in sides:
        out += [h for h in hits if h.jurisdiction == side]
        refs = [r for r in CORE_SECTIONS[side] if (side, r) not in have]
        if not refs:
            continue
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(CORE_SQL, {"jurisdiction": side, "refs": refs})
            found = {row["section_ref"]: row for row in await cur.fetchall()}
        out += [
            SearchHit(**{**found[r], "score": float(found[r]["score"])}) for r in refs if r in found
        ]
    out += [h for h in hits if h.jurisdiction not in sides]
    return out


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
    jurisdiction: str | None = None,
) -> SearchResult:
    """Embed the query and rank all chunks, or one jurisdiction's, without balancing."""
    embedded = await embedder.embed_query(query)
    hits = await rank_chunks(
        conn, query=query, embedding=embedded.vectors[0], model=embedder.model,
        jurisdiction=jurisdiction, top_k=top_k, params=SearchParams(top_k, candidates, rrf_k),
    )  # fmt: skip
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
    detection = detect(query)
    try:
        embedded = await embedder.embed_query(query)
        async with await psycopg.AsyncConnection.connect(
            settings.database_url.get_secret_value()
        ) as conn:
            hits = await retrieve(
                conn, query=query, embedding=embedded.vectors[0], model=embedder.model,
                jurisdiction=detection.jurisdiction, first="TR",
                params=SearchParams.from_settings(settings),
            )  # fmt: skip
    finally:
        await embedder.aclose()
    terms = ", ".join(f"{t.text} ({t.jurisdiction})" for t in detection.matched_terms)
    print(f"jurisdiction: {detection.jurisdiction} [{terms}] | query tokens: {embedded.tokens}")
    for n, hit in enumerate(hits, 1):
        print(
            f"{n}. {hit.score:.4f} vec={hit.vector_rank} fts={hit.text_rank} "
            f"ref={hit.reference_rank} "
            f"[{hit.jurisdiction}] {hit.section_ref} p.{hit.page} | {hit.heading[:60]}"
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit('usage: python -m app.search "question"')
    asyncio.run(main(sys.argv[1]))
