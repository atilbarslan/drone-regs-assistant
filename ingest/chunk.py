"""Sections, chunks and the size-based splitter shared by all parsers.

Parsers turn a document into Sections along its legal structure (an article, a rule, an AMC or
GM). split_section() keeps a section whole when it is short enough and otherwise cuts it into
overlapping chunks at paragraph, then sentence, then word boundaries.

Sizes are in estimated tokens. There is no tokenizer here (the Gemini tokenizer is an API
call), so tokens are estimated from characters; see CHARS_PER_TOKEN.
"""

import re
from dataclasses import asdict, dataclass, field

# Rough average for English prose. Turkish words are longer and may split into more tokens, so
# Turkish chunks are probably somewhat larger in real tokens than estimated here.
CHARS_PER_TOKEN = 4
MAX_TOKENS = 800  # a section up to this size stays one chunk
TARGET_TOKENS = 600  # pieces of a longer section aim for this size
OVERLAP_TOKENS = 60  # text repeated from the end of the previous piece
MIN_TOKENS = 150  # a smaller last piece is merged into the one before it if that fits


@dataclass(frozen=True)
class Paragraph:
    text: str
    page: int | None = None


@dataclass(frozen=True)
class Section:
    section_ref: str
    heading: str
    paragraphs: tuple[Paragraph, ...]
    page: int | None = None  # where the section starts


@dataclass(frozen=True)
class Chunk:
    source_id: str
    section_ref: str
    heading: str
    page: int | None
    language: str
    version: str
    chunk_index: int  # position within the section, starting at 0
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


def estimate_tokens(text: str) -> int:
    return -(-len(text) // CHARS_PER_TOKEN)


_SENTENCE_END = re.compile(r"(?<=[.;:])\s+")


def _pieces(paragraph: Paragraph, limit_chars: int) -> list[Paragraph]:
    """Split one paragraph that is longer than limit_chars at sentence, then word boundaries."""
    if len(paragraph.text) <= limit_chars:
        return [paragraph]
    out: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(paragraph.text):
        words = sentence.split(" ") if len(sentence) > limit_chars else [sentence]
        for word in words:
            candidate = f"{current} {word}" if current else word
            if len(candidate) <= limit_chars or not current:
                current = candidate
            else:
                out.append(current)
                current = word
    if current:
        out.append(current)
    return [Paragraph(text, paragraph.page) for text in out]


def _tail(text: str, max_chars: int) -> str:
    """The end of text, at most max_chars long, starting at a word boundary."""
    if len(text) <= max_chars:
        return text
    cut = text[-max_chars:]
    space = cut.find(" ")
    return cut[space + 1 :] if space != -1 else cut


def split_section(section: Section) -> list[tuple[str, int | None]]:
    """Return (text, page) pieces for a section; page is where each piece starts."""
    paragraphs = [p for p in section.paragraphs if p.text.strip()]
    if not paragraphs:
        return []
    whole = "\n".join(p.text for p in paragraphs)
    if estimate_tokens(whole) <= MAX_TOKENS:
        return [(whole, paragraphs[0].page or section.page)]

    target = TARGET_TOKENS * CHARS_PER_TOKEN
    overlap = OVERLAP_TOKENS * CHARS_PER_TOKEN
    units = [piece for p in paragraphs for piece in _pieces(p, target)]

    groups: list[list[Paragraph]] = []
    current: list[Paragraph] = []
    size = 0
    for unit in units:
        if current and size + len(unit.text) + 1 > target:
            groups.append(current)
            current, size = [], 0
        current.append(unit)
        size += len(unit.text) + 1
    if current:
        groups.append(current)

    # Merge a short last group into the previous one when the result, overlap included, stays
    # within MAX_TOKENS.
    if len(groups) > 1:
        last = "\n".join(u.text for u in groups[-1])
        joined = "\n".join(u.text for u in groups[-2] + groups[-1])
        fits = estimate_tokens(joined) + OVERLAP_TOKENS <= MAX_TOKENS
        if estimate_tokens(last) < MIN_TOKENS and fits:
            groups[-2:] = [groups[-2] + groups[-1]]

    result: list[tuple[str, int | None]] = []
    previous = ""
    for group in groups:
        body = "\n".join(u.text for u in group)
        text = f"{_tail(previous, overlap)}\n{body}" if previous else body
        result.append((text, group[0].page or section.page))
        previous = body
    return result


def chunk_sections(
    sections: list[Section], *, source_id: str, language: str, version: str
) -> list[Chunk]:
    chunks = []
    for section in sections:
        for index, (text, page) in enumerate(split_section(section)):
            chunks.append(
                Chunk(
                    source_id=source_id,
                    section_ref=section.section_ref,
                    heading=section.heading,
                    page=page,
                    language=language,
                    version=version,
                    chunk_index=index,
                    text=text,
                )
            )
    return chunks


@dataclass
class ParseResult:
    """What a parser produced, plus what it could not place, for the build report."""

    sections: list[Section] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # left out on purpose (front matter, TOC)
    unrecognized: list[str] = field(default_factory=list)  # kept, reference not parsed
    approximate_page: list[str] = field(default_factory=list)  # page of the nearest bookmark
    without_page: list[str] = field(default_factory=list)  # no page number at all
