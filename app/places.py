"""Place names and nationality adjectives used by app/jurisdiction.py. Finite lists on purpose:
a place that is not listed gives no signal, and the question is then answered for both sides.

Sources (retrieved 2026-10-07):
- Turkish provinces: the 81 provinces in the table of tr.wikipedia.org "Türkiye'nin illeri"
  (revision 38164612), plus the spelling "Hakkari" and the short forms Afyon, Antep, Maraş,
  Urfa and İçel.
- EU cities: Wikidata (query.wikidata.org). For each member state, its capital (P36) and the
  most populous items that are instances of city (Q515 or a subclass) by population (P1082);
  the capital plus up to three of those are kept. English names are the Wikidata English
  labels, Turkish names the Turkish labels. Changes by hand, each listed in the PR notes:
  aggregate or duplicate items dropped (metropolitan and urban areas, "Madrid city", "Dublin
  City"), city districts dropped (Petržalka), Marseille added (Wikidata does not type it as a
  city; it is second in en.wikipedia.org "List of cities in the European Union by population
  within city limits", revision 1375565848), Nicosia and North Nicosia left out (a divided
  city, ambiguous like "Kıbrıs"), the Turkish label "Yaş" (Iași) left out because it is the
  Turkish word for age, and a few local spellings and common Turkish spellings added
  (München, Praha, Warszawa, Krakov, ...).
- Nationality adjectives: written by hand for the 27 member states, in Turkish and English.
"""

TR_PROVINCES = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya", "Ankara", "Antalya",
    "Ardahan", "Artvin", "Aydın", "Balıkesir", "Bartın", "Batman", "Bayburt", "Bilecik", "Bingöl",
    "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli", "Diyarbakır",
    "Düzce", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep", "Giresun",
    "Gümüşhane", "Hakkâri", "Hatay", "Iğdır", "Isparta", "İstanbul", "İzmir", "Kahramanmaraş",
    "Karabük", "Karaman", "Kars", "Kastamonu", "Kayseri", "Kırıkkale", "Kırklareli", "Kırşehir",
    "Kilis", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Mardin", "Mersin", "Muğla", "Muş",
    "Nevşehir", "Niğde", "Ordu", "Osmaniye", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas",
    "Şanlıurfa", "Şırnak", "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Uşak", "Van", "Yalova",
    "Yozgat", "Zonguldak",
]  # fmt: skip
TR_PROVINCE_VARIANTS = ["Hakkari", "Afyon", "Antep", "Maraş", "Urfa", "İçel"]

