// Pure functions and texts for the page: no DOM access, so they can be tested with node --test.

export const MODES = ["EU", "TR", "compare"];

export const STRINGS = {
  en: {
    pageTitle: "Drone Rules Assistant",
    skip: "Skip to the question",
    brandSecond: "ASSISTANT",
    home: "Drone Rules Assistant, start page",
    navLabel: "Main",
    navSources: "Sources",
    navHow: "How it works",
    navGitHub: "GitHub",
    languageLabel: "Language",
    jurisdiction: "JURISDICTION",
    jurisdictionLabel: "Jurisdiction",
    modeNames: { EU: "EU", TR: "TÜRKİYE", compare: "COMPARE" },
    kicker: "REGULATION (EU) 2019/947 · 2019/945 AND SHT-İHA 30.07.2026",
    headline: "Drone rules, answered with the article that says so.",
    lede:
      "Ask in English or Turkish. Every statement links to the exact article and page of the " +
      "official EASA or SHGM text, and when your question leaves out something the rules " +
      "depend on, the answer says so.",
    askLabel: "Ask a question",
    switchHint:
      "Mention a country or city (“in Germany”, “İstanbul’da”) and the switch follows your " +
      "question. You can always change it.",
    questionLabel: "YOUR QUESTION",
    placeholders: {
      EU: "e.g. My drone weighs 200 g. What do I need before flying in France?",
      TR: "ör. 200 gramlık dronumla İzmir’de ticari çekim yapabilir miyim?",
      compare: "e.g. How do registration rules differ between Türkiye and the EU?",
    },
    submit: "Ask",
    submitting: "Asking…",
    waitSeconds: (s) => `Wait ${s} s`,
    tryOne: "Try one",
    noticeLegal: "Not legal advice: the official text prevails.",
    noticeData: "Questions are sent to the Google Gemini API free tier, so do not enter personal data.",
    factsLabel: "What is behind the answers",
    factSections: "sections indexed from the EASA Easy Access Rules for UAS (June 2026) and SHGM SHT-İHA (30.07.2026)",
    factCiteValue: "ART. + PAGE",
    factCite: "on every statement, linked to the official PDF; citations are checked on the server",
    factTests:
      "test questions (36 used for tuning, 5 held out); answer keys checked against the official texts by a UAS pilot",
    howTitle: "HOW IT WORKS",
    howSteps: [
      "The two official texts are split by article and indexed both by meaning and by exact terms, such as “UAS.OPEN.020” or “Madde 12”.",
      "Your question selects the EU, Türkiye or both, and the closest articles are retrieved.",
      "Google Gemini writes a structured answer from those passages only, citing them part by part.",
      "The server removes any part without a valid citation and links each source to its page in the official PDF.",
    ],
    footerSources: "Sources",
    footerNote: "Portfolio demo · answers may be wrong or incomplete",
    sourceLines: {
      EU: "EASA EASY ACCESS RULES FOR UAS · JUNE 2026",
      TR: "SHGM SHT-İHA · 30.07.2026",
      compare: "COMPARISON · SHT-İHA 30.07.2026 ↔ EASA EASY ACCESS RULES JUNE 2026",
    },
    loading: "Searching the sources and writing the answer…",
    factsGiven: "What you told us",
    removeFact: (label) => `Remove “${label}” and ask again`,
    dependsHeading: (n) =>
      n === 1 ? "THE ANSWER DEPENDS ON 1 THING YOU DIDN’T SAY" : `THE ANSWER DEPENDS ON ${n} THINGS YOU DIDN’T SAY`,
    dependsHint: "Tap what applies to get one direct answer.",
    answerLabel: "Answer",
    refusedTitle: "No answer in the sources",
    notInSources: "NOT IN THE SOURCES",
    keyDifferences: "Key differences",
    tableCaption: (question) => `Türkiye and the EU compared: ${question}`,
    topic: "TOPIC",
    sideTR: "TÜRKİYE · SHGM",
    sideEU: "EU · EASA",
    emptyCell: "Not in the sources",
    followUp: "Follow-up",
    sameQuestion: { TR: "Same question for Türkiye", EU: "Same question for the EU" },
    askAgain: {
      EU: "Ask this again for the EU",
      TR: "Ask this again for Türkiye",
      compare: "Ask this again as a comparison",
    },
    sourcesHeading: (n) => `SOURCES · ${n}`,
    sourcesSummary: (n) => (n === 1 ? "1 source · article and page" : `${n} sources · articles and pages`),
    showSources: (n) => `Show all sources (${n})`,
    hideSources: "Hide sources",
    citeLabel: (n, ref) => `Source ${n}: ${ref}`,
    openPdf: (p) => (p ? `Open official PDF, p. ${p}` : "Open official PDF"),
    page: "p.",
    followUpLabel: "Ask a follow-up",
    followUpPlaceholder: "Ask a follow-up…",
    errorTitle: "No answer",
    resetsLocal: (time) => `In your local time: ${time}`,
    invalid: "The question cannot be empty and can be at most 500 characters.",
    network: "Could not reach the server. Check your connection and try again.",
    unexpected: "Something went wrong. Please try again.",
    newQuestion: "New question",
  },
  tr: {
    pageTitle: "Drone Mevzuat Asistanı",
    skip: "Soruya geç",
    brandSecond: "ASİSTAN",
    home: "Drone Mevzuat Asistanı, ana sayfa",
    navLabel: "Ana menü",
    navSources: "Kaynaklar",
    navHow: "Nasıl çalışır",
    navGitHub: "GitHub",
    languageLabel: "Dil",
    jurisdiction: "YETKİ ALANI",
    jurisdictionLabel: "Yetki alanı",
    modeNames: { EU: "AB", TR: "TÜRKİYE", compare: "KARŞILAŞTIR" },
    kicker: "(AB) 2019/947 · 2019/945 TÜZÜKLERİ VE SHT-İHA 30.07.2026",
    headline: "Drone kurallarına, dayanağı olan maddeyle cevap.",
    lede:
      "Türkçe ya da İngilizce sorun. Her ifade, EASA ya da SHGM resmi metnindeki maddeye ve " +
      "sayfaya bağlanır; sorunuz kuralların bağlı olduğu bir bilgiyi belirtmiyorsa cevap bunu söyler.",
    askLabel: "Soru sorun",
    switchHint:
      "Bir ülke ya da şehir yazın (“in Germany”, “İstanbul’da”), anahtar sorunuza göre değişir. " +
      "İstediğiniz zaman değiştirebilirsiniz.",
    questionLabel: "SORUNUZ",
    placeholders: {
      EU: "ör. Dronum 200 gram. Fransa’da uçmadan önce ne yapmam gerekir?",
      TR: "ör. 200 gramlık dronumla İzmir’de ticari çekim yapabilir miyim?",
      compare: "ör. Kayıt kuralları Türkiye ile AB arasında nasıl farklı?",
    },
    submit: "Sor",
    submitting: "Soruluyor…",
    waitSeconds: (s) => `${s} sn bekleyin`,
    tryOne: "Birini deneyin",
    noticeLegal: "Hukuki danışmanlık değildir: resmi metin esastır.",
    noticeData: "Sorular Google Gemini API’nin ücretsiz katmanına gönderilir; kişisel veri girmeyin.",
    factsLabel: "Cevapların arkasında ne var",
    factSections: "bölüm: EASA Easy Access Rules for UAS (Haziran 2026) ve SHGM SHT-İHA (30.07.2026) metinlerinden dizinlendi",
    factCiteValue: "MADDE + SAYFA",
    factCite: "her ifadede, resmi PDF’e bağlantılı; atıflar sunucuda denetlenir",
    factTests:
      "test sorusu (36'sı ayar için, 5'i bekletilen); cevap anahtarları bir İHA pilotu tarafından resmi metinlerden kontrol edildi",
    howTitle: "NASIL ÇALIŞIR",
    howSteps: [
      "İki resmi metin maddelere bölünür; hem anlama hem de “UAS.OPEN.020”, “Madde 12” gibi tam ifadelere göre dizinlenir.",
      "Sorunuz AB’yi, Türkiye’yi ya da ikisini seçer; en yakın maddeler getirilir.",
      "Google Gemini yalnız bu parçalardan yapılandırılmış bir cevap yazar ve her bölümde dayandığı parçayı gösterir.",
      "Sunucu geçerli atfı olmayan her bölümü çıkarır ve her kaynağı resmi PDF’teki sayfasına bağlar.",
    ],
    footerSources: "Kaynaklar",
    footerNote: "Portföy demosu · cevaplar yanlış ya da eksik olabilir",
    sourceLines: {
      EU: "EASA EASY ACCESS RULES FOR UAS · HAZİRAN 2026",
      TR: "SHGM SHT-İHA · 30.07.2026",
      compare: "KARŞILAŞTIRMA · SHT-İHA 30.07.2026 ↔ EASA EASY ACCESS RULES HAZİRAN 2026",
    },
    loading: "Kaynaklar aranıyor ve cevap yazılıyor…",
    factsGiven: "Verdiğiniz bilgiler",
    removeFact: (label) => `“${label}” bilgisini kaldır ve yeniden sor`,
    dependsHeading: (n) =>
      n === 1 ? "CEVAP, BELİRTMEDİĞİNİZ 1 BİLGİYE BAĞLI" : `CEVAP, BELİRTMEDİĞİNİZ ${n} BİLGİYE BAĞLI`,
    dependsHint: "Size uyanı seçin; tek ve doğrudan bir cevap alın.",
    answerLabel: "Cevap",
    refusedTitle: "Kaynaklarda cevap yok",
    notInSources: "KAYNAKLARDA OLMAYANLAR",
    keyDifferences: "Temel farklar",
    tableCaption: (question) => `Türkiye ve AB karşılaştırması: ${question}`,
    topic: "KONU",
    sideTR: "TÜRKİYE · SHGM",
    sideEU: "AB · EASA",
    emptyCell: "Kaynaklarda yok",
    followUp: "Devam",
    sameQuestion: { TR: "Aynı soruyu Türkiye için sor", EU: "Aynı soruyu AB için sor" },
    askAgain: {
      EU: "Bu soruyu AB için yeniden sor",
      TR: "Bu soruyu Türkiye için yeniden sor",
      compare: "Bu soruyu karşılaştırma olarak yeniden sor",
    },
    sourcesHeading: (n) => `KAYNAKLAR · ${n}`,
    sourcesSummary: (n) => `${n} kaynak · madde ve sayfalar`,
    showSources: (n) => `Tüm kaynakları göster (${n})`,
    hideSources: "Kaynakları gizle",
    citeLabel: (n, ref) => `Kaynak ${n}: ${ref}`,
    openPdf: (p) => (p ? `Resmi PDF’i aç, s. ${p}` : "Resmi PDF’i aç"),
    page: "s.",
    followUpLabel: "Devam sorusu sorun",
    followUpPlaceholder: "Devam sorusu…",
    errorTitle: "Cevap alınamadı",
    resetsLocal: (time) => `Yerel saatinizle: ${time}`,
    invalid: "Soru boş olamaz ve en fazla 500 karakter olabilir.",
    network: "Sunucuya ulaşılamadı. Bağlantınızı kontrol edip tekrar deneyin.",
    unexpected: "Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.",
    newQuestion: "Yeni soru",
  },
};

