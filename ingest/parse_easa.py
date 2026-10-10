"""Parse the EASA Easy Access Rules XML export into Sections.

The export is a Word document saved as a single XML package ("flat OPC"). Its table of contents
(er:toc) lists one er:topic per article, rule, AMC or GM, with the title, the content type
(IR = Implementing Regulation (EU) 2019/947, DR = Delegated Regulation (EU) 2019/945, AMC, GM)
and the id of the Word content control (w:sdt) in the body that holds its text.

The XML has no page numbers. They come from the bookmarks of the PDF edition, whose titles
match the topic titles.
"""

import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from pathlib import Path

from pypdf import PdfReader

from ingest.chunk import Paragraph, ParseResult, Section

PKG = "{http://schemas.microsoft.com/office/2006/xmlPackage}"
ER = "{http://www.easa.europa.eu/erules-export}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

IR_REGULATION = "2019/947"
DR_REGULATION = "2019/945"

# The "short description" paragraph names the act that last amended a topic (for example
# "ED Decision 2022/002/R"); it is metadata, not rule text.
METADATA_STYLE = "Dxshortdesc"


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _key(title: str) -> str:
    """Comparison key for titles: no whitespace at all, case-folded."""
    return re.sub(r"\s+", "", title.replace("\xa0", " ")).casefold()


# --- section references ------------------------------------------------------------------------

_SUFFIX = r"(?:\s?\([0-9a-z]+\))*"
_ITEM = rf"(?:Artic\w*\s*\d+|UAS\.[A-Z]+(?:-\d+)?\.\d{{3}}|Appendix\s*\d+){_SUFFIX}"
_MORE = rf"(?:\s*(?:,|\band\b|&)\s*(?:{_ITEM}|\([0-9a-z]+\){_SUFFIX}))*"
_AMC_GM = re.compile(rf"^((?:AMC|GM)\d+(?:bis)?(?:\s+(?:to\s+)?AMC\d+)?\s+{_ITEM}{_MORE})\s*(.*)$")
_RULE = re.compile(r"^(UAS\.(?:OPEN|SPEC|LUC|STS-\d{2})\.\d{3})\s+(.*)$")
# Headings separate the number from the title with a hyphen, an en dash or an em dash.
_ARTICLE = re.compile(r"^Article\s+(\d+[a-z]?)\s*[-\u2013\u2014]\s*(.*)$")
_PART = re.compile(r"^PART\s+(\d+)\s*[-\u2013\u2014]\s*(.*)$")
_APPENDIX = re.compile(r"^Appendix\s+(\d+)\s*[-\u2013\u2014]?\s*(.*)$")
_ATTACHMENT = re.compile(r"^ATTACHMENT\s+([A-Z])\s*:\s*(.*)$")
_AMC_ANNEX = re.compile(r"^Annex\s+([A-Z])\s+to\s+")
_STS = re.compile(r"UAS\.(STS-\d{2})\.")


def section_ref(
    title: str, content_type: str, last_sts: str | None = None, last_amc: str | None = None
) -> tuple[str, str] | None:
    """Split a topic title into (section_ref, heading), or None if it has no known pattern.

    content_type is the topic's TypeOfContent ("IR (Implementing rule);", "DR (...)", ...).
    last_sts and last_amc are the most recent standard scenario (e.g. "STS-01") and AMC
    reference before this topic; attachments and AMC annexes are named after them.
    """
    title = normalize(title)
    regulation = DR_REGULATION if content_type.startswith("DR") else IR_REGULATION

    if m := _RULE.match(title):
        return m.group(1), m.group(2)
    if m := _AMC_GM.match(title):
        ref = re.sub(r"\bArtic\w*\s*(\d)", r"Article \1", m.group(1))  # also fixes "Articsle"
        return normalize(ref), m.group(2) or normalize(ref)
    if m := _ARTICLE.match(title):
        return f"Article {m.group(1)} ({regulation})", m.group(2)
    if m := _PART.match(title):
        return f"Part {m.group(1)} ({DR_REGULATION} Annex)", m.group(2)
    if m := _APPENDIX.match(title):
        return f"Appendix {m.group(1)} ({IR_REGULATION})", m.group(2) or title
    if m := _ATTACHMENT.match(title):
        prefix = f"{last_sts} " if last_sts else ""
        return f"{prefix}Attachment {m.group(1)}", m.group(2)
    if (m := _AMC_ANNEX.match(title)) and last_amc:
        # The export has two sets of annexes A-E titled "... to AMC1 ... Article 11": one after
        # AMC1 Article 11 and one after AMC1bis Article 11. Naming each annex after the AMC it
        # follows keeps the two sets apart; the official title stays as the heading.
        return f"{last_amc} Annex {m.group(1)}", title
    if title == "Powers and recitals":
        return f"Recitals ({regulation})", title
    if title == "List of Abbreviations":
        return title, title
    return None


