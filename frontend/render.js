// Pure functions and texts for the page: no DOM access, so they can be tested with node --test.

export const STRINGS = {
  tr: {
    title: "Drone Mevzuat Asistanı",
    subtitle:
      "AB (EASA) ve Türkiye (SHGM) drone kurallarıyla ilgili sorulara, resmi metinden madde göstererek cevap verir.",
    switchLanguage: "English",
    switchLanguageLabel: "Switch to English",
    questionLabel: "Sorunuz",
    placeholder: "Örnek: İstanbul'da drone uçurmak için izin gerekir mi?",
    submit: "Sor",
    submitting: "Yanıtlanıyor…",
    waitSeconds: (s) => `Bekleyin (${s} sn)`,
    hint: "Göndermek için Enter, yeni satır için Shift+Enter.",
    counter: (n, max) => `${n}/${max}`,
    examplesTitle: "Örnek sorular",
    noticeLegal: "Hukuki danışmanlık değildir; resmi metin esastır.",
    noticeData:
      "Sorular Google Gemini API'nin ücretsiz katmanına gönderilir; kişisel veri girmeyin.",
    yourQuestion: "Sorunuz",
    answerTitle: "Cevap",
    refusedTitle: "Kaynaklarda cevap bulunamadı",
    sourcesTitle: "Kaynaklar",
    page: (p) => `sayfa ${p}`,
    openSource: (p) => (p ? `Resmi metni aç (PDF, s. ${p})` : "Resmi metni aç (PDF)"),
    citeLabel: (n, ref) => `Kaynak ${n}: ${ref}`,
    loading: "Kaynaklar aranıyor ve cevap yazılıyor…",
    errorTitle: "Cevap alınamadı",
    resetsLocal: (time) => `Yerel saatinizle: ${time}`,
    invalid: "Soru boş olamaz ve en fazla 500 karakter olabilir.",
    network: "Sunucuya ulaşılamadı. Bağlantınızı kontrol edip tekrar deneyin.",
    unexpected: "Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.",
    footerSources: "Kaynak metinler",
    footerNote: "Portföy demosudur; cevaplar yanlış ya da eksik olabilir.",
    dependsTitle: "Cevap şunlara bağlı",
    dependsHint: "Size uyanı seçin; soru bu bilgiyle yeniden sorulur.",
    factsGiven: "Verdiğiniz bilgiler",
    notInSources: "Kaynaklarda olmayanlar",
    keyDifferences: "Temel farklar",
    topic: "Konu",
    sideTR: "Türkiye",
    sideEU: "AB",
    followUps: "Devam soruları",
    emptyCell: "Kaynaklarda yok",
  },
  en: {
    title: "Drone Rules Assistant",
    subtitle:
      "Answers questions about EU (EASA) and Turkish (SHGM) drone rules, citing the article in the official text.",
    switchLanguage: "Türkçe",
    switchLanguageLabel: "Türkçeye geç",
    questionLabel: "Your question",
    placeholder: "Example: Do I need permission to fly a drone in Berlin?",
    submit: "Ask",
    submitting: "Answering…",
    waitSeconds: (s) => `Wait (${s} s)`,
    hint: "Enter to send, Shift+Enter for a new line.",
    counter: (n, max) => `${n}/${max}`,
    examplesTitle: "Example questions",
    noticeLegal: "Not legal advice; the official text prevails.",
    noticeData:
      "Questions are sent to the free tier of the Google Gemini API; do not enter personal data.",
    yourQuestion: "Your question",
    answerTitle: "Answer",
    refusedTitle: "No answer found in the sources",
    sourcesTitle: "Sources",
    page: (p) => `page ${p}`,
    openSource: (p) => (p ? `Open the official text (PDF, p. ${p})` : "Open the official text (PDF)"),
    citeLabel: (n, ref) => `Source ${n}: ${ref}`,
    loading: "Searching the sources and writing the answer…",
    errorTitle: "No answer",
    resetsLocal: (time) => `In your local time: ${time}`,
    invalid: "The question cannot be empty and can be at most 500 characters.",
    network: "Could not reach the server. Check your connection and try again.",
    unexpected: "Something went wrong. Please try again.",
    footerSources: "Source texts",
    footerNote: "A portfolio demo; answers may be wrong or incomplete.",
    dependsTitle: "The answer depends on",
    dependsHint: "Pick what applies; the question is asked again with it.",
    factsGiven: "What you told us",
    notInSources: "Not in the sources",
    keyDifferences: "Key differences",
    topic: "Topic",
    sideTR: "Türkiye",
    sideEU: "EU",
    followUps: "Follow-up questions",
    emptyCell: "Not in the sources",
  },
};

// Four or five per language, covering EU, Türkiye, both and an unnamed jurisdiction.
export const EXAMPLES = {
  tr: [
    "Türkiye'de kırmızı bölgede uçmak için izin gerekir mi?",
    "AB'de 250 gramdan hafif bir drone için pilot eğitimi gerekir mi?",
    "SHGM'ye göre P1 lisansı için asgari yaş kaç?",
    "AB ile Türkiye'de pilotlar için asgari yaş nedir?",
    "Drone ile gece uçabilir miyim?",
  ],
  en: [
    "What is the maximum height for flights in the open category?",
    "Can I fly over people in the A1 subcategory in Germany?",
    "What licence levels exist under SHGM rules?",
    "How do EU and Turkish rules differ on the minimum age for pilots?",
    "Can I fly a drone at night?",
  ],
};

export const MAX_QUESTION_CHARS = 500;

/** "tr" if the stored choice or the browser's first language is Turkish, otherwise "en". */
export function pickLanguage(stored, browserLanguages) {
  if (stored === "tr" || stored === "en") return stored;
  const first = (browserLanguages && browserLanguages[0]) || "";
  return first.toLowerCase().startsWith("tr") ? "tr" : "en";
}

function quoted(terms) {
  return terms.map((t) => `'${t.text}'`).join(", ");
}

const MODE_NAMES = {
  tr: { EU: "AB mevzuatına göre", TR: "Türkiye mevzuatına göre", compare: "Türkiye ve AB karşılaştırması" },
  en: { EU: "Based on EU rules", TR: "Based on Turkish rules", compare: "Türkiye and the EU compared" },
};

/** The label above an answer, from the response's mode, mode_source and detected fields. */
export function modeLabel(mode, modeSource, detected, lang) {
  const name = MODE_NAMES[lang][mode];
  const terms = ((detected && detected.matched_terms) || []).slice(0, 4);
  if (modeSource === "detected" && terms.length) {
    if (lang === "tr") {
      const word = terms.length === 1 ? "ifadesinden" : "ifadelerinden";
      return `${name} — sorudaki ${quoted(terms)} ${word}`;
    }
    return `${name} — from ${quoted(terms)} in your question`;
  }
  if (modeSource === "explicit") return lang === "tr" ? `${name} — seçiminize göre` : `${name} — your choice`;
  return lang === "tr"
    ? `${name} — soru ülke belirtmiyor (varsayılan)`
    : `${name} — the question names no country (default)`;
}

/** The mode sent as default_mode: the last one answered, else the interface language's. */
export function defaultMode(lastMode, lang) {
  if (lastMode === "EU" || lastMode === "TR" || lastMode === "compare") return lastMode;
  return lang === "tr" ? "TR" : "EU";
}

/** Facts for the next request: the ones already given plus the chosen one, once each. */
export function withFact(facts, fact) {
  return facts.includes(fact) ? [...facts] : [...facts, fact];
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
