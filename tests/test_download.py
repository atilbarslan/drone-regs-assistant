import hashlib

import httpx
import pytest

from ingest.download import HashMismatch, fetch

CONTENT = b"sample file body " * 1000
SHA = hashlib.sha256(CONTENT).hexdigest()
URL = "https://example.test/file.pdf"


def client_returning(status: int, body: bytes, calls: list) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, content=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_downloads_and_keeps_file_with_expected_hash(tmp_path):
    calls = []
    dest = tmp_path / "raw" / "file.pdf"

    assert fetch(client_returning(200, CONTENT, calls), URL, SHA, dest) is True
    assert dest.read_bytes() == CONTENT
    assert len(calls) == 1


def test_skips_download_when_file_already_matches(tmp_path):
    dest = tmp_path / "file.pdf"
    dest.write_bytes(CONTENT)
    calls = []

    assert fetch(client_returning(200, b"other", calls), URL, SHA, dest) is False
    assert calls == []


def test_replaces_local_file_with_wrong_hash(tmp_path):
    dest = tmp_path / "file.pdf"
    dest.write_bytes(b"stale")

    assert fetch(client_returning(200, CONTENT, []), URL, SHA, dest) is True
    assert dest.read_bytes() == CONTENT


def test_hash_mismatch_leaves_no_file(tmp_path):
    dest = tmp_path / "file.pdf"

    with pytest.raises(HashMismatch) as exc:
        fetch(client_returning(200, b"changed upstream", []), URL, SHA, dest)

    assert exc.value.actual == hashlib.sha256(b"changed upstream").hexdigest()
    assert list(tmp_path.iterdir()) == []


def test_http_error_leaves_no_file(tmp_path):
    with pytest.raises(httpx.HTTPStatusError):
        fetch(client_returning(404, b"not found", []), URL, SHA, tmp_path / "file.pdf")

    assert list(tmp_path.iterdir()) == []
