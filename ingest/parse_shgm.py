"""Parse the SHGM SHT-İHA instruction (PDF) into Sections, one per article ("Madde").

Layout of the document: chapter lines ("BİRİNCİ BÖLÜM" plus a title line), then for each
article a heading line ("Amaç") followed by "MADDE 1 – (1) ...". Paragraphs and list items
start indented; continuation lines start at the left margin.

pdf_lines() reads positioned text lines with pdfminer.six; parse_lines() works on those lines
only, so it can be tested without a PDF.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTTextLine

from ingest.chunk import Paragraph, ParseResult, Section

ARTICLE = re.compile(r"^(GEÇİCİ MADDE|MADDE)\s+(\d+)\s*[–-]\s*(.*)$")
CHAPTER = re.compile(r"^[A-ZÇĞİÖŞÜ ]+\sBÖLÜM$")
SENTENCE_END = re.compile(r"[.:;]$")
PARAGRAPH_INDENT = 15.0  # points right of the left margin that mark a new paragraph
MAX_HEADING_LINES = 3


@dataclass(frozen=True)
class Line:
    text: str
    page: int
    x0: float


def _text_lines(element) -> Iterator[LTTextLine]:
    for child in element:
        if isinstance(child, LTTextLine):
            yield child
        elif hasattr(child, "__iter__"):
            yield from _text_lines(child)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def pdf_lines(pdf_path: Path) -> tuple[list[Line], int]:
    """Text lines in reading order, and how many lines were dropped as page furniture.

    Dropped: lines not entirely inside the page (the PDF carries a repeated number as a huge
    line that starts far outside the page on every page) and the page number, printed at the
    top or the bottom of the page.
    The body text sits in a form XObject, which pdfminer only lays out with all_texts=True.
    """
    lines: list[Line] = []
    dropped = 0
    for page_no, layout in enumerate(extract_pages(pdf_path, laparams=LAParams(all_texts=True)), 1):
        inside = []
        for line in _text_lines(layout):
            fully_inside = line.x0 >= 0 and line.y0 >= 0
            fully_inside &= line.x1 <= layout.width and line.y1 <= layout.height
            text = normalize(line.get_text())
            if not fully_inside:
                dropped += 1
            elif text:
                inside.append((line, text))
        inside.sort(key=lambda item: (-item[0].y1, item[0].x0))
        for position in (0, -1):
            if inside and inside[position][1] == str(page_no):
                inside.pop(position)
                dropped += 1
        lines.extend(Line(text, page_no, line.x0) for line, text in inside)
    return lines, dropped


def _join(left: str, right: str) -> str:
    # "komuta-" + "kontrol": a line ending in a hyphen right after a letter continues the word.
    if re.search(r"\w-$", left):
        return left + right
    return f"{left} {right}"


def _heading_start(
    lines: list[Line], article_index: int, floor: int, chapter_lines: set[int]
) -> int:
    """Index of the first heading line before the article line at article_index.

    Heading lines do not end in sentence punctuation, and the line before them ends a
    sentence (the previous article), is a chapter line, or is the start of the document.
    Returns article_index if no heading is found.
    """
    start = article_index
    while (
        start - 1 >= floor
        and start - 1 not in chapter_lines
        and article_index - (start - 1) <= MAX_HEADING_LINES
        and not SENTENCE_END.search(lines[start - 1].text)
    ):
        start -= 1
    if start == article_index:
        return article_index
    before = start - 1
    if start == floor or before in chapter_lines or SENTENCE_END.search(lines[before].text):
        return start
    return article_index


def parse_lines(lines: list[Line]) -> ParseResult:
    result = ParseResult()
    article_indexes = [i for i, line in enumerate(lines) if ARTICLE.match(line.text)]
    if not article_indexes:
        result.unrecognized.append("no 'MADDE N –' line found")
        return result
    left_margin = min(line.x0 for line in lines)

    # Chapter lines ("İKİNCİ BÖLÜM" and the title line after it) are structure, not text.
    chapter_lines = set()
    for i, line in enumerate(lines):
        if CHAPTER.match(line.text):
            chapter_lines.update({i, i + 1})

    # Where each article's heading starts; everything from there up to the next heading
    # belongs to that article.
    starts = []
    floor = 0
    for index in article_indexes:
        starts.append(_heading_start(lines, index, floor, chapter_lines))
        floor = index + 1

    preamble = [line.text for line in lines[: starts[0]] if line.text]
    if preamble:
        result.skipped.append(f"title page: {' / '.join(preamble)}")

    bounds = [*starts[1:], len(lines)]
    for start, index, end in zip(starts, article_indexes, bounds, strict=True):
        kind, number, first_text = ARTICLE.match(lines[index].text).groups()
        ref = f"Geçici Madde {number}" if kind.startswith("GEÇİCİ") else f"Madde {number}"
        heading = normalize(" ".join(line.text for line in lines[start:index]))
        if not heading:
            result.unrecognized.append(f"{ref}: no heading line found")
            heading = ref

        paragraphs: list[Paragraph] = []
        text, page = first_text, lines[index].page
        for i in range(index + 1, end):
            if i in chapter_lines:
                continue
            line = lines[i]
            if line.x0 - left_margin > PARAGRAPH_INDENT:
                if text:
                    paragraphs.append(Paragraph(text, page))
                text, page = line.text, line.page
            else:
                text = _join(text, line.text) if text else line.text
        if text:
            paragraphs.append(Paragraph(text, page))
        result.sections.append(Section(ref, heading, tuple(paragraphs), page=lines[start].page))
    return result


def parse_shgm(pdf_path: Path) -> ParseResult:
    lines, dropped = pdf_lines(pdf_path)
    result = parse_lines(lines)
    result.skipped.append(f"{dropped} lines of page furniture (page numbers, off-page text)")
    return result