// Example questions per interface language and switch position (EU / TR / compare).
export const EXAMPLES = {
  en: {
    EU: [
      "Do I need to register a 200 g drone with a camera?",
      "What is the maximum height in the open category?",
      "Can I fly over people in subcategory A1 in Germany?",
      "Is my Turkish P1 licence valid in the EU?",
    ],
    TR: [
      "P0 lisansıyla gece uçabilir miyim?",
      "İkinci el aldığım dronu nasıl kaydettiririm?",
      "Kırmızı bölgede uçmak için ne gerekir?",
      "Eski İHA1 sertifikam ne olacak?",
    ],
    compare: [
      "Minimum pilot age in Türkiye and the EU",
      "Türkiye’deki M0 sınıfı ile AB’deki C0 aynı mı?",
      "P1 licence vs A2 certificate",
      "Registration rules for a 200 g drone",
    ],
  },
  tr: {
    EU: [
      "AB’de 200 gramlık kameralı bir dronu kaydettirmem gerekir mi?",
      "Açık kategoride azami uçuş yüksekliği nedir?",
      "Almanya’da A1 alt kategorisinde insanların üzerinden uçabilir miyim?",
      "Türk P1 lisansım AB’de geçerli mi?",
    ],
    TR: [
      "P0 lisansıyla gece uçabilir miyim?",
      "İkinci el aldığım dronu nasıl kaydettiririm?",
      "Kırmızı bölgede uçmak için ne gerekir?",
      "Eski İHA1 sertifikam ne olacak?",
    ],
    compare: [
      "Türkiye ve AB’de asgari pilot yaşı",
      "Türkiye’deki M0 sınıfı ile AB’deki C0 aynı mı?",
      "P1 lisansı ile A2 sertifikası",
      "200 gramlık bir dron için kayıt kuralları",
    ],
  },
};

