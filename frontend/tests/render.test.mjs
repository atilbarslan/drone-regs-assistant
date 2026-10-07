// Run with: node --test frontend/tests/*.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  EXAMPLES,
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
} from "../render.js";

test("both languages define the same texts", () => {
  const keys = (lang) => Object.keys(STRINGS[lang]).sort();
  assert.deepEqual(keys("tr"), keys("en"));
  for (const key of ["modeNames", "placeholders", "sourceLines", "askAgain"]) {
    for (const lang of ["en", "tr"]) assert.deepEqual(Object.keys(STRINGS[lang][key]).sort(), [...MODES].sort(), `${lang}.${key}`);
  }
  assert.equal(STRINGS.en.howSteps.length, STRINGS.tr.howSteps.length);
});

test("four example questions per language and switch position", () => {
  for (const lang of ["en", "tr"]) {
    for (const mode of MODES) assert.equal(EXAMPLES[lang][mode].length, 4, `${lang} ${mode}`);
  }
});

test("language: stored choice first, then the browser language, else English", () => {
  assert.equal(pickLanguage("en", ["tr-TR"]), "en");
  assert.equal(pickLanguage(null, ["tr-TR", "en"]), "tr");
  assert.equal(pickLanguage(null, ["TR"]), "tr");
  assert.equal(pickLanguage(null, ["de-DE", "tr"]), "en");
  assert.equal(pickLanguage("xx", []), "en");
});

test("switch position: the last answered mode, else the interface language's side", () => {
  assert.equal(defaultMode(null, "tr"), "TR");
  assert.equal(defaultMode(null, "en"), "EU");
  assert.equal(defaultMode("compare", "tr"), "compare");
  assert.equal(defaultMode("bogus", "en"), "EU");
});

test("arrow keys move round the switch; Home and End jump; other keys do nothing", () => {
  assert.equal(nextMode("EU", "ArrowRight"), "TR");
  assert.equal(nextMode("compare", "ArrowRight"), "EU");
  assert.equal(nextMode("EU", "ArrowLeft"), "compare");
  assert.equal(nextMode("TR", "ArrowUp"), "EU");
  assert.equal(nextMode("TR", "ArrowDown"), "compare");
  assert.equal(nextMode("TR", "Home"), "EU");
  assert.equal(nextMode("EU", "End"), "compare");
  assert.equal(nextMode("EU", "Enter"), null);
});

test("a new question lets the server detect the mode; asking again for a side sends it", () => {
  const facts = [{ fact: "The drone has a camera.", label: "Has a camera" }];
  assert.deepEqual(requestBody({ question: "q", lang: "en", switchMode: "TR", explicit: false, facts }), {
    question: "q",
    lang: "en",
    mode: null,
    default_mode: "TR",
    facts: ["The drone has a camera."],
  });
  assert.equal(requestBody({ question: "q", lang: "tr", switchMode: "EU", explicit: true, facts: [] }).mode, "EU");
});

test("the badge says where the mode came from", () => {
  const germany = { mode: "EU", matched_terms: [{ text: "Germany", jurisdiction: "EU" }] };
  assert.equal(modeBadge("EU", "detected", germany, "en"), "EU rules · detected from “Germany”");
  const almanya = { mode: "EU", matched_terms: [{ text: "Almanya", jurisdiction: "EU" }] };
  assert.equal(modeBadge("EU", "detected", almanya, "tr"), "AB kuralları · sorudaki “Almanya” ifadesinden");
  const none = { mode: null, matched_terms: [] };
  assert.equal(modeBadge("TR", "explicit", none, "en"), "Türkiye rules · your choice");
  assert.equal(modeBadge("TR", "default", none, "tr"), "Türkiye kuralları · soruda ülke yok (varsayılan)");
  assert.equal(modeBadge("compare", "default", none, "en"), "Türkiye vs the EU · no country in the question (default)");
});

test("“same question for …” goes to the other side, and is not offered in compare mode", () => {
  assert.equal(otherSide("EU"), "TR");
  assert.equal(otherSide("TR"), "EU");
  assert.equal(otherSide("compare"), null);
  assert.equal(STRINGS.en.sameQuestion.TR, "Same question for Türkiye");
  assert.equal(STRINGS.tr.sameQuestion.EU, "Aynı soruyu AB için sor");
});

test("source cards show the reference, the regulation or instruction, and the page", () => {
  const eu = { section_ref: "Article 14 (2019/947)", jurisdiction: "EU", page: 399 };
  assert.deepEqual(sourceLabel(eu, "en"), { ref: "Article 14", meta: "2019/947 · p. 399" });
  const amc = { section_ref: "AMC1 UAS.OPEN.020", jurisdiction: "EU", page: 423 };
  assert.deepEqual(sourceLabel(amc, "en"), { ref: "AMC1 UAS.OPEN.020", meta: "EASA · p. 423" });
  const tr = { section_ref: "Madde 11", jurisdiction: "TR", page: 5 };
  assert.deepEqual(sourceLabel(tr, "tr"), { ref: "Madde 11", meta: "SHT-İHA · s. 5" });
  assert.deepEqual(sourceLabel({ ...tr, page: null }, "en"), { ref: "Madde 11", meta: "SHT-İHA" });
});

test("comparison cells end with a short reference", () => {
  assert.equal(shortRef("Madde 8"), "M.8");
  assert.equal(shortRef("Geçici Madde 1"), "Geçici M.1");
  assert.equal(shortRef("Article 14 (2019/947)"), "Art. 14");
  assert.equal(shortRef("UAS.OPEN.020"), "UAS.OPEN.020");
  assert.equal(shortRef("GM1 Article 2(11)"), "GM1 Article 2(11)");
});

test("facts are added once and can be removed", () => {
  const camera = { fact: "The drone has a camera.", label: "Has a camera" };
  const c0 = { fact: "The drone carries a C0 class label.", label: "C0" };
  assert.deepEqual(withFact([], camera), [camera]);
  assert.deepEqual(withFact([camera], { ...camera }), [camera]);
  assert.deepEqual(withFact([camera], c0), [camera, c0]);
  assert.deepEqual(withoutFact([camera, c0], camera.fact), [c0]);
});

test("the depends-on heading counts what was not said", () => {
  assert.equal(STRINGS.en.dependsHeading(2), "THE ANSWER DEPENDS ON 2 THINGS YOU DIDN’T SAY");
  assert.equal(STRINGS.en.dependsHeading(1), "THE ANSWER DEPENDS ON 1 THING YOU DIDN’T SAY");
  assert.equal(STRINGS.en.sourcesSummary(5), "5 sources · articles and pages");
});

test("reset times are shown in local time, invalid ones ignored", () => {
  assert.equal(formatLocalTime(null, "tr"), null);
  assert.equal(formatLocalTime("not a date", "en"), null);
  assert.match(formatLocalTime("2026-10-08T07:00:00Z", "en"), /2026/);
});
