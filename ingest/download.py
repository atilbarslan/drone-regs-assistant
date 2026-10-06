"""Download the files listed in sources.yaml into data/raw/ and verify their SHA-256 hashes.

Usage: python -m ingest.download

A file already on disk with the expected hash is not downloaded again. A download whose hash
does not match is discarded and reported; the script then exits with status 1.
"""

import hashlib
import sys
from pathlib import Path

import httpx

from ingest.sources import RAW_DIR, load_sources

USER_AGENT = "drone-regs-assistant/0.1 (+https://github.com/atilbarslan/drone-regs-assistant)"
CHUNK_SIZE = 1 << 16


class HashMismatch(Exception):
    def __init__(self, url: str, expected: str, actual: str):
        super().__init__(f"{url}: expected sha256 {expected}, got {actual}")
        self.actual = actual


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(CHUNK_SIZE):
            digest.update(block)
    return digest.hexdigest()


def fetch(client: httpx.Client, url: str, expected_sha256: str, dest: Path) -> bool:
    """Make sure dest holds the file at url with the expected hash.

    Returns True if it was downloaded, False if a matching file was already there.
    Raises HashMismatch (and leaves dest untouched) if the downloaded file does not match.
    """
    if dest.exists() and sha256_of(dest) == expected_sha256:
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    digest = hashlib.sha256()
    try:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            with tmp.open("wb") as f:
                for block in response.iter_bytes(CHUNK_SIZE):
                    digest.update(block)
                    f.write(block)
        actual = digest.hexdigest()
        if actual != expected_sha256:
            raise HashMismatch(url, expected_sha256, actual)
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    return True


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=httpx.Timeout(30.0, read=120.0),
    )


def main(raw_dir: Path = RAW_DIR) -> int:
    failed = False
    with make_client() as client:
        for source in load_sources():
            for url, expected, dest in source.downloads(raw_dir):
                try:
                    downloaded = fetch(client, url, expected, dest)
                except HashMismatch as exc:
                    failed = True
                    print(f"mismatch   {source.id}: {exc}", file=sys.stderr)
                    print(
                        "           The file changed at the source. Review it and update "
                        "sources.yaml.",
                        file=sys.stderr,
                    )
                except httpx.HTTPError as exc:
                    failed = True
                    print(f"error      {source.id}: {url}: {exc!r}", file=sys.stderr)
                else:
                    status = "downloaded" if downloaded else "up to date"
                    print(f"{status:<11}{source.id}: {dest.name} sha256={expected[:12]}…")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