# Capital first, then the largest cities. Each entry: names in English, Turkish and the local
# language, as people may write them.
EU_CITIES: dict[str, list[list[str]]] = {
    "Austria": [["Vienna", "Viyana", "Wien"], ["Graz"], ["Linz"]],
    "Belgium": [
        ["Brussels", "Brüksel", "Bruxelles", "Brussel"],
        ["Antwerp", "Anvers", "Antwerpen"],
        ["Ghent", "Gent"],
        ["Charleroi"],
    ],
    "Bulgaria": [["Sofia", "Sofya"], ["Plovdiv", "Filibe"], ["Varna"]],
    "Croatia": [["Zagreb"], ["Split", "İspelet"], ["Rijeka", "Feyomi"]],
    "Cyprus": [["Limassol", "Limasol", "Lemesos"], ["Larnaca", "Larnaka"]],
    "Czechia": [["Prague", "Prag", "Praha"], ["Brno"], ["Ostrava"]],
    "Denmark": [["Copenhagen", "Kopenhag", "København"], ["Aarhus", "Århus"], ["Odense"]],
    "Estonia": [["Tallinn"], ["Tartu"], ["Narva"]],
    "Finland": [["Helsinki"], ["Espoo"], ["Tampere"]],
    "France": [["Paris"], ["Marseille", "Marsilya"], ["Lyon"]],
    "Germany": [["Berlin"], ["Hamburg"], ["Munich", "Münih", "München"]],
    "Greece": [["Athens", "Atina", "Athína"], ["Thessaloniki", "Selanik"], ["Patras"]],
    "Hungary": [["Budapest", "Budapeşte"], ["Debrecen"], ["Szeged", "Segedin"]],
    "Ireland": [["Dublin"], ["Cork"], ["Galway"]],
    "Italy": [["Rome", "Roma"], ["Milan", "Milano"], ["Naples", "Napoli"]],
    "Latvia": [["Riga", "Rīga"], ["Daugavpils"], ["Liepāja", "Liepaja"]],
    "Lithuania": [["Vilnius"], ["Kaunas"], ["Klaipėda", "Klaipeda"]],
    # The capital has the country's name, which is already a signal.
    "Luxembourg": [["Esch-sur-Alzette"], ["Dudelange"]],
    "Malta": [["Valletta"], ["Birkirkara"], ["Mosta"], ["Qormi"]],
    "Netherlands": [["Amsterdam"], ["Rotterdam"], ["The Hague", "Lahey", "Den Haag"]],
    "Poland": [
        ["Warsaw", "Varşova", "Warszawa"],
        ["Kraków", "Krakow", "Krakov"],
        ["Wrocław", "Wroclaw"],
    ],
    "Portugal": [["Lisbon", "Lizbon", "Lisboa"], ["Porto"], ["Braga"]],
    "Romania": [
        ["Bucharest", "Bükreş", "București", "Bucuresti"],
        ["Cluj-Napoca", "Cluj", "Kaloşvar"],
        ["Iași", "Iasi"],
    ],
    "Slovakia": [["Bratislava"], ["Košice", "Kosice", "Koşice"], ["Prešov", "Presov"]],
    "Slovenia": [["Ljubljana"], ["Maribor"], ["Kranj"]],
    "Spain": [["Madrid"], ["Barcelona", "Barselona"], ["Valencia", "Valensiya"]],
    "Sweden": [["Stockholm"], ["Gothenburg", "Göteborg"], ["Malmö", "Malmo"]],
}

# Names that are also everyday words or personal names. They count only when written like a
# place: with a Turkish suffix after an apostrophe ("Van'da", "Split'te"), after a preposition
# with a capital letter ("in Batman", "to Cork"), or before "ili"/"şehri" ("Ordu ili").
AMBIGUOUS_PLACES = {
    # Turkish provinces: van, Batman, "ordu" (army), "ağrı" (pain), "tokat" (slap),
    # "aydın" (bright, a given name), "muş", "bursa" (scholarship, dative)
    "Van", "Batman", "Ordu", "Ağrı", "Tokat", "Aydın", "Muş", "Bursa",
    # EU cities: split, cork, and Sofia/Sofya, which are also given names
    "Split", "Cork", "Sofia", "Sofya",
}  # fmt: skip

# Nationality adjectives. They count only before a word about rules, authorities, airspace or
# drones ("German drone rules", "Fransız kurallarına"), so that "in German", "Almanca",
# "French fries" or "fotoğraf çek" do not. Adjectives identical to the country name in Turkish
# ("Hollanda", "Belçika", ...) are covered by the country names.
EU_ADJECTIVES_EN = [
    "Austrian", "Belgian", "Bulgarian", "Croatian", "Czech", "Danish", "Estonian", "Finnish",
    "French", "German", "Greek", "Hungarian", "Irish", "Italian", "Latvian", "Lithuanian",
    "Luxembourgish", "Maltese", "Dutch", "Polish", "Portuguese", "Romanian", "Slovak",
    "Slovakian", "Slovenian", "Slovene", "Spanish", "Swedish",
]  # fmt: skip
EU_ADJECTIVES_TR = [
    "Alman", "Fransız", "Leh", "Çek", "Bulgar", "Hırvat", "Eston", "Fin", "Yunan", "Macar",
    "İtalyan", "Leton", "Litvan", "Rumen", "Romen", "Slovak", "Sloven", "İspanyol",
]  # fmt: skip
