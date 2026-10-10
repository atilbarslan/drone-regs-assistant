import pytest

from app.jurisdiction import EU_COUNTRIES, detect
from app.places import AMBIGUOUS_PLACES, EU_CITIES, TR_PROVINCES


@pytest.mark.parametrize(
    ("question", "expected", "terms"),
    [
        # --- EU, Turkish with suffixes ---
        ("AB'de 250 gramdan hafif drone için eğitim gerekir mi?", "EU", ["AB"]),
        ("AB’nin drone kuralları neler?", "EU", ["AB"]),  # typographic apostrophe
        ("Almanya'da drone uçurabilir miyim?", "EU", ["Almanya"]),
        ("Almanyada drone uçurmak serbest mi?", "EU", ["Almanya"]),  # suffix without apostrophe
        ("Avrupa'daki kurallara göre gece uçuşu", "EU", ["Avrupa"]),
        ("Avrupa Birliği'nde kayıt zorunlu mu?", "EU", ["Avrupa Birliği"]),
        ("İtalya'ya tatile drone götüreceğim", "EU", ["İtalya"]),
        ("ispanya'da uçuş izni", "EU", ["ispanya"]),  # lower case, dotted i
        ("Polonya'da uçuş", "EU", ["Polonya"]),
        ("EASA'ya göre C1 sınıfı nedir?", "EU", ["EASA", "C1"]),
        ("2019/947 sayılı tüzük neyi düzenler?", "EU", ["2019/947"]),
        ("A1 alt kategorisinde insanların üzerinden uçulur mu?", "EU", ["A1"]),
        ("açık kategoride azami yükseklik nedir?", "EU", ["açık kategori"]),
        ("SORA nasıl yapılır?", "EU", ["SORA"]),
        # --- EU, English ---
        ("Can I fly in Germany without registration?", "EU", ["Germany"]),
        ("What does the EU say about night flights?", "EU", ["EU"]),
        ("Rules in the open category for a C2 drone", "EU", ["open category", "C2"]),
        ("What is UAS.OPEN.020 about?", "EU", ["UAS.OPEN"]),
        ("Do I need an LUC for this?", "EU", ["LUC"]),
        ("Is STS-01 a standard scenario?", "EU", ["STS-01"]),
        ("European rules for the 'specific' category", "EU", ["European", "'specific' category"]),
        # --- TR ---
        ("Türkiye'de drone kaydı nasıl yapılır?", "TR", ["Türkiye"]),
        ("TÜRKİYE'DE gece uçuşu yasak mı?", "TR", ["TÜRKİYE"]),  # upper-case dotted İ
        ("SHGM'ye göre P1 lisansı kimlere verilir?", "TR", ["SHGM", "P1"]),
        ("Kırmızı bölgede uçuş için kimden izin alınır?", "TR", ["Kırmızı bölge"]),
        ("İHATTYS üzerinden uçuş bildirimi", "TR", ["İHATTYS"]),
        ("SHT-İHA ne zaman yürürlüğe girdi?", "TR", ["SHT-İHA"]),
        ("M2 sınıfı İHA için uçuşa elverişlilik belgesi", "TR", ["M2"]),
        ("Can I fly under SHGM rules at night?", "TR", ["SHGM"]),
        ("What do Turkish rules say about BVLOS?", "TR", ["Turkish"]),
        ("Is a licence needed in Turkey?", "TR", ["Turkey"]),
        ("Türk hava sahasında yabancı drone", "TR", ["Türk"]),
        # --- both ---
        ("AB ile Türkiye kurallarını karşılaştır", "both", ["AB", "Türkiye"]),
        ("Compare EASA and SHGM rules on pilot age", "both", ["EASA", "SHGM"]),
        ("Türk vatandaşıyım, Fransa'da uçabilir miyim?", "both", ["Türk", "Fransa"]),
        # --- none: no signal ---
        ("Drone ile gece uçabilir miyim?", "none", []),
        ("What is the minimum age for a remote pilot?", "none", []),
        ("İHA pilotu olmak için ne gerekir?", "none", []),
        # --- traps: words that look like signals but are not ---
        ("ABD'de drone kuralları", "none", []),  # USA, not AB
        ("Aboneliğim var, ab'de mi?", "none", []),  # lower-case "ab", "abone"
        ("A1 vitamini eksikliği", "none", []),  # code without a drone word
        ("A1 ihalesi ne zaman?", "none", []),  # "ihale" is not "İHA"
        ("C2 ehliyetim var", "none", []),  # driving licence class, no drone word
        ("Pilot lisansı nasıl alınır?", "none", []),  # "pilot" is not "Polonya"
        # Istanbul's European side: İstanbul makes it TR; "Avrupa yakası" adds nothing.
        ("İstanbul Avrupa yakasında drone uçurabilir miyim?", "TR", ["İstanbul"]),
        ("Avrupa yakasında drone uçurabilir miyim?", "none", []),
        ("Lütfen Türkçe cevap ver: gece uçuşu serbest mi?", "none", []),
        ("Please answer in Turkish: is night flying allowed?", "none", []),
        ("Kıbrıs'ta drone uçurulur mu?", "none", []),  # ambiguous: island, not only the EU state
        ("Can I fly a drone in Cyprus?", "none", []),  # same decision in English
        ("Europa League maçında drone", "none", []),  # "Europa" is not "Europe"
    ],
)
def test_detect(question, expected, terms):
    detection = detect(question)

    assert detection.jurisdiction == expected
    assert [t.text for t in detection.matched_terms] == terms