export const MAX_QUESTION_CHARS = 500;

/** "tr" if the stored choice or the browser's first language is Turkish, otherwise "en". */
export function pickLanguage(stored, browserLanguages) {
  if (stored === "tr" || stored === "en") return stored;
  const first = (browserLanguages && browserLanguages[0]) || "";
  return first.toLowerCase().startsWith("tr") ? "tr" : "en";
}

/** The switch position: the last answered mode, else the interface language's side. */
export function defaultMode(lastMode, lang) {
  if (MODES.includes(lastMode)) return lastMode;
  return lang === "tr" ? "TR" : "EU";
}

/** The mode a radiogroup key moves to (arrows wrap, Home/End), or null for other keys. */
export function nextMode(current, key) {
  const i = Math.max(0, MODES.indexOf(current));
  const n = MODES.length;
  switch (key) {
    case "ArrowRight":
    case "ArrowDown":
      return MODES[(i + 1) % n];
    case "ArrowLeft":
    case "ArrowUp":
      return MODES[(i - 1 + n) % n];
    case "Home":
      return MODES[0];
    case "End":
      return MODES[n - 1];
    default:
      return null;
  }
}

/**
 * The /api/ask body. A new question goes with mode null, so the server can detect the
 * jurisdiction, and the switch as default_mode. Asking again for a chosen side sends it as mode.
 */
