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

/** The label shown above an answer, built from jurisdiction and matched_terms. */
export function jurisdictionLabel(jurisdiction, matchedTerms, lang) {
  const terms = (matchedTerms || []).slice(0, 4);
  if (lang === "tr") {
    const from = terms.length
      ? ` — sorudaki ${quoted(terms)} ${terms.length === 1 ? "ifadesinden" : "ifadelerinden"}`
      : "";
    switch (jurisdiction) {
      case "EU":
        return `AB mevzuatına göre${from}`;
      case "TR":
        return `Türkiye mevzuatına göre${from}`;
      case "both":
        return `Türkiye ve AB${from}`;
      default:
        return "Soru ülke belirtmiyor — iki taraf";
    }
  }
  const from = terms.length ? ` — from ${quoted(terms)} in your question` : "";
  switch (jurisdiction) {
    case "EU":
      return `Based on EU rules${from}`;
    case "TR":
      return `Based on Turkish rules${from}`;
    case "both":
      return `Türkiye and the EU${from}`;
    default:
      return "No country named in the question — both sides";
  }
}

/** The answer without the server's jurisdiction line, which the label replaces. */
export function stripJurisdictionLine(answer, line) {
  if (line && answer.startsWith(line)) return answer.slice(line.length).trimStart();
  return answer;
}

/**
 * Split an answer into paragraphs of tokens: {type: "text", value} or {type: "cite", n}.
 * Only numbers that are in `citationNumbers` become citations; anything else stays text.
 */
export function splitAnswer(answer, citationNumbers) {
  const known = new Set(citationNumbers);
  return answer
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
    .map((paragraph) => {
      const tokens = [];
      let last = 0;
      for (const match of paragraph.matchAll(/\[(\d+)\]/g)) {
        const n = Number(match[1]);
        if (!known.has(n)) continue;
        if (match.index > last) tokens.push({ type: "text", value: paragraph.slice(last, match.index) });
        tokens.push({ type: "cite", n });
        last = match.index + match[0].length;
      }
      if (last < paragraph.length) tokens.push({ type: "text", value: paragraph.slice(last) });
      return tokens;
    });
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
