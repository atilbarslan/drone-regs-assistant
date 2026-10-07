"""Hybrid search against the test database, with the fake bag-of-words embedder.

The chunks are short, self-written stand-ins shaped like the real sources.
"""

import pytest

from app.search import (
    SearchHit,
    SearchParams,
    balance,
    extract_references,
    reference_regex,
    retrieve,
    search,
)

pytestmark = pytest.mark.anyio


async def run(db, embedder, query: str, top_k: int = 5):
    result = await search(db, embedder, query, top_k=top_k, candidates=20, rrf_k=60)
    return result.hits


async def test_exact_rule_reference_ranks_that_rule_first(db, loaded):
    hits = await run(db, loaded, "UAS.OPEN.020")

    assert hits[0].section_ref == "UAS.OPEN.020"
    assert (hits[0].text_rank, hits[0].reference_rank) == (1, 1)
    # A clear win, not a tie broken by row order: the AMC that cites the rule three times is
    # closer in the (bag-of-words) vector space.
    assert hits[1].section_ref == "AMC1 UAS.OPEN.030"
    assert hits[1].vector_rank == 1
    assert hits[0].score > hits[1].score
    assert (hits[0].document_id, hits[0].page) == ("eu-sample", 10)
    assert hits[0].citation_url == "https://example.test/eu-sample.pdf"


@pytest.mark.parametrize("query", ["Madde 12 ne diyor?", "12. madde", "12 nci maddeye göre"])
async def test_article_number_in_turkish_ranks_that_article_first(db, loaded, query):
    hits = await run(db, loaded, query)

    assert hits[0].section_ref == "Madde 12"
    assert hits[0].reference_rank == 1


async def test_article_reference_matches_both_regulations_but_not_longer_numbers(db, loaded):
    hits = await run(db, loaded, "Article 4", top_k=10)

    assert hits[0].section_ref == "Article 4 (2019/947)"
    assert [h.section_ref for h in hits if h.reference_rank] == ["Article 4 (2019/947)"]


async def test_reference_inside_a_question(db, loaded):
    hits = await run(db, loaded, "What does UAS.OPEN.020 say about the remote pilot?")

    assert hits[0].section_ref == "UAS.OPEN.020"


async def test_plain_words_find_the_passage(db, loaded):
    hits = await run(db, loaded, "kırmızı bölgede uçuş izni")

    assert hits[0].section_ref == "Madde 12"
    assert hits[0].vector_rank is not None and hits[0].text_rank is not None


async def test_score_is_reciprocal_rank_fusion(db, loaded):
    hits = await run(db, loaded, "horizontal distance from uninvolved people", top_k=6)

    for hit in hits:
        ranks = (hit.vector_rank, hit.text_rank, hit.reference_rank)
        expected = sum(1 / (60 + r) for r in ranks if r is not None)
        assert hit.score == pytest.approx(expected)
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)


async def test_top_k_limits_results(db, loaded):
    assert len(await run(db, loaded, "pilot", top_k=2)) == 2


async def test_vector_search_ignores_chunks_embedded_with_another_model(db, loaded):
    await db.execute(
        "UPDATE chunks SET embedding_model = 'other-model' WHERE section_ref = 'Madde 15'"
    )

    hits = await run(db, loaded, "lisans seviyeleri", top_k=10)

    madde_15 = [h for h in hits if h.section_ref == "Madde 15"]
    # Still found by full-text search, but not by vector search.
    assert madde_15 and madde_15[0].vector_rank is None and madde_15[0].text_rank is not None


async def test_query_with_no_text_match_still_uses_vectors(db, loaded):
    hits = await run(db, loaded, "the and of")  # only stop words: no full-text query

    assert hits
    assert all(h.text_rank is None for h in hits)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("What does uas.open.020 say?", ["UAS.OPEN.020"]),
        ("AMC1 UAS.SPEC.050(1)(d)", ["AMC1 UAS.SPEC.050", "UAS.SPEC.050"]),
        ("article 11 of 2019/947", ["Article 11"]),
        ("Madde 1 ve madde 12", ["Madde 1", "Madde 12"]),
        ("12'nci madde", ["Madde 12"]),
        ("GEÇİCİ MADDE 3", ["Geçici Madde 3"]),
        ("İHA ile nerede uçabilirim?", []),
    ],
)
def test_extract_references(query, expected):
    assert extract_references(query) == expected


def test_reference_regex_does_not_match_longer_numbers():
    import re

    pattern = re.compile(reference_regex("Madde 1"))
    assert pattern.search("Madde 1")
    assert not pattern.search("Madde 12")
    assert re.search(reference_regex("Article 4"), "Article 4 (2019/945)")


# --- jurisdiction ----------------------------------------------------------------------------


async def ranked(db, embedder, query: str, jurisdiction: str, first: str = "TR", top_k: int = 4):
    embedded = await embedder.embed_query(query)
    return await retrieve(
        db,
        query=query,
        embedding=embedded.vectors[0],
        model=embedder.model,
        jurisdiction=jurisdiction,
        first=first,
        params=SearchParams(top_k=top_k, candidates=20, rrf_k=60),
    )


async def test_one_jurisdiction_searches_only_its_sources(db, loaded):
    # Turkish words, but the question is about the EU: only EU passages come back.
    hits = await ranked(db, loaded, "kırmızı bölgede pilot", "EU")

    assert hits and {h.jurisdiction for h in hits} == {"EU"}


async def test_unknown_jurisdiction_is_balanced_between_sources(db, loaded):
    hits = await ranked(db, loaded, "pilot uçuş izni", "none", first="TR", top_k=4)

    assert [h.jurisdiction for h in hits] == ["TR", "TR", "EU", "EU"]


async def test_balanced_search_lists_the_interface_language_side_first(db, loaded):
    hits = await ranked(db, loaded, "pilot", "both", first="EU", top_k=3)

    # The first side gets the odd place.
    assert [h.jurisdiction for h in hits] == ["EU", "EU", "TR"]


def hit(side: str, n: int):
    return SearchHit(n, side, side, side, "", f"{side}-{n}", "", 1, "en", "", 1, None, None, 0.0)


def test_balance_fills_a_short_side_from_the_other():
    by_side = {"TR": [hit("TR", 1)], "EU": [hit("EU", n) for n in range(1, 8)]}

    result = balance(by_side, ["TR", "EU"], top_k=6)

    assert [h.section_ref for h in result] == ["TR-1", "EU-1", "EU-2", "EU-3", "EU-4", "EU-5"]


def test_balance_with_both_sides_empty():
    assert balance({"TR": [], "EU": []}, ["TR", "EU"], top_k=8) == []
