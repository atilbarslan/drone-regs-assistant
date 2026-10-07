import asyncio
import os
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from app.config import Settings
from app.main import create_app
from app.migrate import migrate, read_migrations
from ingest.embed import embed_pending, sync_source
from tests.fakes import EU_CHUNKS, TR_CHUNKS, FakeEmbedder, NoWaitPacer, sample_source

# Tests never read .env, so they cannot reach the production database by accident. They use a
# separate database (created if missing) on the docker-compose server; CI sets
# TEST_DATABASE_URL for its service container.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://drone:drone@localhost:5432/drone_regs_test"
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_settings(**overrides) -> Settings:
    values = {"database_url": TEST_DATABASE_URL, **overrides}
    return Settings(_env_file=None, **values)


@pytest.fixture(scope="session")
def test_database() -> str:
    """Create the test database if needed and apply the migrations once per test run."""
    dbname = conninfo_to_dict(TEST_DATABASE_URL)["dbname"]
    admin_url = make_conninfo(TEST_DATABASE_URL, dbname="postgres")
    with psycopg.connect(admin_url, autocommit=True) as admin:
        exists = admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone()
        if not exists:
            admin.execute(f'CREATE DATABASE "{dbname}"')

    async def apply() -> None:
        async with await psycopg.AsyncConnection.connect(TEST_DATABASE_URL) as conn:
            await migrate(conn, read_migrations())

    asyncio.run(apply())
    return TEST_DATABASE_URL


@pytest.fixture
async def db(test_database: str) -> AsyncIterator[psycopg.AsyncConnection]:
    """An autocommit connection to an empty test database."""
    async with await psycopg.AsyncConnection.connect(test_database, autocommit=True) as conn:
        await conn.execute("TRUNCATE documents CASCADE")
        yield conn


@asynccontextmanager
async def _client(settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    # httpx's ASGITransport does not run the lifespan, so run it here to open and close the pool.
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
def client_for() -> Callable[[Settings], AbstractAsyncContextManager[AsyncClient]]:
    return _client


@pytest.fixture
async def client(test_database: str) -> AsyncIterator[AsyncClient]:
    async with _client(make_settings()) as c:
        yield c


@pytest.fixture
async def loaded(db):
    embedder = FakeEmbedder()
    await sync_source(db, sample_source("eu-sample", "en", "EU"), EU_CHUNKS)
    await sync_source(db, sample_source("tr-sample", "tr", "TR"), TR_CHUNKS)
    stats = await embed_pending(db, embedder, make_settings(), NoWaitPacer())
    assert stats.embedded == len(EU_CHUNKS) + len(TR_CHUNKS)
    return embedder
