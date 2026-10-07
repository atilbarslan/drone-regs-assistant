"""Decide from the question alone whether it is about EU rules, Turkish rules, both, or neither.

A pure function over word lists: no network and no extra model call (the free-tier quota is
small). The result also lists the words that decided it, so the answer can say why.

Pitfalls handled here, each with a test:
- Turkish suffixes after an apostrophe ("AB'de", "Almanya'da", "SHGM'ye") or attached to a
  name ("Almanyada"); acronyms take only the apostrophe form, so "ABD" (USA) is not "AB".
- Dotted and dotless i: "İ" has no one-letter lower case, so i/ı/I/İ are matched as one class.
- Codes such as A1, C2, P1 or M0 count only when the question also has a drone word that fits
  the code ("A1 alt kategorisi", "C1 sınıfı", "P2 lisansı"), so "A1 vitamini" is ignored.
- "Avrupa yakası" (Istanbul's European side) is not Europe, "Türkçe"/"in Turkish" is a
  language, and "Kıbrıs"/"Cyprus" alone is ambiguous; none of these counts.
- Place names (81 Turkish provinces, EU capitals and largest cities, see app/places.py) take
  only real Turkish case endings when written without an apostrophe, so "Kilis" does not match
  "kilise", "Konya" not "konyak", "Samsun" not "Samsung". Names that are also common words
  ("Van", "Batman", "Ordu", "Split", "Cork", ...) count only when written like a place.
- Nationality adjectives ("German", "Fransız") count only before a word about rules,
  authorities, airspace or drones, so "in German", "Almanca" or "fotoğraf çek" do not.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

from app.places import (
    AMBIGUOUS_PLACES,
    EU_ADJECTIVES_EN,
    EU_ADJECTIVES_TR,
    EU_CITIES,
    TR_PROVINCE_VARIANTS,
    TR_PROVINCES,
)

Jurisdiction = Literal["EU", "TR", "both", "none"]

_TURKISH_LETTERS = "a-zçğıöşü"
# Suffix after an apostrophe: AB'de, SHGM'nin, Türkiye'deki (straight or typographic quote).
_APOSTROPHE_SUFFIX = rf"(?:['’][{_TURKISH_LETTERS}]+)?"
# Names may also take the suffix without an apostrophe: Almanyada, Avrupadaki.
_ANY_SUFFIX = rf"(?:['’]?[{_TURKISH_LETTERS}]*)"
# Place names: any suffix after an apostrophe, but without one only real case endings
# (locative, ablative, dative after a vowel, genitive, "-lı"), optionally plural. A bare vowel
# is not accepted, so "Kilis" + "e" (kilise, church) does not match.
_CASE_ENDINGS = (
    "da|de|ta|te|dan|den|tan|ten|daki|deki|taki|teki|ya|ye|yı|yi|yu|yü|nın|nin|nun|nün|lı|li|lu|lü"
)
_NAME_SUFFIX = rf"(?:['’][{_TURKISH_LETTERS}]+|(?:{_CASE_ENDINGS})(?:lar|ler)?)?"


def _letters(word: str) -> str:
    """Regex for a literal word: i/ı/I/İ interchangeable, spaces flexible."""
    out = []
    for char in word:
        if char in "iıIİ":
            out.append("[iıIİ]")
        elif char == " ":
            out.append(r"\s+")
        else:
            out.append(re.escape(char))
    return "".join(out)


def _words(words: list[str], suffix: str, flags: int = re.IGNORECASE) -> re.Pattern:
    alternatives = "|".join(_letters(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<![\w.])({alternatives}){suffix}(?![\w])", flags)


EU_COUNTRIES = [
    # Turkish names
    "Avusturya", "Belçika", "Bulgaristan", "Hırvatistan", "Güney Kıbrıs", "Kıbrıs Cumhuriyeti",
    "Çekya", "Çek Cumhuriyeti", "Danimarka", "Estonya", "Finlandiya", "Fransa", "Almanya",
    "Yunanistan", "Macaristan", "İrlanda", "İtalya", "Letonya", "Litvanya", "Lüksemburg", "Malta",
    "Hollanda", "Polonya", "Portekiz", "Romanya", "Slovakya", "Slovenya", "İspanya", "İsveç",
    # English names
    # "Cyprus" and "Kıbrıs" alone are ambiguous (the island is divided), so only the
    # Republic counts.
    "Austria", "Belgium", "Bulgaria", "Croatia", "Republic of Cyprus", "Czechia", "Czech Republic",
    "Denmark", "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Ireland", "Italy",
    "Latvia", "Lithuania", "Luxembourg", "Netherlands", "Holland", "Poland", "Portugal",
    "Romania", "Slovakia", "Slovenia", "Spain", "Sweden",
]  # fmt: skip

# Drone words that make a code like A1 or C2 a drone code. "İHA" must end the word or take a
# suffix, so that "ihale" (tender) does not count.
_DRONE = r"drone\w*|dron\w*|[iİ]ha(?:['’]\w*|lar\w*|ları\w*)?\b|uas\b|uav\w*|unmanned|insansız"
_CATEGORY_CONTEXT = re.compile(
    rf"\b(?:kategor\w*|category|categories|subcategory|{_DRONE}|uçuş\w*|uçur\w*|uçmak|"
    rf"flight\w*|fly\w*|operasyon\w*|operation\w*)",
    re.IGNORECASE,
)
_CLASS_CONTEXT = re.compile(rf"\b(?:sınıf\w*|class\w*|etiket\w*|label\w*|{_DRONE})", re.IGNORECASE)
_LICENCE_CONTEXT = re.compile(r"\b(?:lisans\w*|licen[cs]e\w*|pilot\w*)", re.IGNORECASE)


@dataclass(frozen=True)
class Rule:
    jurisdiction: Literal["EU", "TR"]
    pattern: re.Pattern
    context: re.Pattern | None = None  # the question must also match this


def _code(pattern: str) -> re.Pattern:
    """A short code (A1, C2, P1, M0) as a separate token."""
    return re.compile(rf"(?<![\w.])({pattern})(?![\w.])", re.IGNORECASE)


_QUOTE = "['‘’\"]"


def _places(names: list[str]) -> re.Pattern:
    return _words([n for n in names if n not in AMBIGUOUS_PLACES], _NAME_SUFFIX)


def _ambiguous_places(names: list[str]) -> list[re.Pattern]:
    """A name that is also a common word counts only when written like a place: with an
    apostrophe suffix ("Van'da"), after a preposition with a capital letter ("in Batman"), or
    before "ili"/"şehri"/"kenti" ("Ordu ili")."""
    words = [n for n in names if n in AMBIGUOUS_PLACES]
    if not words:
        return []
    alternatives = "|".join(_letters(w) for w in sorted(words, key=len, reverse=True))
    return [
        re.compile(rf"(?<![\w.])({alternatives})['’][{_TURKISH_LETTERS}]+(?![\w])"),
        re.compile(rf"(?<![\w])(?i:in|at|near|around|to|from|over)\s+({alternatives})(?![\w'’])"),
        re.compile(
            rf"(?<![\w.])({alternatives})\s+(?i:{_letters('il')}|{_letters('ili')}\w*|"
            rf"{_letters('ilçe')}\w*|şehr\w*|kent\w*|merkez\w*|göl\w*)(?![\w])"
        ),
    ]


# Words about rules, authorities, airspace or drones that make a nationality adjective count.
_EN_RULE_NOUNS = (
    r"rules?|law|laws|legislation|regulations?|regulators?|airspace|authorit(?:y|ies)|aviation|"
    r"civil|drones?|UAS|UAV|registration|operators?|pilots?|licen[cs]es?|requirements?|"
    r"government|police|territory|cit(?:y|ies)|airports?|borders?|skies"
)
_TR_RULE_NOUNS = (
    rf"kural\w*|mevzuat\w*|yasa\w*|kanun\w*|düzenleme\w*|yönetmelik\w*|hava\s+saha\w*|"
    rf"sivil|havacılık\w*|otorite\w*|makam\w*|drone\w*|dron\w*|{_letters('İHA')}\w*|"
    rf"pilot\w*|lisans\w*|kayıt\w*|kayd\w*|tescil\w*|polis\w*|hükümet\w*|devlet\w*|"
    rf"şehir\w*|şehr\w*|kent\w*|havaliman\w*|sınır\w*|toprak\w*|vatandaş\w*"
)


def _adjectives_en(adjectives: list[str]) -> re.Pattern:
    # Capitalised, as English writes nationalities: "polish the propellers" is not Polish.
    alternatives = "|".join(sorted(adjectives, key=len, reverse=True))
    return re.compile(rf"(?<![\w])({alternatives})\s+(?i:{_EN_RULE_NOUNS})(?![\w])")


def _adjectives_tr(adjectives: list[str]) -> re.Pattern:
    alternatives = "|".join(_letters(a) for a in sorted(adjectives, key=len, reverse=True))
    return re.compile(rf"(?<![\w])({alternatives})\s+(?:{_TR_RULE_NOUNS})(?![\w])", re.IGNORECASE)


_EU_CITY_NAMES = [name for cities in EU_CITIES.values() for city in cities for name in city]
_TR_PLACE_NAMES = TR_PROVINCES + TR_PROVINCE_VARIANTS

# Rules are tried in order, and a match that overlaps an earlier one is ignored, so the more
# specific rules ("Avrupa Birliği") come before the general ones ("Avrupa").
RULES: list[Rule] = [
    # --- EU ---
    Rule("EU", _words(["Avrupa Birliği", "Avrupa Birliğ", "European Union"], _ANY_SUFFIX)),
    Rule("EU", _words(["AB", "EU"], _APOSTROPHE_SUFFIX, flags=0)),  # upper case only
    Rule("EU", _words(["EASA"], _APOSTROPHE_SUFFIX)),
    # "Avrupa yakası" is Istanbul's European side, not the EU.
    Rule(
        "EU",
        re.compile(
            rf"(?<![\w.])(Avrupa(?!\s+yakas)|European|Europe){_ANY_SUFFIX}(?![\w])", re.IGNORECASE
        ),
    ),
    Rule("EU", _words(EU_COUNTRIES, _NAME_SUFFIX)),
    Rule("EU", _places(_EU_CITY_NAMES)),
    *[Rule("EU", pattern) for pattern in _ambiguous_places(_EU_CITY_NAMES)],
    Rule("EU", _adjectives_en(EU_ADJECTIVES_EN)),
    Rule("EU", _adjectives_tr(EU_ADJECTIVES_TR)),
    Rule("EU", re.compile(r"(?<![\w/])(2019/94[57])(?![\w/])")),
    Rule(
        "EU",
        re.compile(
            rf"(?<![\w])((?:open|specific|certified|{_QUOTE}(?:open|specific|certified){_QUOTE})"
            r"\s+categor(?:y|ies))",
            re.IGNORECASE,
        ),
    ),
    Rule(
        "EU",
        re.compile(
            rf"(?<![\w])((?:{_letters('açık')}|spesifik|sertifikal{_letters('ı')})\s+kategori)\w*",
            re.IGNORECASE,
        ),
    ),
    Rule("EU", re.compile(r"\b(UAS\.(?:OPEN|SPEC|LUC|STS)\b|STS-0[12])", re.IGNORECASE)),
    Rule("EU", _words(["SORA", "LUC"], _APOSTROPHE_SUFFIX, flags=0)),
    Rule("EU", _code("A[123]"), _CATEGORY_CONTEXT),
    Rule("EU", _code("C[0-6]"), _CLASS_CONTEXT),
    # --- TR ---
    Rule("TR", _words(["Türkiye", "Turkiye", "Turkey"], _ANY_SUFFIX)),
    # "Türk" as a word ("Türk hava sahası"), never "Türkçe"; "Turkish" only next to a word
    # about rules, since "in Turkish" names the language.
    Rule(
        "TR",
        re.compile(rf"(?<![\w.])(Türk)(?!çe|ce){_APOSTROPHE_SUFFIX}(?![\w])", re.IGNORECASE),
    ),
    Rule("TR", _adjectives_en(["Turkish"])),
    Rule("TR", _places(_TR_PLACE_NAMES)),
    *[Rule("TR", pattern) for pattern in _ambiguous_places(_TR_PLACE_NAMES)],
    Rule("TR", _words(["SHGM"], _APOSTROPHE_SUFFIX)),
    Rule("TR", _words(["Sivil Havacılık Genel Müdürlüğü"], _ANY_SUFFIX)),
    Rule("TR", re.compile(rf"\b(SHT[-\s]?{_letters('İ')}HA){_APOSTROPHE_SUFFIX}", re.IGNORECASE)),
    Rule("TR", _words(["İHATTYS", "KDM-ERP", "KDM-ORG"], _APOSTROPHE_SUFFIX)),
    Rule(
        "TR",
        re.compile(
            rf"(?<![\w])((?:{_letters('yeşil')}|turuncu|{_letters('kırmızı')})\s+bölge)\w*",
            re.IGNORECASE,
        ),
    ),
    Rule("TR", _code("P[0-2]"), _LICENCE_CONTEXT),
    Rule("TR", _code("M[0-3]"), _CLASS_CONTEXT),
]


@dataclass(frozen=True)
class MatchedTerm:
    text: str  # as written in the question, without a Turkish suffix
    jurisdiction: Literal["EU", "TR"]


@dataclass(frozen=True)
class Detection:
    jurisdiction: Jurisdiction
    matched_terms: list[MatchedTerm] = field(default_factory=list)

    def terms(self, jurisdiction: Literal["EU", "TR"]) -> list[str]:
        return [t.text for t in self.matched_terms if t.jurisdiction == jurisdiction]


def detect(question: str) -> Detection:
    found: list[tuple[int, MatchedTerm]] = []
    taken: list[tuple[int, int]] = []  # spans already matched by an earlier rule
    seen: set[tuple[str, str]] = set()
    for rule in RULES:
        if rule.context is not None and not rule.context.search(question):
            continue
        for match in rule.pattern.finditer(question):
            start, end = match.span()
            if any(start < t_end and t_start < end for t_start, t_end in taken):
                continue
            taken.append((start, end))
            text = re.sub(r"\s+", " ", match.group(1)).strip()
            key = (rule.jurisdiction, text.casefold())
            if key not in seen:
                seen.add(key)
                found.append((match.start(1), MatchedTerm(text, rule.jurisdiction)))
    terms = [term for _, term in sorted(found, key=lambda item: item[0])]
    sides = {t.jurisdiction for t in terms}
    if sides == {"EU", "TR"}:
        result: Jurisdiction = "both"
    elif sides:
        result = sides.pop()
    else:
        result = "none"
    return Detection(result, terms)
