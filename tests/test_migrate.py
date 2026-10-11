"""Migrations: the pending files are applied all together or not at all."""

import psycopg
import pytest

from app.migrate import migrate

pytestmark = pytest.mark.anyio

GOOD = ("900_test_good.sql", "CREATE TABLE migrate_test_good (id integer)")
BROKEN = ("901_test_broken.sql", "CREATE TABLE migrate_test_broken (id no_such_type)")


async def test_a_failing_file_leaves_no_migration_applied_or_recorded(db, test_database):
    try:
        async with await psycopg.AsyncConnection.connect(test_database) as conn:
            with pytest.raises(psycopg.errors.UndefinedObject):
                await migrate(conn, [GOOD, BROKEN])

        tables = await db.execute("SELECT to_regclass('migrate_test_good')")
        assert (await tables.fetchone())[0] is None
        recorded = await db.execute(
            "SELECT name FROM schema_migrations WHERE name = ANY(%s)", ([GOOD[0], BROKEN[0]],)
        )
        assert await recorded.fetchall() == []
    finally:
        await db.execute("DROP TABLE IF EXISTS migrate_test_good")
        await db.execute(
            "DELETE FROM schema_migrations WHERE name = ANY(%s)", ([GOOD[0], BROKEN[0]],)
        )
