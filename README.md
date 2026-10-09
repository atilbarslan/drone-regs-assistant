# drone-regs-assistant

A small retrieval-augmented generation (RAG) demo that answers questions about drone rules in
the European Union (EASA Easy Access Rules for Unmanned Aircraft Systems) and Türkiye (SHGM
SHT-İHA), citing the article or paragraph each statement comes from. The interface works in
Turkish and English. It is a portfolio project, not a product, and its answers are not legal
advice: the official texts always prevail.

**Status: work in progress.** Downloading, parsing, chunking, embedding, hybrid search, the
answer endpoint (`POST /api/ask`) and the web page (served at `/`) work; the evaluation and the
deployment are still being built.

Fonts (Barlow Condensed, IBM Plex Sans, IBM Plex Mono; SIL Open Font License 1.1) are served
from this site, not from Google Fonts, so visitors' IP addresses are not sent to a third party
and the Content Security Policy allows fonts from this origin only. Licences: `frontend/fonts/`.

To try the interface without a Gemini API key, run `python -m scripts.dev_fake_server` (fake
answers, real search on the local database; see the file's docstring).

## Evaluation

36 questions in `eval/questions.yaml` (Turkish and English; EU, Türkiye, both, unclear and
out-of-scope questions). The answer keys were written from the official texts and checked against
the official PDFs. `python -m eval.run --config NAME` asks each question the way the page does
(real Gemini API, run by hand, never in CI); a second model call per question (the judge)
checks the key's facts and must quote the answer word for word. `python -m eval.report` writes
`eval/REPORT.md`, with every change and its measured effect.

| | Baseline | Current |
|---|---|---|
| Jurisdiction detected correctly | 36/36 | 36/36 |
| Expected articles retrieved | 45/56 | 45/56 |
| Required facts in the answer | 45/59 | 48/59 |
| Facts contradicted | 0 | 0 |
| Out-of-scope questions refused | 4/4 | 4/4 |
| Answerable questions refused | 2/32 | 1/32 |

"Current" is measured after prompt changes that were tuned on this same set of questions, so it
flatters the system; the held-out row below uses questions that were not seen while tuning. The
model is not deterministic: two runs of the same configuration differed by 4 required facts, so
small differences are noise.

| Held-out (5 questions, not seen while tuning) | — |
|---|---|
| Required facts in the answer | to come |

A limit of the free tier: the stronger model on the same account (gemini-3.8-flash, 20 requests
a day) could not be compared. On two days, 35 of its 36 requests to answer the questions the
smaller model got wrong returned "503 UNAVAILABLE". The one answer it gave (a licence-recognition
question) did not refuse where the smaller model usually did, but missed the same facts, because
the article it needed was not retrieved; it took 45 s. One answer is no evidence either way.

Retrieval has an option to add a few core articles of each jurisdiction to the passages
(registration, class, licence, zones and technical requirements in SHT-İHA; Articles 4, 9, 14 and
UAS.OPEN.020 in 2019/947), chosen from the structure of the regulations rather than from the
questions. It is off: on the evaluation set it raised retrieval (45 → 50 of 57) but not the
facts in the answers, and made prompts a third longer.
