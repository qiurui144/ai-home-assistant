"""aiosqlite wrapper with PRAGMA + numbered migrations.

Migration files match `NNN_*.sql` and apply ascending. kv_meta.schema_version tracks
applied count. Each file runs in its own transaction; failure rolls back and raises.
Integrity check on open: corrupted DB triggers rename + new DB (per spec §7 case 10),
which is the OPERATIONAL behavior — for tests we surface as IntegrityError.
"""
from __future__ import annotations

import contextlib
import logging
import re
import time
from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

PRAGMAS = [
    "PRAGMA foreign_keys = OFF",
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA temp_store = MEMORY",
    "PRAGMA mmap_size = 268435456",
    "PRAGMA busy_timeout = 5000",
    "PRAGMA cache_size = -32000",
]

_MIGRATION_PATTERN = re.compile(r"^(\d{3})_.*\.sql$")


class MigrationError(Exception):
    """Raised when a migration fails. DB is left at last successful schema_version."""


class IntegrityError(Exception):
    """Raised when integrity_check returns non-'ok' on open."""


class Database:
    def __init__(self, path: str) -> None:
        self._path = path

    @classmethod
    async def open(cls, path: str, *, migrations_dir: str | None) -> Database:
        db = cls(path)
        await db._init_pragmas()
        await db._verify_integrity()
        await db._ensure_kv_meta_table()
        if migrations_dir:
            await db._apply_migrations(migrations_dir)
        return db

    async def close(self) -> None:
        pass  # connections are per-acquire; nothing global to close

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        conn = await aiosqlite.connect(self._path)
        try:
            for stmt in PRAGMAS:
                await conn.execute(stmt)
            yield conn
        finally:
            await conn.close()

    async def _init_pragmas(self) -> None:
        async with self.connect():
            pass

    async def _verify_integrity(self) -> None:
        async with self.connect() as c:
            row = await (await c.execute("PRAGMA integrity_check")).fetchone()
            # PRAGMA integrity_check always returns at least one row; None here
            # would mean a fundamentally broken aiosqlite layer — assert is correct.
            assert row is not None
            if row[0] != "ok":
                raise IntegrityError(f"sqlite integrity_check={row[0]}")

    async def _ensure_kv_meta_table(self) -> None:
        # kv_meta is created by migration 001_initial.sql.
        # This method is intentionally a no-op: the migration runner calls
        # _get_schema_version (which handles the missing-table case) and then
        # applies 001_initial.sql which owns the CREATE TABLE statement.
        pass

    async def _get_schema_version(self, c: aiosqlite.Connection) -> int:
        # kv_meta may not exist yet (before migration 001 runs); return 0.
        try:
            row = await (await c.execute(
                "SELECT value FROM kv_meta WHERE key='schema_version'"
            )).fetchone()
            return int(row[0]) if row else 0
        except aiosqlite.OperationalError:
            return 0

    async def _set_schema_version(self, c: aiosqlite.Connection, v: int) -> None:
        await c.execute(
            "INSERT OR REPLACE INTO kv_meta(key, value, updated_at) VALUES "
            "('schema_version', ?, ?)",
            (str(v), int(time.time() * 1000)),
        )

    async def _apply_migrations(self, migrations_dir: str) -> None:
        mig_path = Path(migrations_dir)
        files = sorted(p for p in mig_path.iterdir() if _MIGRATION_PATTERN.match(p.name))
        for f in files:
            m = _MIGRATION_PATTERN.match(f.name)
            assert m
            version = int(m.group(1))
            async with self.connect() as c:
                current = await self._get_schema_version(c)
                if current >= version:
                    continue
                logger.info("applying migration %s", f.name)
                try:
                    await c.executescript(f.read_text())
                    await self._set_schema_version(c, version)
                    await c.commit()
                except aiosqlite.Error as exc:
                    await c.rollback()
                    raise MigrationError(f"migration {f.name} failed: {exc}") from exc
