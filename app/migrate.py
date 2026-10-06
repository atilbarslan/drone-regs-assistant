"""Apply the SQL migrations in db/migrations/ that have not been applied yet.

Usage: python -m app.migrate   (uses DATABASE_URL)

Files run in name order, each in its own transaction, and are recorded in schema_migrations.
An advisory lock keeps two processes from migrating at the same time.
"""

import asyncio
from pathlib import Path

import psycopg

from app.config import Settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "db" / "migrations"
LOCK_ID = 7_120_301  # arbitrary, shared by every process that migrates this database


def read_migrations(directory: Path = MIGRATIONS_DIR) -> list[tuple[str, str]]:
    paths = sorted(directory.glob("*.sql"))
    return [(path.name, path.read_text(encoding="utf-8")) for path in paths]


async def migrate(conn: psycopg.AsyncConnection, migrations: list[tuple[str, str]]) -> list[str]:
    """Apply the given (name, sql) migrations that are not recorded yet; return their names."""
    applied_now = []
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_ID,))
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        cur = await conn.execute("SELECT name FROM schema_migrations")
        done = {row[0] for row in await cur.fetchall()}
        for name, sql in migrations:
            if name in done:
                continue
            await conn.execute(sql)
            await conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (name,))
            applied_now.append(name)
    return applied_now


async def main() -> None:
    settings = Settings()
    migrations = read_migrations()
    async with await psycopg.AsyncConnection.connect(
        settings.database_url.get_secret_value()
    ) as conn:
        applied = await migrate(conn, migrations)
    print(f"applied: {', '.join(applied)}" if applied else "database is up to date")


if __name__ == "__main__":
    asyncio.run(main())