# --- Word numbering ----------------------------------------------------------------------------

_ROMAN = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"),
          (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]  # fmt: skip


def _roman(n: int) -> str:
    out = ""
    for value, letters in _ROMAN:
        while n >= value:
            out += letters
            n -= value
    return out


def _format_number(n: int, fmt: str) -> str:
    match fmt:
        case "decimal":
            return str(n)
        case "lowerLetter" | "upperLetter":
            letter = chr(ord("a") + (n - 1) % 26) * ((n - 1) // 26 + 1)
            return letter.upper() if fmt == "upperLetter" else letter
        case "lowerRoman":
            return _roman(n)
        case "upperRoman":
            return _roman(n).upper()
        case _:
            return ""


class Numbering:
    """Generates the labels Word draws for automatically numbered paragraphs.

    Most EASA list labels such as "(1)" or "(a)" are typed into the text, but some lists use
    Word numbering, whose labels exist only in numbering.xml. The numbering is set either on
    the paragraph or on its paragraph style (in this export, the style-level lists are all
    dash bullets). Counters are kept per list instance (w:num); restarts that depend on other
    Word settings are not modelled.
    """

    def __init__(self, numbering_root: ET.Element | None, styles_root: ET.Element | None = None):
        # numId -> ilvl -> (format, label template such as "(%1)", start value)
        self.levels: dict[str, dict[int, tuple[str, str, int]]] = {}
        self.counters: dict[str, list[int]] = {}
        # styleId -> the style's w:numPr
        self.style_numbering: dict[str, ET.Element] = {}
        if styles_root is not None:
            for style in styles_root.findall(f"{W}style"):
                num_pr = style.find(f"{W}pPr/{W}numPr")
                if num_pr is not None and num_pr.find(f"{W}numId") is not None:
                    self.style_numbering[style.get(f"{W}styleId")] = num_pr
        if numbering_root is None:
            return
        abstract = {}
        for an in numbering_root.findall(f"{W}abstractNum"):
            abstract[an.get(f"{W}abstractNumId")] = {
                int(lvl.get(f"{W}ilvl")): _level(lvl) for lvl in an.findall(f"{W}lvl")
            }
        for num in numbering_root.findall(f"{W}num"):
            ref = num.find(f"{W}abstractNumId")
            levels = dict(abstract.get(ref.get(f"{W}val"), {})) if ref is not None else {}
            for override in num.findall(f"{W}lvlOverride"):
                ilvl = int(override.get(f"{W}ilvl"))
                start = override.find(f"{W}startOverride")
                if start is not None and ilvl in levels:
                    fmt, text, _ = levels[ilvl]
                    levels[ilvl] = (fmt, text, int(start.get(f"{W}val")))
            self.levels[num.get(f"{W}numId")] = levels

    def label(self, paragraph: ET.Element) -> str:
        num_pr = paragraph.find(f"{W}pPr/{W}numPr")
        if num_pr is None:
            style = paragraph.find(f"{W}pPr/{W}pStyle")
            num_pr = self.style_numbering.get(style.get(f"{W}val")) if style is not None else None
        if num_pr is None:
            return ""
        num_id_el, ilvl_el = num_pr.find(f"{W}numId"), num_pr.find(f"{W}ilvl")
        num_id = num_id_el.get(f"{W}val") if num_id_el is not None else None
        ilvl = int(ilvl_el.get(f"{W}val")) if ilvl_el is not None else 0
        levels = self.levels.get(num_id or "")
        if not levels or ilvl not in levels:
            return ""
        counters = self.counters.setdefault(num_id, [0] * 9)
        if counters[ilvl] == 0:
            counters[ilvl] = levels[ilvl][2] - 1
        counters[ilvl] += 1
        for deeper in range(ilvl + 1, 9):
            counters[deeper] = 0

        fmt, template, _ = levels[ilvl]
        if fmt == "bullet":
            # Symbol-font bullets are private-use characters; show those as a plain bullet.
            mark = template.strip()
            return mark if mark and not "\ue000" <= mark[0] <= "\uf8ff" else "•"

        def substitute(m: re.Match) -> str:
            level = int(m.group(1)) - 1
            level_fmt = levels.get(level, (fmt, "", 1))[0]
            return _format_number(max(counters[level], 1), level_fmt)

        return normalize(re.sub(r"%(\d)", substitute, template)) if fmt != "none" else ""


def _level(lvl: ET.Element) -> tuple[str, str, int]:
    fmt = lvl.find(f"{W}numFmt")
    text = lvl.find(f"{W}lvlText")
    start = lvl.find(f"{W}start")
    return (
        fmt.get(f"{W}val") if fmt is not None else "decimal",
        text.get(f"{W}val") if text is not None else "",
        int(start.get(f"{W}val")) if start is not None else 1,
    )


# --- body text ---------------------------------------------------------------------------------


def paragraph_text(paragraph: ET.Element) -> str:
    """Visible text of a w:p: text runs, with tabs and line breaks as spaces.

    Only w:r children are read, so tab-stop definitions in w:pPr and deleted text (w:delText)
    are ignored.
    """
    parts = []
    for run in paragraph.iter(f"{W}r"):
        for el in run:
            if el.tag == f"{W}t":
                parts.append(el.text or "")
            elif el.tag in (f"{W}tab", f"{W}br", f"{W}cr"):
                parts.append(" ")
            elif el.tag == f"{W}noBreakHyphen":
                parts.append("-")
    return normalize("".join(parts))


def _sdt_id(sdt: ET.Element) -> str | None:
    el = sdt.find(f"{W}sdtPr/{W}id")
    return el.get(f"{W}val") if el is not None else None


def _blocks(container: ET.Element, topic_ids: set[str]) -> Iterator[ET.Element]:
    """Paragraphs and tables in document order, skipping nested topics."""
    for child in container:
        if child.tag in (f"{W}p", f"{W}tbl"):
            yield child
        elif child.tag == f"{W}sdt":
            if _sdt_id(child) in topic_ids:
                continue
            content = child.find(f"{W}sdtContent")
            if content is not None:
                yield from _blocks(content, topic_ids)
        elif child.tag in (f"{W}sdtContent", f"{W}customXml"):
            yield from _blocks(child, topic_ids)


def _table_rows(table: ET.Element) -> list[str]:
    rows = []
    for tr in table.findall(f"{W}tr"):
        cells = [
            normalize(" ".join(paragraph_text(p) for p in tc.iter(f"{W}p")))
            for tc in tr.findall(f"{W}tc")
        ]
        while cells and not cells[0]:
            cells.pop(0)
        while cells and not cells[-1]:
            cells.pop()
        if cells:
            rows.append(" | ".join(cells))
    return rows


def topic_paragraphs(
    sdt: ET.Element, title: str, topic_ids: set[str], numbering: Numbering
) -> list[str]:
    """Body text of a topic, one string per paragraph or table row.

    The topic title, repeated in the body as a heading paragraph, is left out; subheadings
    inside the topic ("DEFINITION OF ...") are kept.
    """
    content = sdt.find(f"{W}sdtContent")
    if content is None:
        return []
    out = []
    for block in _blocks(content, topic_ids):
        if block.tag == f"{W}tbl":
            out.extend(_table_rows(block))
            continue
        style_el = block.find(f"{W}pPr/{W}pStyle")
        style = style_el.get(f"{W}val") if style_el is not None else ""
        text = paragraph_text(block)
        if style == METADATA_STYLE or (style.startswith("Heading") and _key(text) == _key(title)):
            continue
        label = numbering.label(block)
        if text:
            out.append(f"{label} {text}" if label else text)
    return out


# --- page numbers from the PDF bookmarks -------------------------------------------------------


def pdf_outline(pdf_path: Path) -> list[tuple[str, int | None]]:
    """(title, 1-based page) for every bookmark, in document order."""
    reader = PdfReader(pdf_path)
    out: list[tuple[str, int | None]] = []

    def walk(items: list) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item)
            else:
                page = reader.get_destination_page_number(item)
                out.append((item.title, page + 1 if page is not None and page >= 0 else None))

    walk(reader.outline)
    return out


