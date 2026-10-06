"""GET /health: the app is running and can reach the database."""

import asyncio
import logging

import psycopg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db import ping

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    timeout = request.app.state.settings.health_db_timeout
    try:
        # One deadline for both waiting on the pool and running the query.
        async with asyncio.timeout(timeout):
            await ping(request.app.state.pool)
    except (psycopg.Error, TimeoutError) as exc:
        # Log only the error type: driver messages can include host names from the DSN.
        logger.warning("health check: database unreachable (%s)", type(exc).__name__)
        return JSONResponse({"status": "error", "database": "unreachable"}, status_code=503)
    return JSONResponse({"status": "ok", "database": "ok"})
