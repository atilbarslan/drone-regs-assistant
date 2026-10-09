"""Write eval/REPORT.md from result files: a summary row per run, then per-question tables.

    python -m eval.report eval/results/<a>.json [eval/results/<b>.json ...] [--detail N]

The summary compares the runs in the order given. The per-question table and the error classes
are for the run named by --detail (default: the last one). Changes and hypotheses are kept by
hand in eval/CHANGES.md and included as they are.
"""

import argparse
import json
import statistics
from pathlib import Path

from eval import score

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "eval" / "REPORT.md"
CHANGES = ROOT / "eval" / "CHANGES.md"


def load(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["path"] = str(Path(path).resolve().relative_to(ROOT))
    return data


def ok_results(run: dict) -> list[dict]:
    return [r for r in run["results"] if "error" not in r]


def classes(r: dict) -> list[str]:
    """Error classes of one answered question (empty: nothing wrong found)."""
    out = []
    if not r["detection"]["ok"]:
        out.append("tespit")
    refusal = r["refusal"]
    if refusal["should_refuse"]:
        if not (refusal["refused_flag"] or refusal["empty_and_explained"]):
            out.append("reddetme")
        return out
    if refusal["false_refusal"]:
        out.append("reddetme")
    ranks = r["retrieval"]["ranks"]
    musts = [f for f in r["facts"] if f["kind"] == "must"]
    must_missing = [f for f in musts if f["status"] != "present"]
    if any(f["status"] == "contradicted" for f in r["facts"]):
        out.append("üretim (çelişki)")
    if must_missing:
        if ranks and not all(ranks.values()):
            out.append("getirme")
        if ranks and any(ranks.values()):
            out.append("üretim")
    if ranks and any(ranks.values()) and r["citations"]["any_expected_cited"] is False:
        out.append("atıf")
    if r["depends_on"]["already_given"]:
        out.append("depends_on")
    return out


def summary(run: dict) -> dict:
    rs = ok_results(run)
    facts = [f for r in rs for f in r["facts"]]
    must = score.coverage(facts, "must")
    should = score.coverage(facts, "should")
    refuse = [r for r in rs if r["refusal"]["should_refuse"]]
    answer = [r for r in rs if not r["refusal"]["should_refuse"]]
    with_sources = [r for r in answer if r["retrieval"]["ranks"]]
    expected_refs = [rank for r in with_sources for rank in r["retrieval"]["ranks"].values()]
    by_mode: dict[str, list[int]] = {}
    for r in rs:
        if r["latency"]["generation_ms"]:
            by_mode.setdefault(r["latency"]["mode"], []).append(r["latency"]["generation_ms"])
    calls = run.get("calls_total") or run.get("calls", {})
    return {
        "questions": len(run["results"]),
        "errors": len(run["results"]) - len(rs),
        "detection_ok": sum(r["detection"]["ok"] for r in rs),
        "retrieved_any": sum(any(r["retrieval"]["ranks"].values()) for r in with_sources),
        "retrieved_all": sum(all(r["retrieval"]["ranks"].values()) for r in with_sources),
        "with_sources": len(with_sources),
        "expected_refs_found": sum(1 for x in expected_refs if x),
        "expected_refs": len(expected_refs),
        "cited_any": sum(bool(r["citations"]["any_expected_cited"]) for r in with_sources),
        "must": must,
        "should": should,
        "contradicted": sum(1 for f in facts if f["status"] == "contradicted"),
        "unverified": sum(1 for f in facts if f["status"] == "unverified"),
        "refuse_flag": sum(r["refusal"]["refused_flag"] for r in refuse),
        "refuse_explained": sum(bool(r["refusal"]["empty_and_explained"]) for r in refuse),
        "refuse_total": len(refuse),
        "false_refusals": sum(r["refusal"]["false_refusal"] for r in answer),
        "answer_total": len(answer),
        "depends_questions": sum(bool(r["depends_on"]["questions"]) for r in rs),
        "depends_items": sum(len(r["depends_on"]["questions"]) for r in rs),
        "depends_redundant": sum(len(r["depends_on"]["already_given"]) for r in rs),
        "latency": {m: (statistics.median(v), max(v), len(v)) for m, v in sorted(by_mode.items())},
        "tokens": (
            round(statistics.mean(r["latency"]["prompt_tokens"] or 0 for r in rs)) if rs else 0,
            round(statistics.mean(r["latency"]["output_tokens"] or 0 for r in rs)) if rs else 0,
        ),
        "calls": calls,
    }


def cov(c: score.Coverage) -> str:
    return f"{c.present}/{c.total} (yok {c.absent}, çelişki {c.contradicted}, doğrulanamadı {c.unverified})"


def summary_table(runs: list[dict]) -> list[str]:
    rows = [summary(r) for r in runs]
    names = [r["config"]["name"] for r in runs]
    line = lambda label, values: f"| {label} | " + " | ".join(values) + " |"  # noqa: E731
    out = [
        "| Ölçü | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
        line("Soru (hata)", [f"{s['questions']} ({s['errors']})" for s in rows]),
        line("Anahtarı değişip yeniden puanlanan", [", ".join(r["id"] for r in run["results"] if r.get("key_changed")) or "—" for run in runs]),
        line("Tespit doğru", [f"{s['detection_ok']}/{s['questions'] - s['errors']}" for s in rows]),
        line("Getirme: beklenen maddeden en az biri", [f"{s['retrieved_any']}/{s['with_sources']}" for s in rows]),
        line("Getirme: beklenen maddelerin hepsi", [f"{s['retrieved_all']}/{s['with_sources']}" for s in rows]),
        line("Getirme: beklenen madde (toplam)", [f"{s['expected_refs_found']}/{s['expected_refs']}" for s in rows]),
        line("Atıf: beklenen maddeden en az biri [n] ile", [f"{s['cited_any']}/{s['with_sources']}" for s in rows]),
        line("**must** kapsamı", [cov(s["must"]) for s in rows]),
        line("should kapsamı", [cov(s["should"]) for s in rows]),
        line("**Çelişki (contradicted)**", [str(s["contradicted"]) for s in rows]),
        line("Doğrulanamayan hakem kararı", [str(s["unverified"]) for s in rows]),
        line("Reddetme: refused=true", [f"{s['refuse_flag']}/{s['refuse_total']}" for s in rows]),
        line("Reddetme: boş + kaynakta yok dedi", [f"{s['refuse_explained']}/{s['refuse_total']}" for s in rows]),
        line("Yanlış ret", [f"{s['false_refusals']}/{s['answer_total']}" for s in rows]),
        line("depends_on: soru / madde / soruda zaten var", [f"{s['depends_questions']} / {s['depends_items']} / {s['depends_redundant']}" for s in rows]),
    ]  # fmt: skip
    for mode in ("EU", "TR", "compare"):
        values = []
        for s in rows:
            m = s["latency"].get(mode)
            values.append(f"{m[0] / 1000:.1f} / {m[1] / 1000:.1f} sn ({m[2]})" if m else "—")
        out.append(line(f"Üretim süresi {mode}: medyan / en çok (soru)", values))
    out.append(
        line(
            "Ortalama token: prompt / çıktı", [f"{s['tokens'][0]} / {s['tokens'][1]}" for s in rows]
        )
    )
    out.append(line("Gemini çağrısı: embedding (önbellek) / üretim / hakem / yeniden deneme", [
        f"{c.get('embedding', 0)} ({c.get('embedding_cached', 0)}) / {c.get('generation', 0)} / "
        f"{c.get('judge', 0)} / {c.get('retries', 0)}" for c in (s["calls"] for s in rows)
    ]))  # fmt: skip
    return out


def config_table(runs: list[dict]) -> list[str]:
    keys = ["generation_model", "thinking_level", "judge_model", "top_k", "list_top_k",
            "compare_per_side", "core_sections", "prompt_sha", "git", "note", "questions"]  # fmt: skip
    out = [
        "| | " + " | ".join(r["config"]["name"] for r in runs) + " |",
        "|---|" + "---|" * len(runs),
    ]
    for k in keys:
        out.append(f"| {k} | " + " | ".join(str(r["config"].get(k, "")) for r in runs) + " |")
    out.append("| sonuç dosyası | " + " | ".join(f"`{r['path']}`" for r in runs) + " |")
    out.append("| durum | " + " | ".join(r.get("status", "") for r in runs) + " |")
    return out


def rank_text(ranks: dict) -> str:
    return ", ".join(f"{ref}: {rank or 'yok'}" for ref, rank in ranks.items()) or "—"


def facts_text(facts: list[dict], kind: str) -> str:
    marks = {"present": "✓", "absent": "✗", "contradicted": "‼", "unverified": "?"}
    chosen = [f for f in facts if f["kind"] == kind]
    return " ".join(f"{f['id']}{marks.get(f['status'], '·')}" for f in chosen) or "—"


def detail_table(run: dict) -> list[str]:
    out = [
        "| id | tespit (mod) | liste / parça | beklenen maddelerin sırası | atıf | must | should | ret | depends_on | üretim sn | hata sınıfı |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]  # fmt: skip
    for r in run["results"]:
        if "error" in r:
            out.append(f"| {r['id']} | hata: {r['error']} |" + " |" * 9)
            continue
        d, ret, ref = r["detection"], r["retrieval"], r["refusal"]
        refusal = (
            ("✓" if ref["refused_flag"] or ref["empty_and_explained"] else "✗")
            if ref["should_refuse"]
            else ("yanlış ret" if ref["false_refusal"] else "")
        )
        cited = r["citations"]["any_expected_cited"]
        dep = r["depends_on"]
        gen = r["latency"]["generation_ms"]
        out.append(
            f"| {r['id']}{' †' if r.get('key_changed') else ''} | {'✓' if d['ok'] else '✗'} {d['detected_mode'] or 'null'}→{d['mode']} "
            f"| {'liste' if ret['list_question'] else ''} {ret['count']} | {rank_text(ret['ranks'])} "
            f"| {'' if cited is None else ('✓' if cited else '✗')} | {facts_text(r['facts'], 'must')} "
            f"| {facts_text(r['facts'], 'should')} | {refusal} "
            f"| {len(dep['questions'])}{' (' + str(len(dep['already_given'])) + ' zaten var)' if dep['already_given'] else ''} "
            f"| {gen / 1000:.1f} | {', '.join(classes(r)) or '—'} |"
        )  # fmt: skip
    return out


def class_counts(run: dict) -> list[str]:
    counts: dict[str, list[str]] = {}
    for r in ok_results(run):
        for c in classes(r):
            counts.setdefault(c, []).append(r["id"])
    out = ["| Hata sınıfı | Soru sayısı | Sorular |", "|---|---|---|"]
    for c, ids in sorted(counts.items(), key=lambda kv: -len(kv[1])):
        out.append(f"| {c} | {len(ids)} | {', '.join(ids)} |")
    return out


def judge_checks(run: dict, examples: int = 5) -> list[str]:
    """Every contradicted fact, every unverified one, and a few present/absent ones to check."""
    out = ["| id | fact | karar | alıntı (cevaptan) | not |", "|---|---|---|---|---|"]
    picked = []
    rs = ok_results(run)
    for r in rs:
        for f in r["facts"]:
            if f["status"] in ("contradicted", "unverified"):
                picked.append((r, f))
    sample = [(r, f) for r in rs for f in r["facts"] if f["status"] in ("present", "absent")]
    step = max(1, len(sample) // examples)
    picked += sample[::step][:examples]
    for r, f in picked:
        quote = (f["quote"] or "").replace("|", "\\|").replace("\n", " ")[:220]
        text = f["text"].replace("|", "\\|")
        out.append(f"| {r['id']} | {f['id']}: {text} | {f['status']} | {quote} | {f['note']} |")
    return out


def write(runs: list[dict], detail: dict) -> str:
    parts = [
        "# Değerlendirme raporu",
        "",
        "Bu dosya `python -m eval.report` ile üretilir; elle düzenlenmez (değişiklik ve hipotez "
        "tablosu `eval/CHANGES.md`'den aynen alınır). Yöntem: `eval/run.py` ve `eval/score.py` başları.",
        "",
        "Gemini çağrıları her koşunun satırında (son satır). Hakem: her soru için tek çağrı; "
        '"present"/"contradicted" kararları cevaptan birebir alıntı ister, alıntı bulunamazsa '
        '"doğrulanamadı" sayılır.',
        "",
        "## Özet",
        "",
        *summary_table(runs),
        "",
        "## Yapılandırma",
        "",
        *config_table(runs),
        "",
    ]
    if CHANGES.exists():
        parts += [CHANGES.read_text(encoding="utf-8").strip(), ""]
    parts += [
        f"## Hata sınıfları — {detail['config']['name']}",
        "",
        "Sınıflar otomatik çıkarılır: tespit (mod kabul listesinde değil), getirme (eksik must var "
        "ve beklenen maddelerden biri getirilmemiş), üretim (eksik must var ve beklenen maddelerden "
        "en az biri getirilmiş; çelişki ayrı), atıf (beklenen madde getirildi ama hiçbiri [n] ile "
        "gösterilmedi), reddetme, depends_on (soruda zaten olan bilgiyi soruyor). Bir soru birden "
        "çok sınıfta olabilir.",
        "",
        *class_counts(detail),
        "",
        f"## Soru bazında — {detail['config']['name']}",
        "",
        "† anahtar değişti; kayıtlı cevap yeni anahtarla yeniden puanlandı (`eval/rescore.py`). "
        "must/should: ✓ var · ✗ yok · ‼ çelişki · ? doğrulanamadı. Sıra: beklenen maddenin "
        "modele verilen parçalar arasındaki yeri (1 = ilk).",
        "",
        *detail_table(detail),
        "",
        f"## Hakem kararlarını elle kontrol — {detail['config']['name']}",
        "",
        "Bütün çelişki ve doğrulanamayan kararlar, ayrıca 5 örnek var/yok kararı.",
        "",
        *judge_checks(detail),
        "",
    ]
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("results", nargs="+")
    p.add_argument("--detail", help="config name for the per-question tables (default: last)")
    args = p.parse_args()
    runs = [load(path) for path in args.results]
    detail = next((r for r in runs if r["config"]["name"] == args.detail), runs[-1])
    REPORT.write_text(write(runs, detail), encoding="utf-8")
    print(f"wrote {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
