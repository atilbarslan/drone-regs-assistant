"""Parse and chunk every source into data/chunks/<source_id>.jsonl, and print a report.

Usage: python -m ingest.build   (after python -m ingest.download)

Each line of the output is one chunk: source_id, section_ref, heading, page, language,
version, chunk_index, text.
"""

import json
import statistics
import sys
from pathlib import Path

from ingest.chunk import Chunk, ParseResult, chunk_sections, estimate_tokens
from ingest.download import sha256_of
from ingest.parse_easa import parse_easa
from ingest.parse_shgm import parse_shgm
from ingest.sources import RAW_DIR, ROOT, Source, load_sources

CHUNKS_DIR = ROOT / "data" / "chunks"


def parse_source(source: Source, raw_dir: Path = RAW_DIR) -> ParseResult:
    for url, expected, path in source.downloads(raw_dir):
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing; run python -m ingest.download first")
        if sha256_of(path) != expected:
            raise ValueError(f"{path} does not match the sha256 in sources.yaml ({url})")
    match source.parser:
        case "easa_xml":
            return parse_easa(source.file_path(raw_dir), source.pdf_path(raw_dir))
        case "shgm_pdf":
            return parse_shgm(source.file_path(raw_dir))


def write_jsonl(chunks: list[Chunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")


def report(source: Source, result: ParseResult, chunks: list[Chunk]) -> str:
    tokens = [estimate_tokens(c.text) for c in chunks]
    split = sum(1 for c in chunks if c.chunk_index == 1)
    refs = list(dict.fromkeys(c.section_ref for c in chunks))
    lines = [
        f"== {source.id} ({source.version})",
        f"sections: {len(result.sections)}, chunks: {len(chunks)}, sections split: {split}",
        f"estimated tokens per chunk: min {min(tokens)}, median {statistics.median(tokens):.0f}, "
        f"max {max(tokens)}",
        f"first refs: {', '.join(refs[:8])}",
    ]
    for label, items in [
        ("skipped", result.skipped),
        ("unrecognized", result.unrecognized),
        ("approximate page", result.approximate_page),
        ("without page", result.without_page),
    ]:
        lines.append(f"{label} ({len(items)}): {'; '.join(items) if items else '-'}")
    return "\n".join(lines)


def main() -> int:
    for source in load_sources():
        result = parse_source(source)
        chunks = chunk_sections(
            result.sections, source_id=source.id, language=source.language, version=source.version
        )
        write_jsonl(chunks, CHUNKS_DIR / f"{source.id}.jsonl")
        print(report(source, result, chunks), end="\n\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
