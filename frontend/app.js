// Page behaviour. Everything that comes from the server, the model's answer included, is put
// into the page with textContent / createTextNode, never as HTML.

import {
  EXAMPLES,
  MAX_QUESTION_CHARS,
  MODES,
  STRINGS,
  defaultMode,
  formatLocalTime,
  modeBadge,
  nextMode,
  otherSide,
  pickLanguage,
  requestBody,
  shortRef,
  sourceLabel,
  withFact,
  withoutFact,
} from "./render.js";

const $ = (id) => document.getElementById(id);
const homeView = $("home-view");
const answerView = $("answer-view");
const askForm = $("ask-form");
const input = $("question");
const submit = $("submit");
const followForm = $("followup-form");
const followInput = $("followup");
const followSubmit = $("followup-submit");
const answerBody = $("answer-body");
const answerTitle = $("answer-title");

const state = {
  lang: pickLanguage(readStoredLanguage(), navigator.languages || [navigator.language]),
  mode: null, // the switch position
  view: "home",
  question: "",
  facts: [], // [{ fact, label }] chosen from depends_on
  data: null, // the last answer
  error: null, // { message, resetsAt } of the last failed request
  busy: false,
  waitTimer: null,
};
state.mode = defaultMode(null, state.lang);

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

const t = () => STRINGS[state.lang];

function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (value === undefined || value === null || value === false) continue;
    if (name === "text") node.textContent = value;
    else node.setAttribute(name, value === true ? "" : value);
  }
  for (const child of children) if (child !== null && child !== undefined) node.append(child);
  return node;
}

const SVG_NS = "http://www.w3.org/2000/svg";

function icon(paths, size = 16, stroke = "#F2A93B") {
  const svg = document.createElementNS(SVG_NS, "svg");
  for (const [name, value] of Object.entries({
    width: size,
    height: size,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke,
    "stroke-width": "1.5",
    "aria-hidden": "true",
    focusable: "false",
  })) {
    svg.setAttribute(name, value);
  }
  for (const d of paths) {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
}

const WARNING = ["M8 1.5l6.5 12h-13z", "M8 6.5v3.5M8 11.8v.2"];
const CHEVRON = ["M4 6l4 4 4-4"];

// --- language and static texts --------------------------------------------------------------

function applyLanguage() {
  const s = t();
  document.documentElement.lang = state.lang;
  document.title = s.pageTitle;
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = s[node.dataset.i18n];
  }
  for (const node of document.querySelectorAll("[data-i18n-aria]")) {
    node.setAttribute("aria-label", s[node.dataset.i18nAria]);
  }
  for (const button of document.querySelectorAll(".lang button")) {
    button.setAttribute("aria-pressed", String(button.dataset.lang === state.lang));
  }
  $("how-steps").replaceChildren(...s.howSteps.map((text) => el("li", { text })));
  followInput.placeholder = s.followUpPlaceholder;
  updateButtons();
  renderSwitches();
  renderExamples();
  if (state.view === "answer") renderAnswerView();
}

for (const button of document.querySelectorAll(".lang button")) {
  button.addEventListener("click", () => {
    if (state.lang === button.dataset.lang) return;
    state.lang = button.dataset.lang;
    storeLanguage(state.lang);
    applyLanguage();
  });
}

// --- jurisdiction switch (radiogroup, arrow keys) -------------------------------------------

const SWITCH_SLOTS = ["switch-home", "switch-header", "switch-answer"];

function renderSwitches() {
  for (const id of SWITCH_SLOTS) {
    const slot = $(id);
    const focused = slot.contains(document.activeElement);
    const group = el("div", {
      class: "switch",
      role: "radiogroup",
      "aria-label": t().jurisdictionLabel,
      "aria-labelledby": id === "switch-home" ? "jurisdiction-label" : null,
    });
    for (const mode of MODES) {
      const on = mode === state.mode;
      const button = el(
        "button",
        {
          type: "button",
          role: "radio",
          class: `mode-${mode}`,
          "aria-checked": String(on),
          tabindex: on ? "0" : "-1",
          "data-mode": mode,
        },
        el("span", { class: "dot", "aria-hidden": "true" }),
        t().modeNames[mode],
      );
      button.addEventListener("click", () => setMode(mode, id));
      button.addEventListener("keydown", (event) => {
        const next = nextMode(state.mode, event.key);
        if (!next) return;
        event.preventDefault();
        setMode(next, id);
      });
      group.append(button);
    }
    slot.replaceChildren(group);
    if (focused) group.querySelector('[aria-checked="true"]').focus();
  }
}

