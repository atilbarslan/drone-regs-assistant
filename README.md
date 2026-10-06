# drone-regs-assistant

A small retrieval-augmented generation (RAG) demo that answers questions about drone rules in
the European Union (EASA Easy Access Rules for Unmanned Aircraft Systems) and Türkiye (SHGM
SHT-İHA), citing the article or paragraph each statement comes from. The interface works in
Turkish and English. It is a portfolio project, not a product, and its answers are not legal
advice: the official texts always prevail.

**Status: work in progress.** Downloading, parsing and chunking the two sources works
(`python -m ingest.download`, then `python -m ingest.build`); embedding, search, the answer
endpoint and the web interface are still being built.
