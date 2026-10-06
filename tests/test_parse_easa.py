import xml.etree.ElementTree as ET

import pytest

from ingest.parse_easa import PageFinder, parse_package, section_ref

IR = "IR (Implementing rule);"
DR = "DR (Delegated rule);"
AMC = "AMC to IR (Acceptable means of compliance to implementing rule);"
GM = "GM to IR (Guidance material to implementing rule);"


@pytest.mark.parametrize(
    ("title", "content_type", "context", "expected"),
    [
        ("UAS.OPEN.020 Sample rule", IR, {}, ("UAS.OPEN.020", "Sample rule")),
        ("UAS.STS-02.050 Sample rule", IR, {}, ("UAS.STS-02.050", "Sample rule")),
        ("AMC1 UAS.SPEC.050(1)(d)  Sample", AMC, {}, ("AMC1 UAS.SPEC.050(1)(d)", "Sample")),
        ("GM1\xa0Article\xa02(3)\xa0Sample", GM, {}, ("GM1 Article 2(3)", "Sample")),
        (
            "AMC1 UAS.OPEN.020(5)(c) and (d), UAS.OPEN.030(3) Sample heading",
            AMC,
            {},
            ("AMC1 UAS.OPEN.020(5)(c) and (d), UAS.OPEN.030(3)", "Sample heading"),
        ),
        # A typo in a source title is corrected in the reference.
        (
            "GM1 Articsle 2(28), (29) and (33) Sample",
            GM,
            {},
            ("GM1 Article 2(28), (29) and (33)", "Sample"),
        ),
        ("GM1 to AMC1 Article 14(6) Sample", GM, {}, ("GM1 to AMC1 Article 14(6)", "Sample")),
        ("AMC1bis Article 11 Sample", AMC, {}, ("AMC1bis Article 11", "Sample")),
        ("GM1 UAS.STS-01.030(5)&(6) Sample", GM, {}, ("GM1 UAS.STS-01.030(5)&(6)", "Sample")),
        # Article numbers repeat between the two regulations, so the reference names it.
        ("Article 4 - Sample", IR, {}, ("Article 4 (2019/947)", "Sample")),
        ("Article 4 - Sample", DR, {}, ("Article 4 (2019/945)", "Sample")),
        ("PART 3 — Sample", DR, {}, ("Part 3 (2019/945 Annex)", "Sample")),
        ("Appendix 2 — Sample", IR, {}, ("Appendix 2 (2019/947)", "Sample")),
        ("ATTACHMENT A: Sample", IR, {"last_sts": "STS-01"}, ("STS-01 Attachment A", "Sample")),
        (
            "Annex B to AMC1 to Article 11",
            AMC,
            {"last_amc": "AMC1bis Article 11"},
            ("AMC1bis Article 11 Annex B", "Annex B to AMC1 to Article 11"),
        ),
        ("Powers and recitals", DR, {}, ("Recitals (2019/945)", "Powers and recitals")),
        ("Something without a known pattern", IR, {}, None),
    ],
)
def test_section_ref(title, content_type, context, expected):
    assert section_ref(title, content_type, **context) == expected


def test_page_finder_assigns_repeated_titles_in_order():
    finder = PageFinder([("Article 1 - Scope", 3), ("Article 1 - Scope", 40), ("Other", 41)])

    assert finder.find("Article 1 - Scope") == 3
    assert finder.find("Article\xa01 -  Scope") == 40
    assert finder.find("Missing") is None


# --- a minimal export with the same structure as the real one ------------------------------------

NS = (
    'xmlns:pkg="http://schemas.microsoft.com/office/2006/xmlPackage" '
    'xmlns:er="http://www.easa.europa.eu/erules-export" '
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
)


def para(text: str, style: str = "", num: tuple[str, str] | None = None) -> str:
    props = f'<w:pStyle w:val="{style}"/>' if style else ""
    if num:
        props += f'<w:numPr><w:ilvl w:val="{num[1]}"/><w:numId w:val="{num[0]}"/></w:numPr>'
    runs = "".join(
        f"<w:r><w:t>{part}</w:t></w:r>" if part != "\t" else "<w:r><w:tab/></w:r>"
        for part in text.split("|")
    )
    return f"<w:p><w:pPr>{props}</w:pPr>{runs}</w:p>"


def sdt(sdt_id: str, body: str) -> str:
    props = f'<w:sdtPr><w:id w:val="{sdt_id}"/></w:sdtPr>'
    return f"<w:sdt>{props}<w:sdtContent>{body}</w:sdtContent></w:sdt>"


