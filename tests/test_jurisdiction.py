import pytest

from app.jurisdiction import EU_COUNTRIES, detect


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
        ("What do Turkish rules say about BVLOS?", "TR", ["Turkish rules"]),
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
        ("İstanbul Avrupa yakasında drone uçurabilir miyim?", "none", []),
        ("Lütfen Türkçe cevap ver: gece uçuşu serbest mi?", "none", []),
        ("Please answer in Turkish: is night flying allowed?", "none", []),
        ("Kıbrıs'ta drone uçurulur mu?", "none", []),  # ambiguous: island, not only the EU state
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
