import logging

import psycopg
import pytest

from app.db import ConnectionDetailsFilter
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


async def test_pool_warnings_name_the_error_but_not_the_host(client_for, caplog):
    caplog.set_level("WARNING", logger="psycopg.pool")
    settings = make_settings(
        database_url="postgresql://nobody:nothing@127.0.0.1:1/none", health_db_timeout=0.5
    )
    async with client_for(settings) as client:
        await client.get("/health")

    pool_lines = [r.getMessage() for r in caplog.records if r.name == "psycopg.pool"]
    assert any(line.startswith("error connecting in") for line in pool_lines)
    assert any("OperationalError" in line for line in pool_lines)
    assert "127.0.0.1" not in caplog.text and "port 1" not in caplog.text
    assert "nobody" not in caplog.text


async def test_connection_repr_is_kept_out_of_pool_warnings(test_database):
    async with await psycopg.AsyncConnection.connect(test_database) as conn:
        record = logging.LogRecord(
            "psycopg.pool", logging.WARNING, __file__, 1, "discarding connection: %s", (conn,), None
        )
        ConnectionDetailsFilter().filter(record)

    assert record.getMessage() == "discarding connection: AsyncConnection"
