"""The source list (sources.yaml) as typed objects, and where each source's files live locally."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "sources.yaml"
RAW_DIR = ROOT / "data" / "raw"

SHA256_PATTERN = r"^[0-9a-f]{64}$"

FILE_SUFFIXES = {"pdf": ".pdf", "xml-zip": ".xml.zip"}


class Source(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str
    jurisdiction: Literal["EU", "TR"]
    language: Literal["en", "tr"]
    version: str
    published: str
    url: str
    format: Literal["pdf", "xml-zip"]
    sha256: str = Field(pattern=SHA256_PATTERN)
    pdf_url: str | None = None
    pdf_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    parser: Literal["easa_xml", "shgm_pdf"]
    citation_url: str

    def file_path(self, raw_dir: Path = RAW_DIR) -> Path:
        return raw_dir / f"{self.id}{FILE_SUFFIXES[self.format]}"

    def pdf_path(self, raw_dir: Path = RAW_DIR) -> Path | None:
        return raw_dir / f"{self.id}.pdf" if self.pdf_url else None

    def downloads(self, raw_dir: Path = RAW_DIR) -> list[tuple[str, str, Path]]:
        """(url, expected sha256, local path) for every file this source needs."""
        files = [(self.url, self.sha256, self.file_path(raw_dir))]
        if self.pdf_url:
            if self.pdf_sha256 is None:
                raise ValueError(f"{self.id}: pdf_url is set but pdf_sha256 is missing")
            files.append((self.pdf_url, self.pdf_sha256, self.pdf_path(raw_dir)))
        return files


def load_sources(path: Path = SOURCES_FILE) -> list[Source]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = [Source(**item) for item in data["sources"]]
    ids = [s.id for s in sources]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate source ids in {path}")
    return sources
