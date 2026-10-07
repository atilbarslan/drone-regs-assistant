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
