from ingest.parse_shgm import Line, parse_lines

MARGIN, INDENT, CENTER = 71.0, 106.0, 240.0


def test_articles_headings_paragraphs_and_pages():
    lines = [
        Line("ÖRNEK TALİMATI", 1, CENTER),
        Line("BİRİNCİ BÖLÜM", 1, CENTER),
        Line("Genel Hükümler", 1, CENTER),
        Line("Amaç", 1, INDENT),
        Line("MADDE 1 – (1) Bu örnek talimatın amacı, deneme", 1, INDENT),
        Line("metni üretmektir.", 1, MARGIN),
        Line("Tanımlar", 1, INDENT),
        Line("MADDE 2 – (1) Bu örnekte geçen;", 1, INDENT),
        Line("a) Komuta-", 1, INDENT),
        Line("kontrol: örnek bir tanım,", 2, MARGIN),
        Line("b) Uçuş zarfı: başka bir örnek.", 2, INDENT),
        Line("İKİNCİ BÖLÜM", 2, CENTER),
        Line("Son Hükümler", 2, CENTER),
        Line("Geçiş süreci", 2, INDENT),
        Line("GEÇİCİ MADDE 1 – (1) Örnek bir geçiş hükmü.", 2, INDENT),
    ]

    result = parse_lines(lines)

    assert [(s.section_ref, s.heading, s.page) for s in result.sections] == [
        ("Madde 1", "Amaç", 1),
        ("Madde 2", "Tanımlar", 1),
        ("Geçici Madde 1", "Geçiş süreci", 2),
    ]
    assert [p.text for p in result.sections[0].paragraphs] == [
        "(1) Bu örnek talimatın amacı, deneme metni üretmektir."
    ]
    # Chapter lines are not article text; a hyphen at a line end joins the word.
    assert [(p.text, p.page) for p in result.sections[1].paragraphs] == [
        ("(1) Bu örnekte geçen;", 1),
        ("a) Komuta-kontrol: örnek bir tanım,", 1),
        ("b) Uçuş zarfı: başka bir örnek.", 2),
    ]
    assert result.skipped == ["title page: ÖRNEK TALİMATI / BİRİNCİ BÖLÜM / Genel Hükümler"]
    assert result.unrecognized == []


def test_heading_is_two_lines_when_it_wraps():
    lines = [
        Line("MADDE 1 – (1) İlk madde.", 1, INDENT),
        Line("Uzun bir başlığın", 1, INDENT),
        Line("ikinci satırı", 1, INDENT),
        Line("MADDE 2 – (1) İkinci madde.", 1, INDENT),
    ]

    result = parse_lines(lines)

    assert result.sections[1].heading == "Uzun bir başlığın ikinci satırı"
    assert [p.text for p in result.sections[0].paragraphs] == ["(1) İlk madde."]


def test_reports_article_without_heading():
    result = parse_lines([Line("MADDE 1 – (1) Başlıksız bir madde.", 1, INDENT)])

    assert result.sections[0].heading == "Madde 1"
    assert result.unrecognized == ["Madde 1: no heading line found"]