class PageFinder:
    """Matches topic titles to bookmarks in order, so repeated titles get the right page."""

    def __init__(self, outline: list[tuple[str, int | None]]):
        self.keys = [_key(title) for title, _ in outline]
        self.pages = [page for _, page in outline]
        self.position = 0

    def find(self, title: str) -> int | None:
        key = _key(title)
        for i in range(self.position, len(self.keys)):
            if self.keys[i] == key:
                self.position = i + 1
                return self.pages[i]
        matches = [i for i, k in enumerate(self.keys) if k == key]
        return self.pages[matches[0]] if len(matches) == 1 else None


# --- whole document ----------------------------------------------------------------------------


def parse_package(root: ET.Element, outline: list[tuple[str, int | None]] | None) -> ParseResult:
    parts = {part.get(f"{PKG}name"): part for part in root.iter(f"{PKG}part")}
    numbering_part = parts.get("/word/numbering.xml")
    numbering_root = (
        numbering_part.find(f"{PKG}xmlData/{W}numbering") if numbering_part is not None else None
    )
    styles_part = parts.get("/word/styles.xml")
    styles_root = styles_part.find(f"{PKG}xmlData/{W}styles") if styles_part is not None else None
    numbering = Numbering(numbering_root, styles_root)

    toc = root.find(f".//{ER}toc")
    if toc is None:
        raise ValueError("no er:toc element: not an EASA eRules XML export")
    topics = list(toc.iter(f"{ER}topic"))
    topic_ids = {t.get("sdt-id") for t in topics}
    sdts = {_sdt_id(s): s for s in root.iter(f"{W}sdt")}
    pages = PageFinder(outline) if outline is not None else None

    result = ParseResult()
    last_sts = last_amc = None
    last_page = None  # page of the latest matched bookmark, topic or heading
    seen_pages: dict[tuple[str, tuple[str, ...]], int | None] = {}
    for item in toc.iter():
        if item.tag == f"{ER}heading":
            # Headings ("Cover Regulation to ...", "PART A ...") have bookmarks but no text.
            if pages is not None:
                last_page = pages.find(normalize(item.get("title") or "")) or last_page
            continue
        if item.tag != f"{ER}topic":
            continue
        title = normalize(item.get("source-title") or "")
        content_type = item.get("TypeOfContent") or ""
        sdt = sdts.get(item.get("sdt-id"))
        if not title or content_type.startswith("Easy access rules") or sdt is None:
            result.skipped.append(title or f"(untitled {content_type.rstrip(';') or 'topic'})")
            continue

        if m := _STS.search(title):
            last_sts = m.group(1)
        parsed = section_ref(title, content_type, last_sts, last_amc)
        if parsed is None:
            result.unrecognized.append(title)
            parsed = (title, title)
        ref, heading = parsed
        if ref.startswith("AMC") and not _AMC_ANNEX.match(title):
            last_amc = ref

        page = pages.find(title) if pages is not None else None
        if page is None and last_page is not None:
            # No bookmark of its own (e.g. "Powers and recitals"): use the bookmark before it,
            # which is where the section starts or the page just before.
            page = last_page
            result.approximate_page.append(ref)
        elif page is None:
            result.without_page.append(ref)
        last_page = page or last_page
        texts = topic_paragraphs(sdt, title, topic_ids, numbering)
        # Some STS AMC/GM are printed twice, under STS-01 and again under STS-02, with the
        # same text. Keeping one copy avoids returning the same passage twice in search.
        key = (ref, tuple(texts))
        if key in seen_pages:
            result.skipped.append(f"{ref} (repeated on page {page}; kept page {seen_pages[key]})")
            continue
        seen_pages[key] = page
        result.sections.append(
            Section(
                section_ref=ref,
                heading=heading,
                paragraphs=tuple(Paragraph(t, page) for t in texts),
                page=page,
            )
        )
    return result


def read_xml_zip(path: Path) -> ET.Element:
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".xml")]
        if len(names) != 1:
            raise ValueError(f"{path}: expected one XML file in the archive, found {names}")
        with archive.open(names[0]) as f:
            return ET.parse(f).getroot()


def parse_easa(xml_zip: Path, pdf: Path | None) -> ParseResult:
    outline = pdf_outline(pdf) if pdf is not None else None
    return parse_package(read_xml_zip(xml_zip), outline)
