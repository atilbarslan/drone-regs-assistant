import os
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app

# Tests never read .env, so they cannot reach the production database by accident. Locally this
# default matches docker-compose.yml; CI sets TEST_DATABASE_URL for its service container.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://drone:drone@localhost:5432/drone_regs"
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_settings(**overrides) -> Settings:
    values = {"database_url": TEST_DATABASE_URL, **overrides}
    return Settings(_env_file=None, **values)


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
async def client() -> AsyncIterator[AsyncClient]:
    async with _client(make_settings()) as c:
        yield c
