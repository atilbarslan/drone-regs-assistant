from ingest.chunk import (
    CHARS_PER_TOKEN,
    MAX_TOKENS,
    OVERLAP_TOKENS,
    Paragraph,
    Section,
    chunk_sections,
    estimate_tokens,
    split_section,
)


def sentence(i: int) -> str:
    return f"Sentence number {i} says something short about a sample rule."


def paragraph(i: int, page: int | None = None, sentences: int = 6) -> Paragraph:
    text = f"({i}) " + " ".join(sentence(i * 100 + j) for j in range(sentences))
    return Paragraph(text, page)


def test_short_section_stays_one_chunk():
    section = Section("Madde 1", "Amaç", (Paragraph("(1) Kısa bir örnek.", 3),), page=3)

    assert split_section(section) == [("(1) Kısa bir örnek.", 3)]


def test_empty_section_gives_no_chunks():
    assert split_section(Section("Appendix 1", "Empty", (Paragraph("  "),))) == []


def test_long_section_is_split_at_paragraphs_with_overlap():
    paragraphs = tuple(paragraph(i, page=10 + i // 10) for i in range(40))
    section = Section("UAS.OPEN.020", "Sample", paragraphs, page=10)

    pieces = split_section(section)

    assert len(pieces) > 1
    for text, _ in pieces:
        assert estimate_tokens(text) <= MAX_TOKENS
    # Every paragraph survives, and each piece after the first repeats the end of the one
    # before it.
    joined = "\n".join(text for text, _ in pieces)
    for p in paragraphs:
        assert p.text in joined
    for (previous, _), (current, _) in zip(pieces, pieces[1:], strict=False):
        overlap = current.split("\n", 1)[0]
        assert previous.endswith(overlap)
        assert len(overlap) <= OVERLAP_TOKENS * CHARS_PER_TOKEN
    # Pages follow the first paragraph of each piece, not the section start.
    assert pieces[0][1] == 10
    assert pieces[-1][1] == 13


def test_very_long_paragraph_is_split_at_sentences():
    long_paragraph = Paragraph(" ".join(sentence(i) for i in range(200)), 1)

    pieces = split_section(Section("Madde 4", "Tanımlar", (long_paragraph,)))

    assert len(pieces) > 1
    # Apart from the overlap line, every piece starts at the beginning of a sentence.
    for text, _ in pieces:
        body = text.split("\n")[-1]
        assert body.startswith("Sentence number")


def test_chunk_sections_fills_metadata():
    sections = [
        Section("Madde 1", "Amaç", (Paragraph("(1) Bir.", 1),), page=1),
        Section("Madde 2", "Kapsam", (Paragraph("(1) İki.", 2),), page=2),
    ]

    chunks = chunk_sections(sections, source_id="sample", language="tr", version="v1")

    assert [(c.section_ref, c.heading, c.page, c.chunk_index) for c in chunks] == [
        ("Madde 1", "Amaç", 1, 0),
        ("Madde 2", "Kapsam", 2, 0),
    ]
    assert {(c.source_id, c.language, c.version) for c in chunks} == {("sample", "tr", "v1")}
