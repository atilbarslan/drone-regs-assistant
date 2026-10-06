"""FastAPI application factory.

Run with: uvicorn --factory app.main:create_app
A factory instead of a module-level app keeps settings and the database pool out of import time.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import health
from app.config import Settings
from app.db import create_pool


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = create_pool(settings)
        # wait=False: start even when the database is unreachable, so /health can report it.
        await pool.open(wait=False)
        app.state.pool = pool
        try:
            yield
        finally:
            await pool.close()

    app = FastAPI(title="drone-regs-assistant", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health.router)
    return app
