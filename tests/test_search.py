"""Hybrid search against the test database, with the fake bag-of-words embedder.

The chunks are short, self-written stand-ins shaped like the real sources.
"""

import pytest

from app.search import extract_references, reference_regex, search
from ingest.embed import Pacer, embed_pending, sync_source
from tests.conftest import make_settings
from tests.fakes import FakeEmbedder, sample_source

pytestmark = pytest.mark.anyio


def chunk(section_ref: str, heading: str, text: str, language: str, page: int = 1) -> dict:
    return {
        "section_ref": section_ref,
        "heading": heading,
        "page": page,
        "chunk_index": 0,
        "language": language,
        "text": text,
    }


EU_CHUNKS = [
    chunk(
        "UAS.OPEN.020",
        "Operations in subcategory A1",
        "The remote pilot keeps the aircraft away from groups of people.",
        "en",
        page=10,
    ),
    # Mentions UAS.OPEN.020 several times, so a plain word count would favour it.
    chunk(
        "AMC1 UAS.OPEN.030",
        "Operations in subcategory A2",
        "Unlike UAS.OPEN.020, which covers A1, this applies to A2. Read UAS.OPEN.020 and "
        "UAS.OPEN.020 together with the rules for the remote pilot.",
        "en",
        page=11,
    ),
    chunk(
        "UAS.OPEN.030",
        "Operations in subcategory A2",
        "The remote pilot keeps a horizontal distance of 30 metres from uninvolved people.",
        "en",
        page=11,
    ),
    chunk(
        "Article 4 (2019/947)",
        "Open category",
        "Operations are classified in the open category when the aircraft is light.",
        "en",
        page=3,
    ),
    chunk(
        "Article 40 (2019/945)",
        "Requirements for certified aircraft",
        "Aircraft in the certified category need a type certificate.",
        "en",
        page=50,
    ),
]
TR_CHUNKS = [
    chunk(
        "Madde 12",
        "Kısıtlanmış bölgeler",
        "Kırmızı bölgede uçuş izne tabidir. Yeşil bölgede izin gerekmez.",
        "tr",
        page=8,
    ),
    chunk(
        "Madde 15",
        "Pilot yetkinliği",
        "Pilot lisansı P0, P1 ve P2 seviyelerinde verilir; bölgeler için 12 nci maddeye bakınız.",
        "tr",
        page=10,
    ),
]


class NoWaitPacer(Pacer):
    def __init__(self):
        async def no_sleep(_: float) -> None:
            return None

        super().__init__(10**9, 10**9, sleep=no_sleep)


@pytest.fixture
async def loaded(db):
    embedder = FakeEmbedder()
    await sync_source(db, sample_source("eu-sample", "en", "EU"), EU_CHUNKS)
    await sync_source(db, sample_source("tr-sample", "tr", "TR"), TR_CHUNKS)
    stats = await embed_pending(db, embedder, make_settings(), NoWaitPacer())
    assert stats.embedded == len(EU_CHUNKS) + len(TR_CHUNKS)
    return embedder


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
