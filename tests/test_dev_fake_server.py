"""scripts/dev_fake_server.py: no Gemini client, and fake answers the API accepts in each mode."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.gemini import GeminiEmbedder, GeminiLLM
from scripts.dev_fake_server import FAKE_MODEL, build_app
from tests.conftest import make_settings

pytestmark = pytest.mark.anyio


@pytest.fixture
def no_delay(monkeypatch):
    monkeypatch.setenv("FAKE_DELAY", "0")


async def ask_all(questions):
    # The sample chunks were embedded by the fake embedder under its own model name.
    app = build_app(
        make_settings(
            gemini_embedding_model="fake-embedding", gemini_api_key="x", ask_ip_per_minute=10
        )
    )
    async with app.router.lifespan_context(app):
        assert not isinstance(app.state.llm, GeminiLLM)
        assert not isinstance(app.state.embedder, GeminiEmbedder)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return [
                (await client.post("/api/ask", json={"lang": "en", "facts": [], **q})).json()
                for q in questions
            ]


async def test_fake_answers_fit_the_api_in_every_mode(db, loaded, no_delay):
    eu, tr, compare, refused = await ask_all(
        [
            {"question": "Can I fly over people in subcategory A1?", "mode": "EU"},
            {"question": "Kırmızı bölgede uçuş izni", "mode": "TR", "lang": "tr"},
            {"question": "Minimum pilot age", "mode": "compare"},
            {"question": "Sigorta zorunlu mu?", "mode": "TR", "lang": "tr"},
        ]
    )

    assert (eu["mode"], eu["refused"]) == ("EU", False)
    assert eu["sections"] and eu["depends_on"] and eu["citations"]
    assert all(c["jurisdiction"] == "EU" for c in eu["citations"])
    assert (tr["mode"], tr["refused"]) == ("TR", False)
    assert tr["sections"][0]["cases"]
    assert (compare["mode"], compare["refused"]) == ("compare", False)
    assert compare["compare"]["rows"] and len(compare["compare"]["key_differences"]) == 3
    assert refused["refused"] is True and refused["not_in_sources"]


async def test_fake_rows_in_request_log_can_be_told_apart(db, loaded, no_delay):
    await db.execute("TRUNCATE request_log")
    await ask_all([{"question": "Can I fly at night?", "mode": "EU"}])

    cur = await db.execute("SELECT generation_model FROM request_log")
    assert [row[0] for row in await cur.fetchall()] == [FAKE_MODEL]
