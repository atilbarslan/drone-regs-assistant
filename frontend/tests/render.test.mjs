// Run with: node --test frontend/tests/
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  EXAMPLES,
  STRINGS,
  formatLocalTime,
  jurisdictionLabel,
  pickLanguage,
  splitAnswer,
  stripJurisdictionLine,
} from "../render.js";

test("both languages define the same texts", () => {
  assert.deepEqual(Object.keys(STRINGS.tr).sort(), Object.keys(STRINGS.en).sort());
});

test("four or five example questions per language", () => {
  for (const lang of ["tr", "en"]) {
    assert.ok(EXAMPLES[lang].length >= 4 && EXAMPLES[lang].length <= 5, lang);
  }
});

test("language: stored choice first, then the browser language", () => {
  assert.equal(pickLanguage("en", ["tr-TR"]), "en");
  assert.equal(pickLanguage(null, ["tr-TR", "en"]), "tr");
  assert.equal(pickLanguage(null, ["TR"]), "tr");
  assert.equal(pickLanguage(null, ["de-DE", "tr"]), "en");
  assert.equal(pickLanguage("xx", []), "en");
});

test("jurisdiction labels come from matched_terms", () => {
  const germany = [{ text: "Almanya", jurisdiction: "EU" }];
  assert.equal(
    jurisdictionLabel("EU", germany, "tr"),
    "AB mevzuatına göre — sorudaki 'Almanya' ifadesinden",
  );
  assert.equal(
    jurisdictionLabel("EU", [{ text: "Germany", jurisdiction: "EU" }], "en"),
    "Based on EU rules — from 'Germany' in your question",
  );
  const both = [
    { text: "AB", jurisdiction: "EU" },
    { text: "Türkiye", jurisdiction: "TR" },
  ];
  assert.equal(jurisdictionLabel("both", both, "tr"), "Türkiye ve AB — sorudaki 'AB', 'Türkiye' ifadelerinden");
  assert.equal(
    jurisdictionLabel("TR", [{ text: "SHGM", jurisdiction: "TR" }], "en"),
    "Based on Turkish rules — from 'SHGM' in your question",
  );
  assert.equal(jurisdictionLabel("none", [], "tr"), "Soru ülke belirtmiyor — iki taraf");
  assert.equal(jurisdictionLabel("none", [], "en"), "No country named in the question — both sides");
});

test("the server's jurisdiction line is stripped only when it matches", () => {
  const line = "Bu cevap AB mevzuatına göredir (sorudaki 'AB' ifadesinden).";
  assert.equal(stripJurisdictionLine(`${line}\n\nCevap [1].`, line), "Cevap [1].");
  assert.equal(stripJurisdictionLine("Cevap [1].", line), "Cevap [1].");
  assert.equal(stripJurisdictionLine("Cevap.", null), "Cevap.");
});

test("answers split into paragraphs of text and known citations", () => {
  const parts = splitAnswer("Birinci [1] ve [2].\n\nİkinci [9] paragraf [1]", [1, 2]);
  assert.deepEqual(parts, [
    [
      { type: "text", value: "Birinci " },
      { type: "cite", n: 1 },
      { type: "text", value: " ve " },
      { type: "cite", n: 2 },
      { type: "text", value: "." },
    ],
    [
      { type: "text", value: "İkinci [9] paragraf " },
      { type: "cite", n: 1 },
    ],
  ]);
});

test("markup in an answer stays text", () => {
  const parts = splitAnswer('<img src=x onerror="alert(1)"> [1]', [1]);
  assert.deepEqual(parts[0][0], { type: "text", value: '<img src=x onerror="alert(1)"> ' });
});

test("reset times are shown in local time, invalid ones ignored", () => {
  assert.equal(formatLocalTime(null, "tr"), null);
  assert.equal(formatLocalTime("not a date", "en"), null);
  assert.match(formatLocalTime("2026-10-08T07:00:00Z", "en"), /2026/);
});
