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
  language, and "Kıbrıs" alone is ambiguous; none of these counts.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

Jurisdiction = Literal["EU", "TR", "both", "none"]

_TURKISH_LETTERS = "a-zçğıöşü"
# Suffix after an apostrophe: AB'de, SHGM'nin, Türkiye'deki (straight or typographic quote).
_APOSTROPHE_SUFFIX = rf"(?:['’][{_TURKISH_LETTERS}]+)?"
# Names may also take the suffix without an apostrophe: Almanyada, Avrupadaki.
_ANY_SUFFIX = rf"(?:['’]?[{_TURKISH_LETTERS}]*)"


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
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia", "Czech Republic",
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
    Rule("EU", _words(EU_COUNTRIES, _ANY_SUFFIX)),
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
    Rule(
        "TR",
        re.compile(
            r"\b(Turkish\s+(?:rules?|law|laws|regulations?|airspace|authorit(?:y|ies)|"
            r"civil aviation))",
            re.IGNORECASE,
        ),
    ),
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
