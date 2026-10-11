"""Postgres access through an async psycopg 3 connection pool."""

import logging

import psycopg
from psycopg_pool import AsyncConnectionPool

from app.config import Settings


class ConnectionDetailsFilter(logging.Filter):
    """Keep database host, port and user out of psycopg_pool's own warnings.

    The pool logs the driver's error ("error connecting in 'pool-1': connection failed:
    connection to server at <host>, port <port> failed: ...") and, in other warnings, a
    connection's repr, which names the host, user and database. This filter keeps each warning
    but replaces those arguments with their type, so the log still says that connecting failed
    and how: "error connecting in 'pool-1': OperationalError". app/health.py logs the same way.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(_without_details(arg) for arg in record.args)
        return True


def _without_details(value: object) -> object:
    if isinstance(value, BaseException | psycopg.Connection | psycopg.AsyncConnection):
        return type(value).__name__
    return value


# The pool's modules all log to this logger; a logger filter sees each of its records.
logging.getLogger("psycopg.pool").addFilter(ConnectionDetailsFilter())


def create_pool(settings: Settings) -> AsyncConnectionPool:
    # open=False: the pool is opened in the app lifespan, inside the running event loop.
    return AsyncConnectionPool(
        settings.database_url.get_secret_value(),
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        open=False,
        # Check each connection before handing it out. Neon closes idle connections when it
        # scales to zero, and a stale connection would otherwise fail the first query.
        check=AsyncConnectionPool.check_connection,
    )


async def ping(pool: AsyncConnectionPool) -> None:
    """Run SELECT 1 on a pooled connection. Raises psycopg.Error if the database is unreachable."""
    async with pool.connection() as conn:
        await conn.execute("SELECT 1")


def vector_literal(values: list[float]) -> str:
    """pgvector's text form ("[0.1,0.2,...]"), passed as a parameter and cast with ::vector."""
    return "[" + ",".join(repr(float(v)) for v in values) + "]"
