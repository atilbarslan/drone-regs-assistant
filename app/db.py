"""Postgres access through an async psycopg 3 connection pool."""

from psycopg_pool import AsyncConnectionPool

from app.config import Settings


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
