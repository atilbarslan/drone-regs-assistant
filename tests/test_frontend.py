"""The static page: served by FastAPI, with security headers, and no HTML-writing APIs."""

import re

import pytest

from app.main import FRONTEND_DIR

pytestmark = pytest.mark.anyio


async def test_index_is_served_with_security_headers(client):
    response = await client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<script type="module" src="app.js">' in response.text
    csp = response.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp
    assert "font-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/app.js", "javascript"),
        ("/render.js", "javascript"),
        ("/styles.css", "text/css"),
        ("/fonts.css", "text/css"),
        ("/fonts/ibm-plex-sans-latin-400-normal.woff2", "font/woff2"),
    ],
)
async def test_assets_are_served(client, path, content_type):
    response = await client.get(path)

    assert response.status_code == 200
    assert content_type in response.headers["content-type"]


async def test_api_routes_are_not_shadowed_by_the_page(client):
    assert (await client.get("/health")).headers["content-type"] == "application/json"
    assert (await client.post("/api/ask", json={})).status_code == 422


async def test_docs_keep_working_without_csp(client):
    response = await client.get("/docs")

    assert response.status_code == 200
    assert "content-security-policy" not in response.headers


def test_frontend_never_writes_html():
    # Model output must reach the page as text only. These APIs would parse it as HTML.
    forbidden = re.compile(
        r"\.innerHTML|\.outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function\("
    )
    for path in FRONTEND_DIR.glob("*.js"):
        assert not forbidden.search(path.read_text(encoding="utf-8")), path.name


def test_page_basics():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    # English first (the audience is European); the script switches to Turkish if the visitor
    # chose it or the browser asks for it.
    assert '<html lang="en">' in html
    assert 'name="viewport"' in html
    # The two fixed notices are part of the page, not of the model's answer.
    assert "Not legal advice — the official text prevails." in html
    assert "do not enter personal data." in html
    assert "<script>" not in html and "style=" not in html  # nothing inline (CSP)


def test_fonts_are_self_hosted_with_their_licences():
    # Loading from Google Fonts would send every visitor's IP address to Google.
    fonts_css = (FRONTEND_DIR / "fonts.css").read_text(encoding="utf-8")
    for path in [
        FRONTEND_DIR / "index.html",
        FRONTEND_DIR / "styles.css",
        FRONTEND_DIR / "fonts.css",
    ]:
        text = path.read_text(encoding="utf-8")
        assert "fonts.googleapis" not in text and "fonts.gstatic" not in text, path.name
    css_text = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8") + fonts_css
    assert not re.search(r"url\(\s*[\"']?(https?:)?//", css_text)  # no third-party url()
    files = re.findall(r'url\("(fonts/[^"]+\.woff2)"\)', fonts_css)
    assert len(files) == 14  # 7 weights × latin and latin-ext (Turkish İ, ş, ğ)
    for file in files:
        assert (FRONTEND_DIR / file).is_file(), file
    for family in ("barlow-condensed", "ibm-plex-sans", "ibm-plex-mono"):
        licence = (FRONTEND_DIR / "fonts" / f"LICENSE-{family}.txt").read_text(encoding="utf-8")
        assert "SIL Open Font License" in licence, family