export function requestBody({ question, lang, switchMode, explicit, facts }) {
  return {
    question,
    lang,
    mode: explicit ? switchMode : null,
    default_mode: switchMode,
    facts: facts.map((f) => f.fact),
  };
}

function quoted(terms) {
  return terms.map((t) => `“${t.text}”`).join(", ");
}

const BADGE_NAMES = {
  en: { EU: "EU rules", TR: "Türkiye rules", compare: "Türkiye vs the EU" },
  tr: { EU: "AB kuralları", TR: "Türkiye kuralları", compare: "Türkiye ve AB" },
};

/** The badge above an answer: the mode and where it came from. */
export function modeBadge(mode, modeSource, detected, lang) {
  const name = BADGE_NAMES[lang][mode];
  const terms = ((detected && detected.matched_terms) || []).slice(0, 3);
  if (modeSource === "detected" && terms.length) {
    return lang === "tr"
      ? `${name} · sorudaki ${quoted(terms)} ifadesinden`
      : `${name} · detected from ${quoted(terms)}`;
  }
  if (modeSource === "explicit") return lang === "tr" ? `${name} · seçiminiz` : `${name} · your choice`;
  return lang === "tr" ? `${name} · soruda ülke yok (varsayılan)` : `${name} · no country in the question (default)`;
}

/** The other side for "Same question for …"; none in compare mode. */
export function otherSide(mode) {
  if (mode === "EU") return "TR";
  if (mode === "TR") return "EU";
  return null;
}

/** "Article 14 (2019/947)" → { ref: "Article 14", regulation: "2019/947" }. */
function splitRef(sectionRef) {
  const match = /^(.*?)\s*\((\d{4}\/\d+)\)\s*$/.exec(sectionRef);
  return match ? { ref: match[1], regulation: match[2] } : { ref: sectionRef, regulation: null };
}

/** A source card's two labels: the reference and "2019/947 · p. 399" / "SHT-İHA · s. 5". */
export function sourceLabel(citation, lang) {
  const { ref, regulation } = splitRef(citation.section_ref);
  const source = regulation || (citation.jurisdiction === "TR" ? "SHT-İHA" : "EASA");
  const page = citation.page ? ` · ${STRINGS[lang].page} ${citation.page}` : "";
  return { ref, meta: source + page };
}

/** The short tag at the end of a comparison cell: "M.8", "Geçici M.1", "Art. 14", "UAS.OPEN.020". */
export function shortRef(sectionRef) {
  const { ref } = splitRef(sectionRef);
  return ref
    .replace(/^Geçici Madde\s+/, "Geçici M.")
    .replace(/^Madde\s+/, "M.")
    .replace(/^Article\s+/, "Art. ");
}

/** Facts for the next request: the ones already given plus the chosen one, once each. */
export function withFact(facts, option) {
  return facts.some((f) => f.fact === option.fact) ? [...facts] : [...facts, option];
}

export function withoutFact(facts, fact) {
  return facts.filter((f) => f.fact !== fact);
}

/** Local-time rendering of an ISO timestamp, or null if it is missing or invalid. */
export function formatLocalTime(iso, lang) {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString(lang === "tr" ? "tr-TR" : "en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
