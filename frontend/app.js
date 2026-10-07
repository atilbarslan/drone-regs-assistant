// Page behaviour. Everything that comes from the server, the model's answer included, is put
// into the page with textContent / createTextNode, never as HTML.

import {
  EXAMPLES,
  MAX_QUESTION_CHARS,
  STRINGS,
  formatLocalTime,
  jurisdictionLabel,
  pickLanguage,
  splitAnswer,
  stripJurisdictionLine,
} from "./render.js";

const $ = (id) => document.getElementById(id);
const form = $("ask-form");
const input = $("question");
const submit = $("submit");
const counter = $("counter");
const examples = $("examples");
const result = $("result");
const langButton = $("lang-toggle");

let lang = pickLanguage(readStoredLanguage(), navigator.languages || [navigator.language]);
let busy = false;
let waitTimer = null;

function readStoredLanguage() {
  try {
    return localStorage.getItem("lang");
  } catch {
    return null;
  }
}

function storeLanguage(value) {
  try {
    localStorage.setItem("lang", value);
  } catch {
    // Storage can be unavailable (private mode); the choice then lasts for this page only.
  }
}

function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (name === "text") node.textContent = value;
    else node.setAttribute(name, value);
  }
  for (const child of children) node.append(child);
  return node;
}

// --- language ------------------------------------------------------------------------------

function applyLanguage() {
  const t = STRINGS[lang];
  document.documentElement.lang = lang;
  document.title = t.title;
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = t[node.dataset.i18n];
  }
  input.placeholder = t.placeholder;
  langButton.textContent = t.switchLanguage;
  langButton.setAttribute("aria-label", t.switchLanguageLabel);
  langButton.lang = lang === "tr" ? "en" : "tr";
  if (!busy && !waitTimer) submit.textContent = t.submit;
  updateCounter();
  examples.replaceChildren(
    ...EXAMPLES[lang].map((question) => {
      const button = el("button", { type: "button", class: "example", text: question });
      button.addEventListener("click", () => {
        input.value = question;
        updateCounter();
        ask(question);
      });
      return el("li", {}, button);
    }),
  );
}

langButton.addEventListener("click", () => {
  lang = lang === "tr" ? "en" : "tr";
  storeLanguage(lang);
  applyLanguage();
});

// --- form ----------------------------------------------------------------------------------

function updateCounter() {
  counter.textContent = STRINGS[lang].counter(input.value.length, MAX_QUESTION_CHARS);
}

input.maxLength = MAX_QUESTION_CHARS;
input.addEventListener("input", updateCounter);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});
form.addEventListener("submit", (event) => {
  event.preventDefault();
  ask(input.value);
});

function setBusy(value) {
  busy = value;
  submit.disabled = value || Boolean(waitTimer);
  submit.textContent = value ? STRINGS[lang].submitting : STRINGS[lang].submit;
  result.setAttribute("aria-busy", String(value));
}

// After a per-minute limit, keep the button disabled and count down the seconds.
function waitBeforeRetry(seconds) {
  clearInterval(waitTimer);
  let left = seconds;
  submit.disabled = true;
  submit.textContent = STRINGS[lang].waitSeconds(left);
  waitTimer = setInterval(() => {
    left -= 1;
    if (left > 0) {
      submit.textContent = STRINGS[lang].waitSeconds(left);
      return;
    }
    clearInterval(waitTimer);
    waitTimer = null;
    submit.disabled = busy;
    submit.textContent = STRINGS[lang].submit;
  }, 1000);
}