function setMode(mode, fromSlot) {
  state.mode = mode;
  renderSwitches();
  if (fromSlot) $(fromSlot).querySelector('[aria-checked="true"]').focus();
  renderExamples();
  if (state.view === "answer") renderAskAgain();
}

// --- start page -----------------------------------------------------------------------------

function renderExamples() {
  input.placeholder = t().placeholders[state.mode];
  $("examples").replaceChildren(
    ...EXAMPLES[state.lang][state.mode].map((question) => {
      const button = el("button", { type: "button", class: "chip", text: question });
      button.addEventListener("click", () => {
        input.value = question;
        ask({ question, facts: [], explicit: false });
      });
      return el("li", {}, button);
    }),
  );
}

input.maxLength = MAX_QUESTION_CHARS;
followInput.maxLength = MAX_QUESTION_CHARS;

// Enter sends, Shift+Enter makes a new line.
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    askForm.requestSubmit();
  }
});
askForm.addEventListener("submit", (event) => {
  event.preventDefault();
  ask({ question: input.value, facts: [], explicit: false });
});
followForm.addEventListener("submit", (event) => {
  event.preventDefault();
  ask({ question: followInput.value, facts: [], explicit: false });
});

// --- views ----------------------------------------------------------------------------------

function showView(view, { push = true } = {}) {
  if (state.view === view) return;
  state.view = view;
  homeView.hidden = view !== "home";
  answerView.hidden = view !== "answer";
  document.body.classList.toggle("view-home", view === "home");
  document.body.classList.toggle("view-answer", view === "answer");
  if (push) history.pushState({ view }, "");
  window.scrollTo(0, 0);
}

// Back and forward move between the start page and the answer. A reload starts on the start
// page, so the entry it lands on must say so (it may hold an older "answer" state).
history.replaceState({ view: "home" }, "");
window.addEventListener("popstate", () => {
  const view = history.state && history.state.view === "answer" && state.question ? "answer" : "home";
  showView(view, { push: false });
});

$("brand").addEventListener("click", (event) => {
  event.preventDefault();
  showView("home");
  input.focus();
});

// The header links point at parts of the start page.
for (const link of document.querySelectorAll('.site-nav a[href^="#"]')) {
  link.addEventListener("click", (event) => {
    const target = document.querySelector(link.getAttribute("href"));
    if (!target) return;
    event.preventDefault();
    if (state.view !== "home" && target.closest("#home-view")) showView("home", { push: false });
    target.scrollIntoView();
    target.focus({ preventScroll: true });
  });
}

// --- asking ---------------------------------------------------------------------------------

function updateButtons() {
  const s = t();
  for (const button of [submit, followSubmit]) {
    button.disabled = state.busy || Boolean(state.waitTimer);
    if (!state.waitTimer) button.textContent = state.busy ? s.submitting : s.submit;
  }
}

function setBusy(value) {
  state.busy = value;
  answerBody.setAttribute("aria-busy", String(value));
  updateButtons();
}

// After a per-minute limit, keep the buttons disabled and count down the seconds.
function waitBeforeRetry(seconds) {
  clearInterval(state.waitTimer);
  let left = seconds;
  const show = () => {
    for (const button of [submit, followSubmit]) {
      button.disabled = true;
      button.textContent = t().waitSeconds(left);
    }
  };
  state.waitTimer = setInterval(() => {
    left -= 1;
    if (left > 0) return show();
    clearInterval(state.waitTimer);
    state.waitTimer = null;
    updateButtons();
  }, 1000);
  show();
}

function showHomeMessage(message) {
  $("home-message").replaceChildren(messageBox(message));
}