def package(toc: str, body: str) -> ET.Element:
    numbering = (
        '<w:numbering><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/>'
        '<w:numFmt w:val="lowerRoman"/><w:lvlText w:val="(%1)"/></w:lvl></w:abstractNum>'
        '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/>'
        '<w:lvlText w:val="—"/></w:lvl></w:abstractNum>'
        '<w:num w:numId="5"><w:abstractNumId w:val="0"/></w:num>'
        '<w:num w:numId="6"><w:abstractNumId w:val="1"/></w:num></w:numbering>'
    )
    styles = (
        '<w:styles><w:style w:styleId="bullet0"><w:pPr><w:numPr><w:numId w:val="6"/></w:numPr>'
        "</w:pPr></w:style></w:styles>"
    )
    xml = (
        f"<pkg:package {NS}>"
        f'<pkg:part pkg:name="/customXml/item1.xml"><pkg:xmlData><er:document><er:toc>{toc}'
        "</er:toc></er:document></pkg:xmlData></pkg:part>"
        f'<pkg:part pkg:name="/word/numbering.xml"><pkg:xmlData>{numbering}'
        "</pkg:xmlData></pkg:part>"
        f'<pkg:part pkg:name="/word/styles.xml"><pkg:xmlData>{styles}</pkg:xmlData></pkg:part>'
        f'<pkg:part pkg:name="/word/document.xml"><pkg:xmlData><w:document><w:body>{body}'
        "</w:body></w:document></pkg:xmlData></pkg:part></pkg:package>"
    )
    return ET.fromstring(xml)


def topic(title: str, sdt_id: str, content_type: str) -> str:
    return f'<er:topic source-title="{title}" sdt-id="{sdt_id}" TypeOfContent="{content_type}"/>'


def test_parse_package_reads_text_numbering_tables_and_pages():
    toc = (
        topic("Disclaimer", "9", "Easy access rules;")
        + '<er:heading title="Cover Regulation" sdt-id="8"/>'
        + topic("Article 1 - Sample subject", "1", IR)
        + topic("GM1 Article 1 Sample", "2", GM)
    )
    table = (
        "<w:tbl><w:tr><w:tc>" + para("") + "</w:tc><w:tc>" + para("Term") + "</w:tc><w:tc>"
        + para("Meaning") + "</w:tc></w:tr></w:tbl>"
    )  # fmt: skip
    article = (
        para("Article 1 - Sample subject", style="Heading3IR")
        + para("Regulation (EU) 2099/1", style="Dxshortdesc")
        + para("(1)|\t|An opening sentence.")
        + para("first item", num=("5", "0"))
        + para("second item", num=("5", "0"))
        + para("a dash item", style="bullet0")
        + table
        + para("A SUBHEADING", style="Heading4OrgManual")
        # A topic nested inside another belongs to itself only.
        + sdt("2", para("GM1 Article 1 Sample", style="Heading3GM") + para("Guidance text."))
    )
    root = package(toc, sdt("9", para("Disclaimer text.")) + sdt("1", article))
    outline = [("Disclaimer", 2), ("Cover Regulation", 5), ("Article 1 - Sample subject", 6),
               ("GM1 Article 1 Sample", 7)]  # fmt: skip

    result = parse_package(root, outline)

    assert [(s.section_ref, s.heading, s.page) for s in result.sections] == [
        ("Article 1 (2019/947)", "Sample subject", 6),
        ("GM1 Article 1", "Sample", 7),
    ]
    assert [p.text for p in result.sections[0].paragraphs] == [
        "(1) An opening sentence.",
        "(i) first item",
        "(ii) second item",
        "— a dash item",
        "Term | Meaning",
        "A SUBHEADING",
    ]
    assert [p.text for p in result.sections[1].paragraphs] == ["Guidance text."]
    assert result.skipped == ["Disclaimer"]
    assert result.unrecognized == result.without_page == result.approximate_page == []


def test_parse_package_drops_repeated_topics_and_estimates_missing_pages():
    toc = (
        '<er:heading title="Cover Regulation" sdt-id="8"/>'
        + topic("Powers and recitals", "1", IR)
        + topic("GM1 UAS.STS-01.030(4) Sample", "2", GM)
        + topic("GM1 UAS.STS-01.030(4) Sample", "3", GM)
    )
    body = (
        sdt("1", para("(1) A recital."))
        + sdt("2", para("Same guidance."))
        + sdt("3", para("Same guidance."))
    )
    outline = [("Cover Regulation", 20), ("GM1 UAS.STS-01.030(4) Sample", 30),
               ("GM1 UAS.STS-01.030(4) Sample", 35)]  # fmt: skip

    result = parse_package(package(toc, body), outline)

    assert [(s.section_ref, s.page) for s in result.sections] == [
        ("Recitals (2019/947)", 20),
        ("GM1 UAS.STS-01.030(4)", 30),
    ]
    assert result.approximate_page == ["Recitals (2019/947)"]
    assert result.skipped == ["GM1 UAS.STS-01.030(4) (repeated on page 35; kept page 30)"]