async function ask(rawQuestion) {
  const question = rawQuestion.trim();
  const t = STRINGS[lang];
  if (busy || waitTimer) return;
  if (!question || question.length > MAX_QUESTION_CHARS) {
    showError(t.invalid);
    return;
  }
  setBusy(true);
  result.replaceChildren(el("p", { class: "loading", role: "status", text: t.loading }));
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, lang }),
    });
    const body = await response.json().catch(() => null);
    if (response.ok && body) {
      showAnswer(question, body);
    } else if ((response.status === 429 || response.status === 503) && body && body.message) {
      showError(body.message, body.resets_at);
      if (response.status === 429 && !body.resets_at && body.retry_after_seconds) {
        waitBeforeRetry(body.retry_after_seconds);
      }
    } else if (response.status === 422) {
      showError(t.invalid);
    } else {
      showError(t.unexpected);
    }
  } catch {
    showError(t.network);
  } finally {
    setBusy(false);
  }
}

// --- answer --------------------------------------------------------------------------------

function showAnswer(question, data) {
  const t = STRINGS[lang];
  const citations = new Map(data.citations.map((c) => [c.n, c]));
  const heading = el("h2", { id: "answer-heading", tabindex: "-1", text: t.answerTitle });

  const label = el("p", {
    class: `jurisdiction jurisdiction-${data.jurisdiction}`,
    text: jurisdictionLabel(data.jurisdiction, data.matched_terms, lang),
  });
  const asked = el("p", { class: "asked" }, el("span", { text: `${t.yourQuestion}: ` }), question);

  const body = el("div", { class: data.refused ? "answer refused" : "answer" });
  if (data.refused) body.append(el("p", { class: "refused-title", text: t.refusedTitle }));
  const text = stripJurisdictionLine(data.answer, data.jurisdiction_line);
  for (const tokens of splitAnswer(text, [...citations.keys()])) {
    const paragraph = el("p");
    for (const token of tokens) {
      if (token.type === "text") {
        paragraph.append(document.createTextNode(token.value));
      } else {
        const citation = citations.get(token.n);
        const link = el("a", {
          href: `#cite-${token.n}`,
          class: "cite",
          "aria-label": t.citeLabel(token.n, citation.section_ref),
          text: `[${token.n}]`,
        });
        link.addEventListener("click", (event) => {
          event.preventDefault();
          focusCitation(token.n);
        });
        paragraph.append(link);
      }
    }
    body.append(paragraph);
  }

  const parts = [heading, label, asked, body];
  if (data.citations.length) {
    parts.push(el("h3", { text: t.sourcesTitle }), citationList(data.citations));
  }
  result.replaceChildren(...parts);
  heading.focus();
}

function citationList(citations) {
  const t = STRINGS[lang];
  const list = el("ol", { class: "citations" });
  for (const c of citations) {
    const title = el(
      "p",
      { class: "citation-title" },
      el("span", { class: "citation-number", text: `[${c.n}]` }),
      " ",
      el("strong", { text: c.section_ref }),
    );
    const meta = el("p", {
      class: "citation-meta",
      text: c.page ? `${c.source_title} · ${t.page(c.page)}` : c.source_title,
    });
    const excerpt = el("blockquote", { text: c.excerpt });
    const link = el("a", {
      href: c.url,
      target: "_blank",
      rel: "noopener noreferrer",
      text: t.openSource(c.page),
    });
    list.append(el("li", { id: `cite-${c.n}`, tabindex: "-1" }, title, meta, excerpt, link));
  }
  return list;
}

function focusCitation(n) {
  const item = document.getElementById(`cite-${n}`);
  if (!item) return;
  for (const other of document.querySelectorAll(".citations li.highlight")) {
    other.classList.remove("highlight");
  }
  item.classList.add("highlight");
  item.focus();
  item.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

// --- errors --------------------------------------------------------------------------------

function showError(message, resetsAt) {
  const t = STRINGS[lang];
  const box = el(
    "div",
    { class: "error", role: "alert" },
    el("p", { class: "error-title", text: t.errorTitle }),
    el("p", { text: message }),
  );
  const local = formatLocalTime(resetsAt, lang);
  if (local) box.append(el("p", { class: "error-local", text: t.resetsLocal(local) }));
  result.replaceChildren(box);
}

applyLanguage();