async function ask({ question, facts, explicit }) {
  const s = t();
  const text = question.trim();
  if (state.busy || state.waitTimer) return;
  if (!text || text.length > MAX_QUESTION_CHARS) {
    if (state.view === "home") showHomeMessage(s.invalid);
    else renderMessage(s.invalid);
    return;
  }
  $("home-message").replaceChildren();
  state.question = text;
  state.facts = facts;
  state.data = null;
  state.error = null;
  followInput.value = "";
  showView("answer");
  renderAnswerView();
  setBusy(true);
  answerTitle.focus();
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        requestBody({ question: text, lang: state.lang, switchMode: state.mode, explicit, facts }),
      ),
    });
    const body = await response.json().catch(() => null);
    if (response.ok && body) {
      state.data = body;
      state.mode = body.mode; // the switch follows the answer (detected or chosen)
      renderSwitches();
      renderExamples();
    } else if ((response.status === 429 || response.status === 503) && body && body.message) {
      state.error = { message: body.message, resetsAt: body.resets_at };
      if (response.status === 429 && !body.resets_at && body.retry_after_seconds) {
        waitBeforeRetry(body.retry_after_seconds);
      }
    } else if (response.status === 422) {
      state.error = { message: s.invalid };
    } else {
      state.error = { message: s.unexpected };
    }
  } catch {
    state.error = { message: s.network };
  } finally {
    setBusy(false);
    renderAnswerView();
    answerTitle.focus();
  }
}

/** Ask the shown question again: in another mode, or with other facts. A chosen mode is sent
 * as such; with only the facts changed, the mode stays what it was (detected, default or
 * chosen), so the badge keeps saying where it came from. */
function askAgain({ mode, facts }) {
  const chosenBefore = state.data && state.data.mode_source === "explicit";
  if (mode) state.mode = mode;
  ask({ question: state.question, facts, explicit: Boolean(mode) || chosenBefore });
}

// --- answer view ----------------------------------------------------------------------------

function renderAnswerView() {
  const s = t();
  const data = state.data;
  answerTitle.textContent = state.question;

  const badge = $("mode-badge");
  const sourceLine = $("source-line");
  if (data) {
    badge.hidden = false;
    badge.className = `badge mode-${data.mode}`;
    badge.replaceChildren(
      el("span", { class: "dot", "aria-hidden": "true" }),
      modeBadge(data.mode, data.mode_source, data.detected, state.lang),
    );
    sourceLine.textContent = s.sourceLines[data.mode];
  } else {
    badge.hidden = true;
    sourceLine.textContent = "";
  }

  renderFactChips();
  renderAskAgain();

  if (state.busy || (!data && !state.error)) {
    answerBody.replaceChildren(el("p", { class: "loading", role: "status", text: s.loading }));
  } else if (state.error) {
    renderMessage(state.error.message, state.error.resetsAt);
  } else {
    answerBody.replaceChildren(...answerParts(data));
  }
}

function renderFactChips() {
  const s = t();
  const box = $("fact-chips");
  if (!state.facts.length) {
    box.replaceChildren();
    return;
  }
  const chips = state.facts.map((f) => {
    const button = el(
      "button",
      { type: "button", class: "fact-chip", "aria-label": s.removeFact(f.label) },
      f.label,
      el("span", { "aria-hidden": "true", text: "×" }),
    );
    button.disabled = state.busy;
    button.addEventListener("click", () => askAgain({ facts: withoutFact(state.facts, f.fact) }));
    return button;
  });
  box.replaceChildren(el("span", { class: "fact-chips-label", text: `${s.factsGiven}:` }), ...chips);
}

/** When the switch no longer matches the shown answer, offer to ask again in its mode. */
function renderAskAgain() {
  const box = $("ask-again");
  const shown = state.data && state.data.mode;
  if (!shown || state.busy || state.mode === shown) {
    box.replaceChildren();
    return;
  }
  const button = el("button", { type: "button", class: "chip", text: t().askAgain[state.mode] });
  button.addEventListener("click", () => askAgain({ mode: state.mode, facts: state.facts }));
  box.replaceChildren(button);
}

function messageBox(message, resetsAt) {
  const s = t();
  const box = el(
    "div",
    { class: "message", role: "alert" },
    el("p", { class: "message-title", text: s.errorTitle }),
    el("p", { class: "message-text", text: message }),
  );
  const local = formatLocalTime(resetsAt, state.lang);
  if (local) box.append(el("p", { class: "message-local", text: s.resetsLocal(local) }));
  return box;
}

function renderMessage(message, resetsAt) {
  answerBody.replaceChildren(messageBox(message, resetsAt));
}

