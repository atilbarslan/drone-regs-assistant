import hashlib

import pytest

from ingest.build import parse_source
from ingest.sources import Source


def make_source(sha256: str) -> Source:
    return Source(
        id="sample",
        title="Sample",
        jurisdiction="TR",
        language="tr",
        version="1",
        published="2026-01-01",
        url="https://example.test/sample.pdf",
        format="pdf",
        sha256=sha256,
        parser="shgm_pdf",
        citation_url="https://example.test/sample.pdf",
    )


def test_refuses_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_source(make_source("0" * 64), raw_dir=tmp_path)


def test_refuses_file_that_does_not_match_sources_yaml(tmp_path):
    (tmp_path / "sample.pdf").write_bytes(b"edited by hand")
    expected = hashlib.sha256(b"original").hexdigest()

    with pytest.raises(ValueError, match="does not match"):
        parse_source(make_source(expected), raw_dir=tmp_path)
