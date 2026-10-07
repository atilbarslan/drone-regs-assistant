// Run with: node --test frontend/tests/*.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  EXAMPLES,
  STRINGS,
  defaultMode,
  formatLocalTime,
  modeLabel,
  pickLanguage,
  withFact,
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

test("mode labels say where the mode came from", () => {
  const germany = { mode: "EU", matched_terms: [{ text: "Almanya", jurisdiction: "EU" }] };
  assert.equal(modeLabel("EU", "detected", germany, "tr"), "AB mevzuatına göre — sorudaki 'Almanya' ifadesinden");
  assert.equal(
    modeLabel("EU", "detected", { mode: "EU", matched_terms: [{ text: "Germany", jurisdiction: "EU" }] }, "en"),
    "Based on EU rules — from 'Germany' in your question",
  );
  const both = {
    mode: "compare",
    matched_terms: [
      { text: "AB", jurisdiction: "EU" },
      { text: "Türkiye", jurisdiction: "TR" },
    ],
  };
  assert.equal(
    modeLabel("compare", "detected", both, "tr"),
    "Türkiye ve AB karşılaştırması — sorudaki 'AB', 'Türkiye' ifadelerinden",
  );
  assert.equal(modeLabel("TR", "explicit", both, "tr"), "Türkiye mevzuatına göre — seçiminize göre");
  const none = { mode: null, matched_terms: [] };
  assert.equal(modeLabel("TR", "default", none, "tr"), "Türkiye mevzuatına göre — soru ülke belirtmiyor (varsayılan)");
  assert.equal(modeLabel("EU", "default", none, "en"), "Based on EU rules — the question names no country (default)");
});

test("default mode: the last answered mode, else the interface language's", () => {
  assert.equal(defaultMode(null, "tr"), "TR");
  assert.equal(defaultMode(null, "en"), "EU");
  assert.equal(defaultMode("compare", "tr"), "compare");
  assert.equal(defaultMode("bogus", "en"), "EU");
});

test("a chosen fact is added once", () => {
  assert.deepEqual(withFact([], "Has a camera"), ["Has a camera"]);
  assert.deepEqual(withFact(["Has a camera"], "Has a camera"), ["Has a camera"]);
  assert.deepEqual(withFact(["a"], "b"), ["a", "b"]);
});

test("reset times are shown in local time, invalid ones ignored", () => {
  assert.equal(formatLocalTime(null, "tr"), null);
  assert.equal(formatLocalTime("not a date", "en"), null);
  assert.match(formatLocalTime("2026-10-08T07:00:00Z", "en"), /2026/);
});