def test_terms_are_reported_per_side_in_question_order():
    detection = detect("SHGM ile EASA kurallarını ve Almanya'yı karşılaştır")

    assert detection.terms("TR") == ["SHGM"]
    assert detection.terms("EU") == ["EASA", "Almanya"]


def test_specific_rule_wins_over_general_one():
    # "Avrupa Birliği" is one term, not "Avrupa Birliği" plus "Avrupa".
    assert [t.text for t in detect("Avrupa Birliği kuralları").matched_terms] == ["Avrupa Birliği"]


def test_all_27_member_states_are_listed_in_both_languages():
    # 27 states; extra names: Çek Cumhuriyeti and Kıbrıs Cumhuriyeti / Güney Kıbrıs in Turkish,
    # Czech Republic and Holland in English.
    assert len(EU_COUNTRIES) == 27 * 2 + 3
    for name in ["Almanya", "Germany", "Çekya", "Czechia", "Hırvatistan", "Croatia"]:
        assert detect(f"{name} drone").jurisdiction == "EU", name


@pytest.mark.parametrize(
    ("question", "expected", "terms"),
    [
        # --- Turkish provinces ---
        ("İstanbul'da drone uçurabilir miyim?", "TR", ["İstanbul"]),
        ("Ankara'daki parklarda uçuş serbest mi?", "TR", ["Ankara"]),
        ("İzmir'de kayıt nasıl yapılır?", "TR", ["İzmir"]),
        ("istanbulda drone uçurmak", "TR", ["istanbul"]),  # lower case, no apostrophe
        ("ŞANLIURFA'DA UÇUŞ İZNİ", "TR", ["ŞANLIURFA"]),
        ("Antep'te drone", "TR", ["Antep"]),  # short form
        ("Can I fly my drone in Antalya?", "TR", ["Antalya"]),
        # names that are also words, written like places
        ("Van'da drone uçurmak serbest mi?", "TR", ["Van"]),
        ("Can I fly a drone in Batman?", "TR", ["Batman"]),
        ("Ordu ilinde izin gerekir mi?", "TR", ["Ordu"]),
        ("Van Gölü üzerinde drone uçurulur mu?", "TR", ["Van"]),
        ("Bursa'da kayıt", "TR", ["Bursa"]),
        # --- EU cities ---
        ("Can I fly a drone in Berlin?", "EU", ["Berlin"]),
        ("Münih'te drone kuralları", "EU", ["Münih"]),
        ("Varşova'da uçuş izni", "EU", ["Varşova"]),
        ("Krakov'da drone uçurulur mu?", "EU", ["Krakov"]),
        ("Flying near Kraków old town", "EU", ["Kraków"]),
        ("Brüksel'de drone", "EU", ["Brüksel"]),
        ("Is drone photography allowed in The Hague?", "EU", ["The Hague"]),
        ("Limasol'da drone uçurabilir miyim?", "EU", ["Limasol"]),
        ("Split'te drone uçurabilir miyim?", "EU", ["Split"]),
        ("Drone rules in Cork", "EU", ["Cork"]),
        ("Is it allowed in Sofia?", "EU", ["Sofia"]),
        # --- nationality adjectives ---
        ("What are the German drone rules?", "EU", ["German"]),
        ("Fransız kurallarına göre 250 gram altı drone kaydı gerekir mi?", "EU", ["Fransız"]),
        ("Under Polish law, do I need insurance?", "EU", ["Polish"]),
        ("İtalyan hava sahasında uçuş", "EU", ["İtalyan"]),
        ("Çek kurallarına göre kayıt", "EU", ["Çek"]),
        ("What do Dutch authorities require?", "EU", ["Dutch"]),
        ("Turkish drone rules for tourists", "TR", ["Turkish"]),
        # --- both ---
        ("İstanbul'dan Berlin'e drone götürebilir miyim?", "both", ["İstanbul", "Berlin"]),
        # --- traps ---
        ("Split the battery charge between two flights", "none", []),
        ("My van is parked by the field, can I fly there?", "none", []),
        ("Batman filmi için drone çekimi", "none", []),
        ("Başımda ağrı var, drone uçurabilir miyim?", "none", []),  # "ağrı" = pain
        ("Kara ordu tatbikatında drone", "none", []),  # "ordu" = army
        ("Bursa başvurdum, drone alacağım", "none", []),  # "bursa" = to a scholarship
        ("Kilisenin üstünden drone uçurabilir miyim?", "none", []),  # not "Kilis"
        ("Konyak fabrikası üzerinde uçuş", "none", []),  # not "Konya"
        ("Samsung telefonla drone kontrolü", "none", []),  # not "Samsun"
        ("Drone ile fotoğraf çekmek için izin gerekir mi?", "none", []),  # not "Çek"
        ("Please answer in German", "none", []),
        ("Almanca cevap verir misin?", "none", []),
        ("Is a French fries stand a crowd?", "none", []),
        ("Polish the propellers before flying", "none", []),
        ("Sofia wants to fly a drone", "none", []),  # a given name
        ("Have a nice flight", "none", []),
        ("Gölbaşı'nda drone uçurabilir miyim?", "none", []),  # district, not on the list
    ],
)
def test_detect_places_and_adjectives(question, expected, terms):
    detection = detect(question)

    assert detection.jurisdiction == expected
    assert [t.text for t in detection.matched_terms] == terms