function answerParts(data) {
  const citations = new Map(data.citations.map((c) => [c.n, c]));
  const compare = data.mode === "compare";
  const main = el("div", { class: "answer-main" });

  if (data.refused) main.append(el("p", { class: "refused-title", text: t().refusedTitle }));
  if (data.depends_on.length) main.append(dependsBlock(data.depends_on));
  if (data.compare) main.append(...compareBlock(data.compare, citations));
  if (data.sections.length) main.append(sectionsBlock(data.sections, citations));
  if (data.not_in_sources.length) main.append(gapsBlock(data.not_in_sources));
  main.append(followUpsBlock(data));

  if (!data.citations.length) return [main];
  const sources = sourcesBlock(data.citations, compare);
  if (compare) {
    main.append(sources);
    return [main];
  }
  return [el("div", { class: "answer-layout" }, main, sources)];
}

function citeLinks(numbers, citations) {
  const nodes = [];
  for (const n of numbers) {
    const c = citations.get(n);
    if (!c) continue;
    nodes.push(" ", citeLink(n, c, `[${n}]`));
  }
  return nodes;
}

function citeLink(n, citation, text, extraClass = "") {
  const link = el("a", {
    href: `#source-${n}`,
    class: `cite side-${citation.jurisdiction} ${extraClass}`.trim(),
    "aria-label": t().citeLabel(n, citation.section_ref),
    text,
  });
  link.addEventListener("click", (event) => {
    event.preventDefault();
    focusSource(n);
  });
  return link;
}

function dependsBlock(items) {
  const s = t();
  const groups = items.map((item) => {
    const buttons = item.options.map((option) => {
      const button = el("button", { type: "button", class: "chip", text: option.label });
      button.addEventListener("click", () => askAgain({ facts: withFact(state.facts, option) }));
      return el("li", {}, button);
    });
    return el(
      "div",
      { class: "depends-group", role: "group", "aria-label": item.question },
      el("span", { class: "depends-question", text: item.question }),
      el("ul", { class: "chips" }, ...buttons),
    );
  });
  const heading = el("h2", { id: "depends-heading" }, icon(WARNING), s.dependsHeading(items.length));
  return el(
    "section",
    { class: "depends", "aria-labelledby": "depends-heading" },
    heading,
    el("p", { text: s.dependsHint }),
    el("div", { class: "depends-groups" }, ...groups),
  );
}

function sectionsBlock(sections, citations) {
  const card = el("article", { class: "answer-card", "aria-label": t().answerLabel });
  for (const section of sections) {
    const content = el("div", { class: "row-content" });
    if (section.text) content.append(el("p", {}, section.text, ...citeLinks(section.citations, citations)));
    if (section.cases.length) {
      const cases = section.cases.map((c) =>
        el(
          "div",
          { class: "case" },
          el("span", { class: "case-condition", text: c.condition }),
          el("span", { class: "case-verdict", text: c.verdict }),
          el("p", { class: "case-text" }, c.text, ...citeLinks(c.citations, citations)),
        ),
      );
      content.append(el("div", { class: "cases" }, ...cases));
    }
    card.append(el("div", { class: "answer-row" }, el("h3", { text: section.topic }), content));
  }
  return card;
}

function gapsBlock(items) {
  return el(
    "section",
    { class: "gaps", "aria-labelledby": "gaps-heading" },
    el("h2", { id: "gaps-heading", class: "mono-label", text: t().notInSources }),
    el("ul", {}, ...items.map((text) => el("li", { text }))),
  );
}

