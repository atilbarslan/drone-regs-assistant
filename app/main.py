"""FastAPI application factory.

Run with: uvicorn --factory app.main:create_app
A factory instead of a module-level app keeps settings, clients and the database pool out of
import time, and lets tests pass fake providers.

The app assumes a single worker: the request limits are counted in memory (app/limits.py).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import ask, health
from app.config import Settings
from app.db import create_pool
from app.limits import Limits, RateLimiter
from app.providers import LLM, Embedder


def create_app(
    settings: Settings | None = None,
    *,
    embedder: Embedder | None = None,
    llm: LLM | None = None,
    limiter: RateLimiter | None = None,
) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = create_pool(settings)
        # wait=False: start even when the database is unreachable, so /health can report it.
        await pool.open(wait=False)
        app.state.pool = pool
        created = []
        app.state.embedder, app.state.llm = embedder, llm
        if embedder is None and llm is None and settings.gemini_api_key is not None:
            from app.gemini import GeminiEmbedder, GeminiLLM

            key = settings.gemini_api_key.get_secret_value()
            app.state.embedder = GeminiEmbedder(
                key,
                settings.gemini_embedding_model,
                settings.gemini_embedding_dimensions,
                settings.gemini_timeout_seconds,
            )
            app.state.llm = GeminiLLM(
                key,
                settings.gemini_generation_model,
                settings.gemini_timeout_seconds,
                settings.gemini_thinking_level,
            )
            created = [app.state.embedder, app.state.llm]
        try:
            yield
        finally:
            for client in created:
                await client.aclose()
            await pool.close()

    app = FastAPI(title="drone-regs-assistant", lifespan=lifespan)
    app.state.settings = settings
    app.state.limiter = limiter or RateLimiter(
        Limits(
            global_per_minute=settings.ask_global_per_minute,
            global_per_day=settings.ask_global_per_day,
            ip_per_minute=settings.ask_ip_per_minute,
            ip_per_day=settings.ask_ip_per_day,
        )
    )
    app.include_router(health.router)
    app.include_router(ask.router)
    return app