def test_all_81_provinces_are_recognised():
    assert len(TR_PROVINCES) == 81
    for name in TR_PROVINCES:
        detection = detect(f"{name}'da drone uçurabilir miyim?")
        assert (detection.jurisdiction, detection.terms("TR")) == ("TR", [name]), name


def test_every_eu_city_name_is_recognised():
    names = [name for cities in EU_CITIES.values() for city in cities for name in city]
    for name in names:
        for question in (f"{name}'de drone", f"Can I fly a drone in {name}?"):
            detection = detect(question)
            assert (detection.jurisdiction, detection.terms("EU")) == ("EU", [name]), question


def test_every_member_state_has_cities_except_through_its_name():
    # Luxembourg's capital has the country's name; every state has at least two cities.
    assert len(EU_CITIES) == 27
    assert all(len(cities) >= 2 for cities in EU_CITIES.values())


def test_ambiguous_names_need_place_context():
    for name in AMBIGUOUS_PLACES:
        assert detect(f"{name.lower()} bir şey").jurisdiction == "none", name


@pytest.mark.parametrize(
    ("question", "expected", "terms"),
    [
        # "talimat" and "yeni/eski mevzuat" point to SHT-İHA ...
        ("Yeni talimata göre kayıt nasıl yapılır?", "TR", ["Yeni talimat"]),
        ("Talimata göre P0 kimdir?", "TR", ["Talimat", "P0"]),
        (
            "Yeni mevzuat ile eski mevzuat arasındaki farklar",
            "TR",
            ["Yeni mevzuat", "eski mevzuat"],
        ),
        ("İkinci el drone alacağım, yeni mevzuata göre adımlar neler?", "TR", ["yeni mevzuat"]),
        # ... but not a manufacturer's or user's instructions ...
        ("Üreticinin talimatlarına uymak zorunlu mu?", "none", []),
        ("Kullanım talimatı nerede yazıyor?", "none", []),
        ("Üretici kullanım talimatına göre uçuş", "none", []),
        # ... and they are weak: another signal decides.
        ("AB'nin yeni mevzuatı neler getiriyor?", "EU", ["AB"]),
        ("Almanya'daki yeni talimata göre kayıt", "EU", ["Almanya"]),
        # licence names of the previous Turkish instruction
        ("İHA1 belgem var, ne yapmalıyım?", "TR", ["İHA1"]),
        ("IHA-2 sertifikası geçerli mi?", "TR", ["IHA-2"]),
        ("iha0 ile uçabilir miyim?", "TR", ["iha0"]),
        ("İHA 2 tane aldım", "none", []),  # a count, not a licence
        # A1/A3 written with a slash; certificate and remote-pilot context
        ("A1/A3 sertifikam var", "EU", ["A1/A3"]),
        ("Do I need an A2 certificate?", "EU", ["A2"]),
        ("Remote pilot with A1 training", "EU", ["A1"]),
        ("A2 sınavı nasıl yapılır?", "EU", ["A2"]),
        ("A1 vitamini", "none", []),  # still not a drone code
        # P0-P2 alone: a weak Turkish signal (they never appear in the EU texts) ...
        ("What can a p1 holder do?", "TR", ["p1"]),
        ("Is night flying allowed with P0?", "TR", ["P0"]),
        ("P2 ile neler yapılır?", "TR", ["P2"]),
        # ... with a licence word it is a strong one, as before ...
        ("Can a P1 pilot fly in Germany?", "both", ["P1", "Germany"]),
        # ... and alone it gives way to a strong signal.
        ("What does P1 mean in Germany?", "EU", ["Germany"]),
        ("AB'de P2 ne demek?", "EU", ["AB"]),
        ("P3 nedir?", "none", []),  # not a Turkish licence level
        ("C1 vitamini", "none", []),  # EU codes keep needing a drone word
    ],
)
def test_detect_instruction_words_old_licences_and_certificates(question, expected, terms):
    detection = detect(question)

    assert detection.jurisdiction == expected
    assert [t.text for t in detection.matched_terms] == terms
