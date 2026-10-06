import pydantic
import pytest

from ingest.sources import load_sources


def test_sources_yaml_is_valid():
    sources = {s.id: s for s in load_sources()}

    assert set(sources) == {"easa-ear-uas", "shgm-sht-iha"}
    easa, shgm = sources["easa-ear-uas"], sources["shgm-sht-iha"]
    assert (easa.jurisdiction, easa.language, easa.format) == ("EU", "en", "xml-zip")
    assert (shgm.jurisdiction, shgm.language, shgm.format) == ("TR", "tr", "pdf")
    # EASA text comes from the XML; the PDF edition supplies page numbers.
    assert [path.name for _, _, path in easa.downloads()] == [
        "easa-ear-uas.xml.zip",
        "easa-ear-uas.pdf",
    ]
    assert [path.name for _, _, path in shgm.downloads()] == ["shgm-sht-iha.pdf"]


def test_rejects_malformed_hash(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text(
        """
sources:
  - id: sample
    title: Sample
    jurisdiction: EU
    language: en
    version: "1"
    published: "2026-01"
    url: https://example.test/a.pdf
    format: pdf
    sha256: not-a-hash
    parser: shgm_pdf
    citation_url: https://example.test/a.pdf
""",
        encoding="utf-8",
    )

    with pytest.raises(pydantic.ValidationError):
        load_sources(path)