function compareBlock(compare, citations) {
  const s = t();
  const parts = [];
  if (compare.key_differences.length) {
    const items = compare.key_differences.map((text, i) =>
      el(
        "li",
        { class: "difference" },
        el("span", { class: "difference-number", "aria-hidden": "true", text: String(i + 1).padStart(2, "0") }),
        el("p", { text }),
      ),
    );
    parts.push(el("ol", { class: "differences", "aria-label": s.keyDifferences }, ...items));
  }
  const sideHead = (side, text) =>
    el(
      "th",
      { scope: "col" },
      el("span", { class: `side-head mode-${side}` }, el("span", { class: "dot", "aria-hidden": "true" }), text),
    );
  const head = el(
    "tr",
    {},
    el("th", { scope: "col", class: "mono-label", text: s.topic }),
    sideHead("TR", s.sideTR),
    sideHead("EU", s.sideEU),
  );
  const cell = (side) => {
    if (!side) return el("td", { class: "empty", text: s.emptyCell });
    const refs = [];
    for (const n of side.citations) {
      const c = citations.get(n);
      if (c) refs.push(" ", citeLink(n, c, shortRef(c.section_ref), "cell-ref"));
    }
    return el("td", {}, side.text, ...refs);
  };
  const rows = compare.rows.map((row) =>
    el("tr", {}, el("th", { scope: "row", text: row.topic }), cell(row.TR), cell(row.EU)),
  );
  const table = el(
    "table",
    { class: "compare-table" },
    el("caption", { text: s.tableCaption(state.question) }),
    el("thead", {}, head),
    el("tbody", {}, ...rows),
  );
  // A scrollable region must be reachable by keyboard.
  parts.push(el("div", { class: "table-wrap", tabindex: "0", role: "region", "aria-label": s.tableCaption(state.question) }, table));
  return parts;
}

function followUpsBlock(data) {
  const s = t();
  const buttons = [];
  const other = otherSide(data.mode);
  if (other) {
    const same = el("button", { type: "button", class: `chip same-question mode-${other}`, text: s.sameQuestion[other] });
    same.addEventListener("click", () => askAgain({ mode: other, facts: state.facts }));
    buttons.push(same);
  }
  for (const question of data.follow_ups) {
    const button = el("button", { type: "button", class: "chip", text: question });
    button.addEventListener("click", () => ask({ question, facts: [], explicit: false }));
    buttons.push(button);
  }
  if (!buttons.length) return el("div", { hidden: true });
  return el("div", { class: "follow-ups" }, el("span", { class: "follow-ups-label", text: s.followUp }), ...buttons);
}

function sourcesBlock(citations, compare) {
  const s = t();
  const list = el("ol", { class: "source-list", id: "source-list" });
  for (const c of citations) {
    const { ref, meta } = sourceLabel(c, state.lang);
    list.append(
      el(
        "li",
        { id: `source-${c.n}`, class: `source side-${c.jurisdiction}`, tabindex: "-1" },
        el(
          "div",
          { class: "source-head" },
          el("span", { class: "source-ref", text: `[${c.n}] ${ref}` }),
          el("span", { class: "source-meta", text: meta }),
        ),
        el("blockquote", { text: c.excerpt }),
        el("a", { href: c.url, target: "_blank", rel: "noopener noreferrer", text: s.openPdf(c.page) }),
      ),
    );
  }
  const box = el("aside", {
    class: compare ? "sources compare-sources collapsed" : "sources collapsed",
    "aria-labelledby": "sources-heading",
  });
  const toggleText = () => {
    if (!compare) return s.sourcesSummary(citations.length);
    return box.classList.contains("collapsed") ? s.showSources(citations.length) : s.hideSources;
  };
  const toggle = el(
    "button",
    {
      type: "button",
      class: compare ? "chip sources-toggle" : "sources-toggle",
      "aria-expanded": "false",
      "aria-controls": "source-list",
    },
    toggleText(),
  );
  if (!compare) toggle.append(icon(CHEVRON, 16, "#9AA3AF"));
  toggle.addEventListener("click", () => setSourcesOpen(box, toggle, box.classList.contains("collapsed")));
  box.toggleText = toggleText;
  box.append(el("h2", { id: "sources-heading", class: "mono-label", text: s.sourcesHeading(citations.length) }), toggle, list);
  return box;
}

function setSourcesOpen(box, toggle, open) {
  box.classList.toggle("collapsed", !open);
  toggle.setAttribute("aria-expanded", String(open));
  toggle.firstChild.textContent = box.toggleText();
}

function focusSource(n) {
  const item = $(`source-${n}`);
  if (!item) return;
  const box = item.closest(".sources");
  if (box && box.classList.contains("collapsed")) {
    setSourcesOpen(box, box.querySelector(".sources-toggle"), true);
  }
  for (const other of document.querySelectorAll(".source.highlight")) other.classList.remove("highlight");
  item.classList.add("highlight");
  item.focus({ preventScroll: true });
  item.scrollIntoView({ block: "nearest" });
}

applyLanguage();
