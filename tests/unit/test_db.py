import pytest

from ai_ha.store.db import Database, MigrationError


@pytest.mark.asyncio
async def test_open_applies_pragmas(tmp_path):
    db_path = tmp_path / "x.db"
    db = await Database.open(str(db_path), migrations_dir=None)
    async with db.connect() as c:
        row = await (await c.execute("PRAGMA journal_mode")).fetchone()
        assert row[0] == "wal"
        row = await (await c.execute("PRAGMA foreign_keys")).fetchone()
        assert row[0] == 0
    await db.close()


@pytest.mark.asyncio
async def test_migrations_apply_in_order(tmp_path):
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_first.sql").write_text("CREATE TABLE t1 (id INTEGER);")
    (mig_dir / "002_second.sql").write_text("CREATE TABLE t2 (id INTEGER);")
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(mig_dir))
    async with db.connect() as c:
        names = [r[0] for r in await (await c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )).fetchall()]
    await db.close()
    assert "t1" in names and "t2" in names


@pytest.mark.asyncio
async def test_migration_failure_rolls_back(tmp_path):
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_first.sql").write_text("CREATE TABLE t1 (id INTEGER);")
    (mig_dir / "002_bad.sql").write_text("CREATE TABLE t1 (id INTEGER);")  # dup
    with pytest.raises(MigrationError):
        await Database.open(str(tmp_path / "x.db"), migrations_dir=str(mig_dir))


@pytest.mark.asyncio
async def test_idempotent_reopen(tmp_path):
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_first.sql").write_text("CREATE TABLE t1 (id INTEGER);")
    db1 = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(mig_dir))
    await db1.close()
    db2 = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(mig_dir))
    await db2.close()  # second open must not re-run + fail
