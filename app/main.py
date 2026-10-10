"""FastAPI application factory.

Run with: uvicorn --factory app.main:create_app
A factory instead of a module-level app keeps settings, clients and the database pool out of
import time, and lets tests pass fake providers.

The app assumes a single worker: the request limits are counted in memory (app/limits.py).
"""

import logging
import mimetypes
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app import ask, health
from app.config import Settings
from app.db import create_pool
from app.limits import Limits, RateLimiter
from app.providers import LLM, Embedder

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# The page loads only its own files: no inline scripts or styles, no third-party origins (the
# fonts are self-hosted too). Even if model output ever reached the page as HTML, an injected
# script would not run.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; "
    "img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)
# Not every system's mimetypes table knows .woff2; StaticFiles uses it for Content-Type.
mimetypes.add_type("font/woff2", ".woff2")
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
# Browsers then use HTTPS only for a year (set only where the site is served over HTTPS).
HSTS = "max-age=31536000"
# FastAPI's interactive docs load scripts from a CDN, so they get no CSP.
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


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

    docs = settings.api_docs
    app = FastAPI(
        title="drone-regs-assistant",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
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

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        if settings.log_forwarded_count:  # TEMPORARY: see Settings.log_forwarded_count
            values = [
                v
                for header in request.headers.getlist("x-forwarded-for")
                for v in header.split(",")
                if v.strip()
            ]
            logging.getLogger("uvicorn.error").info("x-forwarded-for values: %d", len(values))
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        if settings.hsts:
            response.headers["Strict-Transport-Security"] = HSTS
        if not request.url.path.startswith(DOCS_PATHS):
            response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        return response

    # Mounted last, so /health and /api/* are matched first.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app
