import psycopg
import pytest

from tests.conftest import TEST_DATABASE_URL, make_settings

pytestmark = pytest.mark.anyio


async def test_health_ok_when_database_is_reachable(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_503_when_database_is_unreachable(client_for):
    # Port 1 on localhost refuses connections immediately; nothing leaves the machine.
    settings = make_settings(
        database_url="postgresql://nobody:nothing@127.0.0.1:1/none", health_db_timeout=0.5
    )
    async with client_for(settings) as client:
        response = await client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unreachable"}


async def test_pgvector_extension_is_available(test_database):
    # Guards against running against a plain Postgres image without pgvector.
    async with await psycopg.AsyncConnection.connect(TEST_DATABASE_URL) as conn:
        cur = await conn.execute(
            "SELECT default_version FROM pg_available_extensions WHERE name = 'vector'"
        )
        row = await cur.fetchone()

    assert row is not None
