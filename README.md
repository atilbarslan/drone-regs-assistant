# drone-regs-assistant

A small retrieval-augmented generation (RAG) demo that answers questions about drone rules in
the European Union (EASA Easy Access Rules for Unmanned Aircraft Systems) and Türkiye (SHGM
SHT-İHA), citing the article or paragraph each statement comes from. The interface works in
Turkish and English. It is a portfolio project, not a product, and its answers are not legal
advice: the official texts always prevail.

**Status: work in progress.** Downloading, parsing, chunking, embedding and hybrid search
work (`python -m ingest.download`, `python -m ingest.build`, `python -m app.migrate`,
`python -m ingest.embed`, then `python -m app.search "question"`); the answer endpoint and the
web interface are still being built.
