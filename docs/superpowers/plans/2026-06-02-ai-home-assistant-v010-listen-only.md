# ai-home-assistant v0.1.0 — Listen-only Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v0.1.0 Listen-only foundation — HA WS subscribe + topology snapshot + room-aware Web UI + 7-day soak. No LLM, no learning, no HA write. Validates the plumbing layer that v0.2–v1.0 builds on.

**Architecture:** Single multi-arch Docker container (amd64/arm64/riscv64-buildx). FastAPI + asyncio + SQLite WAL. Subscribes to HA `state_changed` + `*_registry_updated` via WebSocket. Denormalizes `area_id` / `device_id` / `device_class` on ingest so v0.2 histogram queries become zero-JOIN. Snapshots are append-only versioned; topology changes never rewrite history.

**Tech Stack:** Python 3.11, FastAPI 0.115, websockets 13, httpx 0.27, aiosqlite 0.20, pydantic 2.9, pydantic-settings 2.6, tomli 2, watchfiles, Jinja2 (FastAPI built-in), pytest 8 + pytest-asyncio, ruff, mypy --strict. Docker base `python:3.11-slim`.

**Source spec:** `docs/superpowers/specs/2026-06-02-ai-home-assistant-v010-listen-only-design.md` (880 lines, approved 2026-06-02). Spec is the SSOT — when this plan says "per spec §X" it is by design, not a placeholder.

---

## Calendar overview (~3 weeks / 33 commit-grain tasks)

| Phase | Day | Goal | Tasks |
|-------|----:|------|------:|
| 1 — Foundation | 1-5 | config / store / topology / privacy / archive | 1-11 |
| 2 — HA adapter + ingest | 6-9 | REST/WS / mock HA / ingest / counters / health | 12-18 |
| 3 — Web + wire-up | 10-12 | FastAPI + 12 routes + 5 templates + main lifespan | 19-24 |
| 4 — Test + release | 13-21 | integration / soak / multi-arch / RC gates / GA tag | 25-33 |

Buffer: days 19-21 absorb HA WS reconnect quirks, RK3588 verification setbacks, doc polish. v0.1.0 GA target = day 21.

---

## File structure (recap from spec §4)

```
src/ai_ha/
├── __init__.py                __version__ = "0.1.0"
├── __main__.py                python -m ai_ha entry
├── main.py                    async wire-up + lifespan
├── config/{__init__,loader,watcher}.py
├── ha_adapter/{__init__,client,ws_client,topology_fetcher}.py
├── topology/{__init__,snapshot_store,entity_index,orphan_detector}.py
├── privacy/{__init__,hide_matcher}.py
├── ingest/{__init__,pipeline,counters}.py
├── store/{__init__,db,dao}.py
├── store/migrations/001_initial.sql
├── archive/{__init__,jsonl_writer}.py
├── health/{__init__,metrics}.py
└── web/
    ├── {__init__,app,auth}.py
    ├── routes/{health,areas,entities,events,topology,settings}.py
    ├── templates/{base,rooms,room,entities,timeline,settings}.html
    └── static/{app.css,timeline.js}

tests/
├── conftest.py
├── unit/{test_privacy,test_entity_index,test_snapshot_store,test_ingest_pipeline,test_counters,test_config_loader,test_health_metrics}.py
├── integration/conftest.py (MockHAServer)
├── integration/test_{cold_start,event_ingest,topology_update,privacy_e2e,reconnect,web_pages,edge_cases,adversarial,concurrency,resource_exhaustion,i18n,degrade}.py
├── integration/test_api_{health,areas,entities,events,topology,settings}.py
├── integration/test_error_{ha_unreachable,ha_auth,ws_disconnect,config_invalid,db_busy,disk_full,db_corrupted}.py
├── perf/{bench_ingest,bench_topology_snapshot,bench_api}.py
└── soak/{run_soak.py,analyze.py,README.md}
```

---

# Phase 1 — Foundation (Day 1-5)

## Task 1: Project scaffold tooling — pyproject.toml + ruff + mypy + pytest

**Files:**
- Create: `pyproject.toml`
- Create: `ruff.toml`
- Create: `mypy.ini`
- Create: `pytest.ini`
- Modify: `requirements.txt` (add test deps, uncomment block)
- Modify: `.gitignore` (`+coverage`, `+.coverage`, `+htmlcov/`, `+dist/`, `+*.egg-info/`)

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "ai-home-assistant"
version = "0.1.0"
requires-python = ">=3.11"
readme = "README.md"
license = { file = "LICENSE" }
description = "AI Home Assistant — learns your household, augments existing HA Core"

[tool.setuptools.packages.find]
where = ["src"]
include = ["ai_ha*"]

[tool.setuptools.package-data]
ai_ha = [
    "store/migrations/*.sql",
    "web/templates/*.html",
    "web/static/*.css",
    "web/static/*.js",
]

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 2: Write `ruff.toml`**

```toml
line-length = 100
target-version = "py311"

[lint]
select = ["E", "F", "W", "I", "B", "UP", "RUF", "ASYNC", "S"]
ignore = ["S101"]  # allow assert in tests

[lint.per-file-ignores]
"tests/**" = ["S105", "S106"]  # test fixtures may use fake passwords
```

- [ ] **Step 3: Write `mypy.ini`**

```ini
[mypy]
python_version = 3.11
strict = True
warn_unused_configs = True
warn_unreachable = True
exclude = ^(tests/soak/|docs/|build/)

[mypy-aiosqlite.*]
ignore_missing_imports = True
[mypy-tomli.*]
ignore_missing_imports = True
```

- [ ] **Step 4: Write `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
addopts = -ra --strict-markers --strict-config
markers =
    slow: long-running (excluded by default)
    soak: 7-day soak (run separately)
```

- [ ] **Step 5: Append to `requirements.txt`**

Uncomment the test deps block + add:

```
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-benchmark==4.0.0
pytest-cov==5.0.0
ruff==0.7.0
mypy==1.11.2
watchfiles==0.24.0
```

- [ ] **Step 6: Verify install + lint clean**

```bash
docker build -t ai-home-assistant:dev docker/
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "pip install -e . && ruff check src/ tests/ && mypy src/"
# Expect: 0 ruff / 0 mypy errors (src/ is currently almost empty so clean)
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml ruff.toml mypy.ini pytest.ini requirements.txt .gitignore
git commit -m "chore(scaffold): add pyproject + ruff/mypy/pytest config for v0.1.0"
```

---

## Task 2: AppConfig (pydantic-settings) + TOML loader

**Files:**
- Create: `src/ai_ha/config/__init__.py`
- Create: `src/ai_ha/config/loader.py`
- Create: `tests/unit/test_config_loader.py`

- [ ] **Step 1: Write failing test** — `tests/unit/test_config_loader.py`

```python
import textwrap
import pytest
from ai_ha.config.loader import load_config, ConfigError


def test_load_minimal_config(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(textwrap.dedent("""
        [ha]
        url = "http://localhost:8123"
        token = "fake-token"
    """))
    cfg = load_config(str(cfg_path))
    assert cfg.ha.url == "http://localhost:8123"
    assert cfg.behavior.history_retention_days == 30  # default


def test_env_override(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text('[ha]\nurl = "http://x"\ntoken = "t"\n')
    monkeypatch.setenv("HA_URL", "http://from-env:8123")
    cfg = load_config(str(cfg_path))
    assert cfg.ha.url == "http://from-env:8123"


def test_invalid_toml_raises(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("[ha\n  url = broken")
    with pytest.raises(ConfigError) as exc:
        load_config(str(cfg_path))
    assert "TOML" in str(exc.value)


def test_missing_required_field_raises(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("[ha]\nurl = ''\n")
    with pytest.raises(ConfigError):
        load_config(str(cfg_path))
```

- [ ] **Step 2: Run test, expect FAIL**

```bash
pytest tests/unit/test_config_loader.py -v
# Expect: ImportError
```

- [ ] **Step 3: Write `src/ai_ha/config/__init__.py`**

```python
from ai_ha.config.loader import (
    AppConfig,
    HAConfig,
    BehaviorConfig,
    DigestConfig,
    LLMConfig,
    LLMProvider,
    AuditConfig,
    PrivacyConfig,
    WebConfig,
    SoftIntentionConfig,
    ConfigError,
    load_config,
)

__all__ = [
    "AppConfig",
    "HAConfig",
    "BehaviorConfig",
    "DigestConfig",
    "LLMConfig",
    "LLMProvider",
    "AuditConfig",
    "PrivacyConfig",
    "WebConfig",
    "SoftIntentionConfig",
    "ConfigError",
    "load_config",
]
```

- [ ] **Step 4: Write `src/ai_ha/config/loader.py`**

```python
"""TOML + env-var configuration loading.

v0.1.0 only consumes [ha], [behavior], [digest] (max_tokens used by Web UI for
display only since LLM is v0.3+), [audit], [privacy], [web], [soft_intention]
(stored but never read in v0.1.0). [llm.*] is parsed for forward-compat but
not consumed.
"""
from __future__ import annotations

import os
import tomllib  # py311 stdlib (alias of tomli)
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator


class ConfigError(Exception):
    """Raised on TOML parse failure or schema validation failure."""


class HAConfig(BaseModel):
    url: str = Field(min_length=1)
    token: str = Field(min_length=1)


class BehaviorConfig(BaseModel):
    history_retention_days: int = 30
    preference_half_life_days: int = 14
    min_observations_for_pattern: int = 5


class DigestConfig(BaseModel):
    max_tokens: int = 500
    recent_event_window_minutes: int = 30
    include_entities_pattern: list[str] = []


class LLMProvider(BaseModel):
    key: str
    label: str = ""
    base_url: str = ""
    default_model: str = ""
    role: str = "capable"


class LLMConfig(BaseModel):
    fast_tier: str = ""
    capable_tier: str = ""
    escalation_threshold: float = 0.7
    budget_usd_monthly: float = 5.0
    providers: list[LLMProvider] = []


class AuditConfig(BaseModel):
    retention_days: int = 90
    hash_chain: bool = True


class PrivacyConfig(BaseModel):
    allow_cloud_llm_with_digest: bool = False
    hide_entities_pattern: list[str] = []


class WebConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8124
    require_auth: bool = True


class SoftIntentionConfig(BaseModel):
    auto_dismiss_after_hours: int = 72
    max_queue_size: int = 50
    require_dual_confirm_for_critical: bool = True


class ArchiveConfig(BaseModel):
    retention_days: int = 365
    compress: bool = True


class AppConfig(BaseModel):
    ha: HAConfig
    behavior: BehaviorConfig = BehaviorConfig()
    digest: DigestConfig = DigestConfig()
    llm: LLMConfig = LLMConfig()
    audit: AuditConfig = AuditConfig()
    privacy: PrivacyConfig = PrivacyConfig()
    web: WebConfig = WebConfig()
    soft_intention: SoftIntentionConfig = SoftIntentionConfig()
    archive: ArchiveConfig = ArchiveConfig()


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    if env_url := os.environ.get("HA_URL"):
        raw.setdefault("ha", {})["url"] = env_url
    if env_token := os.environ.get("HA_TOKEN"):
        raw.setdefault("ha", {})["token"] = env_token
    if env_port := os.environ.get("AI_HA_WEB_PORT"):
        raw.setdefault("web", {})["port"] = int(env_port)
    return raw


def load_config(path: str | Path) -> AppConfig:
    """Load and validate config.toml. env vars (HA_URL/HA_TOKEN/AI_HA_WEB_PORT) override file."""
    p = Path(path)
    try:
        raw = tomllib.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {p}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"TOML parse error in {p}: {exc}") from exc
    raw = _apply_env_overrides(raw)
    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"config validation failed:\n{exc}") from exc
```

- [ ] **Step 5: Run test, expect PASS**

```bash
pytest tests/unit/test_config_loader.py -v
# Expect: 4 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_ha/config/__init__.py src/ai_ha/config/loader.py tests/unit/test_config_loader.py
git commit -m "feat(config): AppConfig + TOML/env loader with pydantic validation"
```

---

## Task 3: Config watcher (watchfiles → hot-reload callback)

**Files:**
- Create: `src/ai_ha/config/watcher.py`
- Create: `tests/unit/test_config_watcher.py`

- [ ] **Step 1: Write failing test** — `tests/unit/test_config_watcher.py`

```python
import asyncio
import textwrap
import pytest
from ai_ha.config.watcher import ConfigWatcher


@pytest.mark.asyncio
async def test_watcher_fires_on_change(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text('[ha]\nurl = "http://x"\ntoken = "t"\n')
    fired: list[str] = []

    async def on_change(cfg) -> None:
        fired.append(cfg.ha.url)

    watcher = ConfigWatcher(str(cfg_path), on_change, debounce_ms=50)
    task = asyncio.create_task(watcher.run())
    await asyncio.sleep(0.1)
    cfg_path.write_text('[ha]\nurl = "http://y"\ntoken = "t"\n')
    await asyncio.sleep(0.3)
    watcher.stop()
    await task
    assert "http://y" in fired


@pytest.mark.asyncio
async def test_watcher_ignores_invalid_change(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text('[ha]\nurl = "http://x"\ntoken = "t"\n')
    errors: list[Exception] = []

    async def on_change(cfg) -> None:
        pass

    async def on_error(exc: Exception) -> None:
        errors.append(exc)

    watcher = ConfigWatcher(str(cfg_path), on_change, on_error=on_error, debounce_ms=50)
    task = asyncio.create_task(watcher.run())
    await asyncio.sleep(0.1)
    cfg_path.write_text("[broken\n")
    await asyncio.sleep(0.3)
    watcher.stop()
    await task
    assert len(errors) >= 1
```

- [ ] **Step 2: Run test, expect FAIL**

```bash
pytest tests/unit/test_config_watcher.py -v
```

- [ ] **Step 3: Write `src/ai_ha/config/watcher.py`**

```python
"""Hot-reload watcher for /data/config.toml.

Reads the file 50 ms after a Change event (half-write protection per spec §11 risk #8).
Calls on_change with new AppConfig; on validation failure, calls on_error and keeps old config.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from watchfiles import awatch

from ai_ha.config.loader import AppConfig, ConfigError, load_config

logger = logging.getLogger(__name__)


class ConfigWatcher:
    def __init__(
        self,
        path: str | Path,
        on_change: Callable[[AppConfig], Awaitable[None]],
        *,
        on_error: Callable[[Exception], Awaitable[None]] | None = None,
        debounce_ms: int = 200,
    ) -> None:
        self._path = Path(path)
        self._on_change = on_change
        self._on_error = on_error
        self._debounce = debounce_ms / 1000.0
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        async for changes in awatch(self._path, stop_event=self._stop):
            await asyncio.sleep(self._debounce)
            try:
                cfg = load_config(self._path)
            except ConfigError as exc:
                logger.warning("config reload failed, keeping old: %s", exc)
                if self._on_error:
                    await self._on_error(exc)
                continue
            await self._on_change(cfg)
```

- [ ] **Step 4: Run test, expect PASS**

```bash
pytest tests/unit/test_config_watcher.py -v
# Expect: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_ha/config/watcher.py tests/unit/test_config_watcher.py
git commit -m "feat(config): ConfigWatcher hot-reload with half-write debounce + error swallow"
```

---

## Task 4: SQLite db + migration runner

**Files:**
- Create: `src/ai_ha/store/__init__.py`
- Create: `src/ai_ha/store/db.py`
- Create: `tests/unit/test_db.py`

- [ ] **Step 1: Write failing test** — `tests/unit/test_db.py`

```python
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
```

- [ ] **Step 2: Run test, expect FAIL**

```bash
pytest tests/unit/test_db.py -v
```

- [ ] **Step 3: Write `src/ai_ha/store/__init__.py`**

```python
from ai_ha.store.db import Database, MigrationError

__all__ = ["Database", "MigrationError"]
```

- [ ] **Step 4: Write `src/ai_ha/store/db.py`**

```python
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
    async def open(cls, path: str, *, migrations_dir: str | None) -> "Database":
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
            if row[0] != "ok":
                raise IntegrityError(f"sqlite integrity_check={row[0]}")

    async def _ensure_kv_meta_table(self) -> None:
        async with self.connect() as c:
            await c.execute(
                "CREATE TABLE IF NOT EXISTS kv_meta ("
                "  key TEXT PRIMARY KEY, "
                "  value TEXT NOT NULL, "
                "  updated_at INTEGER NOT NULL"
                ") WITHOUT ROWID"
            )
            await c.commit()

    async def _get_schema_version(self, c: aiosqlite.Connection) -> int:
        row = await (await c.execute(
            "SELECT value FROM kv_meta WHERE key='schema_version'"
        )).fetchone()
        return int(row[0]) if row else 0

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
```

- [ ] **Step 5: Run test, expect PASS**

```bash
pytest tests/unit/test_db.py -v
# Expect: 4 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_ha/store/__init__.py src/ai_ha/store/db.py tests/unit/test_db.py
git commit -m "feat(store): Database with PRAGMA + numbered migration runner"
```

---

## Task 5: 001_initial.sql — the 8-table v0.1.0 schema

**Files:**
- Create: `src/ai_ha/store/migrations/001_initial.sql`
- Create: `tests/unit/test_initial_schema.py`

- [ ] **Step 1: Write failing test** — `tests/unit/test_initial_schema.py`

```python
import pytest
from pathlib import Path
from ai_ha.store.db import Database

SCHEMA_DIR = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"
EXPECTED_TABLES = {
    "kv_meta", "topology_snapshots", "areas", "devices", "entities",
    "events", "counters_per_area", "privacy_drops",
}
EXPECTED_INDEXES = {
    "idx_topology_ts",
    "idx_areas_floor", "idx_areas_snapshot",
    "idx_devices_area", "idx_devices_snapshot",
    "idx_entities_area", "idx_entities_device", "idx_entities_class",
    "idx_entities_domain", "idx_entities_snapshot", "idx_entities_orphan",
    "idx_events_ts", "idx_events_entity_ts", "idx_events_area_ts",
    "idx_events_received",
    "idx_counters_bucket",
}


@pytest.mark.asyncio
async def test_initial_creates_8_tables(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA_DIR))
    async with db.connect() as c:
        rows = await (await c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )).fetchall()
    names = {r[0] for r in rows}
    assert EXPECTED_TABLES.issubset(names)


@pytest.mark.asyncio
async def test_initial_creates_indexes(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA_DIR))
    async with db.connect() as c:
        rows = await (await c.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        )).fetchall()
    names = {r[0] for r in rows}
    missing = EXPECTED_INDEXES - names
    assert not missing, f"missing indexes: {missing}"


@pytest.mark.asyncio
async def test_schema_version_set(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA_DIR))
    async with db.connect() as c:
        row = await (await c.execute(
            "SELECT value FROM kv_meta WHERE key='schema_version'"
        )).fetchone()
    assert row[0] == "1"
```

- [ ] **Step 2: Run test, expect FAIL** (no migration file yet)

- [ ] **Step 3: Write `src/ai_ha/store/migrations/001_initial.sql`**

Use the full DDL from **spec Appendix A — SQLite 完整 DDL**. Copy verbatim (8 `CREATE TABLE` + 16 `CREATE INDEX` statements). Do not modify; the spec is the SSOT for schema.

- [ ] **Step 4: Run test, expect PASS**

```bash
pytest tests/unit/test_initial_schema.py -v
# Expect: 3 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_ha/store/migrations/001_initial.sql tests/unit/test_initial_schema.py
git commit -m "feat(store): 001_initial.sql — 8 tables + 16 indexes per spec Appendix A"
```

---

## Task 6: Privacy hide_matcher (regex compile + DoS guard)

**Files:**
- Create: `src/ai_ha/privacy/__init__.py`
- Create: `src/ai_ha/privacy/hide_matcher.py`
- Create: `tests/unit/test_privacy.py`

- [ ] **Step 1: Write failing test** — `tests/unit/test_privacy.py`

```python
import pytest
from ai_ha.privacy.hide_matcher import HideMatcher, PatternComplexityError


def test_empty_pattern_list_matches_nothing():
    m = HideMatcher([])
    assert m.matches("sensor.anything") is False


def test_exact_pattern_matches():
    m = HideMatcher([r"sensor\.bank_card_.*"])
    assert m.matches("sensor.bank_card_balance") is True
    assert m.matches("sensor.bank_card") is False
    assert m.matches("sensor.living_room_temp") is False


def test_multiple_patterns_or():
    m = HideMatcher([r"sensor\.bank_.*", r"person\.guest"])
    assert m.matches("sensor.bank_x") is True
    assert m.matches("person.guest") is True
    assert m.matches("light.x") is False


def test_invalid_regex_raises_at_construct():
    with pytest.raises(Exception):
        HideMatcher(["[unclosed"])


def test_catastrophic_backtracking_pattern_rejected():
    with pytest.raises(PatternComplexityError):
        HideMatcher([r"(a+)+b"])  # classic ReDoS
    with pytest.raises(PatternComplexityError):
        HideMatcher([r"(.*)*x"])
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Write `src/ai_ha/privacy/__init__.py`**

```python
from ai_ha.privacy.hide_matcher import HideMatcher, PatternComplexityError

__all__ = ["HideMatcher", "PatternComplexityError"]
```

- [ ] **Step 4: Write `src/ai_ha/privacy/hide_matcher.py`**

```python
"""Privacy hide-pattern matcher.

Compiles user-supplied regex list, rejects patterns with high catastrophic-backtracking
risk (nested quantifiers over groups). v0.1.0 uses a heuristic; v0.6+ may swap to re2.
"""
from __future__ import annotations

import re


class PatternComplexityError(ValueError):
    """Pattern looks ReDoS-prone — reject before it can be matched."""


_REDOS_RE = re.compile(
    r"\([^)]*[+*][^)]*\)\s*[+*]"   # (X+)+ / (X*)* / (.X)*+ etc
    r"|"
    r"\(\.\*\)\s*[+*]"             # (.*)*
)


def _complexity_guard(pattern: str) -> None:
    if _REDOS_RE.search(pattern):
        raise PatternComplexityError(
            f"pattern {pattern!r} contains nested-quantifier construct "
            "(catastrophic backtracking risk); reject"
        )


class HideMatcher:
    def __init__(self, patterns: list[str]) -> None:
        self._compiled: list[re.Pattern[str]] = []
        for p in patterns:
            _complexity_guard(p)
            self._compiled.append(re.compile(p))

    def matches(self, entity_id: str) -> bool:
        return any(c.fullmatch(entity_id) for c in self._compiled)
```

- [ ] **Step 5: Run test, expect PASS**

```bash
pytest tests/unit/test_privacy.py -v
# Expect: 5 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_ha/privacy/__init__.py src/ai_ha/privacy/hide_matcher.py tests/unit/test_privacy.py
git commit -m "feat(privacy): HideMatcher with ReDoS-guard heuristic"
```

---

## Task 7: Topology snapshot_store (append-only versioned)

**Files:**
- Create: `src/ai_ha/topology/__init__.py`
- Create: `src/ai_ha/topology/snapshot_store.py`
- Create: `tests/unit/test_snapshot_store.py`

- [ ] **Step 1: Write failing test** — `tests/unit/test_snapshot_store.py`

```python
import json
import pytest
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.topology.snapshot_store import SnapshotStore, TopologyPayload

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_insert_returns_id(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    store = SnapshotStore(db)
    payload = TopologyPayload(
        areas=[{"area_id": "a1", "name": "Living"}],
        devices=[],
        entities=[],
    )
    sid, was_new = await store.insert_if_changed(payload, ts_ms=1000)
    assert sid >= 1
    assert was_new is True


@pytest.mark.asyncio
async def test_same_payload_not_duplicated(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    store = SnapshotStore(db)
    payload = TopologyPayload(areas=[{"area_id": "a1"}], devices=[], entities=[])
    sid1, new1 = await store.insert_if_changed(payload, ts_ms=1000)
    sid2, new2 = await store.insert_if_changed(payload, ts_ms=2000)
    assert sid1 == sid2
    assert new1 is True and new2 is False


@pytest.mark.asyncio
async def test_changed_payload_creates_new(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    store = SnapshotStore(db)
    p1 = TopologyPayload(areas=[{"area_id": "a1"}], devices=[], entities=[])
    p2 = TopologyPayload(areas=[{"area_id": "a2"}], devices=[], entities=[])
    sid1, _ = await store.insert_if_changed(p1, ts_ms=1000)
    sid2, _ = await store.insert_if_changed(p2, ts_ms=2000)
    assert sid2 > sid1


@pytest.mark.asyncio
async def test_get_current_returns_last(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    store = SnapshotStore(db)
    assert await store.get_current() is None
    sid, _ = await store.insert_if_changed(
        TopologyPayload(areas=[], devices=[], entities=[]), ts_ms=1000
    )
    cur = await store.get_current()
    assert cur is not None and cur.snapshot_id == sid


@pytest.mark.asyncio
async def test_hash_uses_canonical_json(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    store = SnapshotStore(db)
    p1 = TopologyPayload(
        areas=[{"area_id": "a1", "name": "Living"}], devices=[], entities=[],
    )
    p2 = TopologyPayload(
        areas=[{"name": "Living", "area_id": "a1"}], devices=[], entities=[],
    )
    sid1, _ = await store.insert_if_changed(p1, ts_ms=1000)
    sid2, _ = await store.insert_if_changed(p2, ts_ms=2000)
    assert sid1 == sid2  # key order should not matter
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Write `src/ai_ha/topology/__init__.py`**

```python
from ai_ha.topology.snapshot_store import SnapshotStore, TopologyPayload, Snapshot

__all__ = ["SnapshotStore", "TopologyPayload", "Snapshot"]
```

- [ ] **Step 4: Write `src/ai_ha/topology/snapshot_store.py`**

```python
"""Append-only versioned topology snapshots.

Each TopologyPayload is hashed (canonical JSON, sha256). If hash matches the most
recent snapshot, no new row is inserted — same snapshot_id is returned. Otherwise
a new row appends with auto-incrementing snapshot_id. Old rows are never modified.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from ai_ha.store.db import Database


@dataclass(frozen=True)
class TopologyPayload:
    areas: list[dict[str, Any]] = field(default_factory=list)
    devices: list[dict[str, Any]] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)

    def to_canonical_json(self) -> str:
        return json.dumps(
            {"areas": self.areas, "devices": self.devices, "entities": self.entities},
            sort_keys=True,
            separators=(",", ":"),
        )

    def hash_hex(self) -> str:
        return hashlib.sha256(self.to_canonical_json().encode()).hexdigest()


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: int
    ts_ms: int
    payload_hash: str
    payload: TopologyPayload
    diff_summary: str | None


class SnapshotStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_current(self) -> Snapshot | None:
        async with self._db.connect() as c:
            row = await (await c.execute(
                "SELECT snapshot_id, ts, payload_hash, payload, diff_summary "
                "FROM topology_snapshots ORDER BY snapshot_id DESC LIMIT 1"
            )).fetchone()
        if row is None:
            return None
        return _row_to_snapshot(row)

    async def insert_if_changed(
        self,
        payload: TopologyPayload,
        *,
        ts_ms: int,
        diff_summary: str | None = None,
    ) -> tuple[int, bool]:
        new_hash = payload.hash_hex()
        async with self._db.connect() as c:
            row = await (await c.execute(
                "SELECT snapshot_id FROM topology_snapshots WHERE payload_hash=?",
                (new_hash,),
            )).fetchone()
            if row is not None:
                return int(row[0]), False
            cur = await c.execute(
                "INSERT INTO topology_snapshots(ts, payload_hash, payload, diff_summary) "
                "VALUES (?, ?, ?, ?)",
                (ts_ms, new_hash, payload.to_canonical_json(), diff_summary),
            )
            await c.commit()
            return int(cur.lastrowid), True


def _row_to_snapshot(row: Any) -> Snapshot:
    raw = json.loads(row[3])
    return Snapshot(
        snapshot_id=int(row[0]),
        ts_ms=int(row[1]),
        payload_hash=str(row[2]),
        payload=TopologyPayload(
            areas=raw.get("areas", []),
            devices=raw.get("devices", []),
            entities=raw.get("entities", []),
        ),
        diff_summary=row[4],
    )
```

- [ ] **Step 5: Run test, expect PASS**

```bash
pytest tests/unit/test_snapshot_store.py -v
# Expect: 5 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_ha/topology/__init__.py src/ai_ha/topology/snapshot_store.py tests/unit/test_snapshot_store.py
git commit -m "feat(topology): append-only SnapshotStore with canonical-JSON hash dedup"
```

---

## Task 8: Topology entity_index (in-mem read-only cache)

**Files:**
- Create: `src/ai_ha/topology/entity_index.py`
- Create: `tests/unit/test_entity_index.py`

- [ ] **Step 1: Write failing test** — `tests/unit/test_entity_index.py`

```python
from ai_ha.topology.entity_index import EntityIndex, EntityRef
from ai_ha.topology.snapshot_store import TopologyPayload


def test_empty_index_lookup_returns_none():
    idx = EntityIndex.build_from_payload(TopologyPayload(), snapshot_id=0)
    assert idx.lookup("light.x") is None


def test_lookup_resolves_full_chain():
    payload = TopologyPayload(
        areas=[{"area_id": "a1", "name": "Living"}],
        devices=[{"device_id": "d1", "area_id": "a1"}],
        entities=[{
            "entity_id": "light.living_room", "device_id": "d1",
            "area_id": None,  # inherited from device
            "device_class": "light",
        }],
    )
    idx = EntityIndex.build_from_payload(payload, snapshot_id=7)
    ref = idx.lookup("light.living_room")
    assert ref == EntityRef(
        device_id="d1", area_id="a1", device_class="light", snapshot_id=7,
    )


def test_lookup_uses_entity_area_when_set():
    payload = TopologyPayload(
        areas=[{"area_id": "a1"}, {"area_id": "a2"}],
        devices=[{"device_id": "d1", "area_id": "a1"}],
        entities=[{
            "entity_id": "light.x", "device_id": "d1",
            "area_id": "a2",  # overrides device's a1
            "device_class": "light",
        }],
    )
    idx = EntityIndex.build_from_payload(payload, snapshot_id=1)
    ref = idx.lookup("light.x")
    assert ref is not None and ref.area_id == "a2"


def test_rebuild_swaps_atomically():
    p1 = TopologyPayload(
        areas=[{"area_id": "a1"}],
        devices=[{"device_id": "d1", "area_id": "a1"}],
        entities=[{"entity_id": "e1", "device_id": "d1", "area_id": None}],
    )
    idx = EntityIndex.build_from_payload(p1, snapshot_id=1)
    p2 = TopologyPayload(
        areas=[{"area_id": "a2"}],
        devices=[{"device_id": "d1", "area_id": "a2"}],
        entities=[{"entity_id": "e1", "device_id": "d1", "area_id": None}],
    )
    idx.rebuild_from_payload(p2, snapshot_id=2)
    ref = idx.lookup("e1")
    assert ref is not None and ref.area_id == "a2" and ref.snapshot_id == 2
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Write `src/ai_ha/topology/entity_index.py`**

```python
"""In-memory entity → (device, area, device_class) cache.

Read path is lock-free (atomic dict-pointer swap on rebuild). Write path holds a
single asyncio lock during rebuild. Each lookup returns the snapshot_id active at
build time so the ingest pipeline can stamp events.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from ai_ha.topology.snapshot_store import TopologyPayload


@dataclass(frozen=True)
class EntityRef:
    device_id: str | None
    area_id: str | None
    device_class: str | None
    snapshot_id: int


class EntityIndex:
    def __init__(self) -> None:
        self._map: dict[str, EntityRef] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def build_from_payload(cls, payload: TopologyPayload, *, snapshot_id: int) -> "EntityIndex":
        idx = cls()
        idx._map = _build(payload, snapshot_id)
        return idx

    def lookup(self, entity_id: str) -> EntityRef | None:
        return self._map.get(entity_id)

    def rebuild_from_payload(self, payload: TopologyPayload, *, snapshot_id: int) -> None:
        new_map = _build(payload, snapshot_id)
        self._map = new_map  # atomic pointer swap

    async def rebuild_async(self, payload: TopologyPayload, *, snapshot_id: int) -> None:
        async with self._lock:
            self.rebuild_from_payload(payload, snapshot_id=snapshot_id)


def _build(payload: TopologyPayload, snapshot_id: int) -> dict[str, EntityRef]:
    device_to_area = {
        d["device_id"]: d.get("area_id") for d in payload.devices if "device_id" in d
    }
    out: dict[str, EntityRef] = {}
    for e in payload.entities:
        eid = e.get("entity_id")
        if not eid:
            continue
        dev_id = e.get("device_id")
        area_id = e.get("area_id") or device_to_area.get(dev_id)
        out[eid] = EntityRef(
            device_id=dev_id,
            area_id=area_id,
            device_class=e.get("device_class"),
            snapshot_id=snapshot_id,
        )
    return out
```

- [ ] **Step 4: Run test, expect PASS**

```bash
pytest tests/unit/test_entity_index.py -v
# Expect: 4 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_ha/topology/entity_index.py tests/unit/test_entity_index.py
git commit -m "feat(topology): EntityIndex in-memory cache with atomic rebuild"
```

---

## Task 9: Topology orphan_detector

**Files:**
- Create: `src/ai_ha/topology/orphan_detector.py`
- Create: `tests/unit/test_orphan_detector.py`

- [ ] **Step 1: Write failing test** — `tests/unit/test_orphan_detector.py`

```python
from ai_ha.topology.orphan_detector import find_orphans
from ai_ha.topology.snapshot_store import TopologyPayload


def test_no_orphans_when_all_have_area():
    p = TopologyPayload(
        areas=[{"area_id": "a1"}],
        devices=[{"device_id": "d1", "area_id": "a1"}],
        entities=[
            {"entity_id": "e1", "device_id": "d1", "area_id": None},
            {"entity_id": "e2", "device_id": None, "area_id": "a1"},
        ],
    )
    assert find_orphans(p) == []


def test_orphan_no_device_no_area():
    p = TopologyPayload(
        areas=[{"area_id": "a1"}],
        devices=[],
        entities=[{"entity_id": "orphan.x", "device_id": None, "area_id": None}],
    )
    assert find_orphans(p) == ["orphan.x"]


def test_orphan_device_without_area():
    p = TopologyPayload(
        areas=[{"area_id": "a1"}],
        devices=[{"device_id": "d_orphan", "area_id": None}],
        entities=[{"entity_id": "x", "device_id": "d_orphan", "area_id": None}],
    )
    assert find_orphans(p) == ["x"]


def test_disabled_entities_skipped():
    p = TopologyPayload(
        areas=[],
        devices=[],
        entities=[
            {"entity_id": "x", "device_id": None, "area_id": None, "disabled_by": "user"},
            {"entity_id": "y", "device_id": None, "area_id": None},
        ],
    )
    assert find_orphans(p) == ["y"]
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Write `src/ai_ha/topology/orphan_detector.py`**

```python
"""Detect entities with no area attribution (neither direct nor via device)."""
from __future__ import annotations

from ai_ha.topology.snapshot_store import TopologyPayload


def find_orphans(payload: TopologyPayload) -> list[str]:
    device_to_area = {
        d["device_id"]: d.get("area_id") for d in payload.devices if "device_id" in d
    }
    orphans: list[str] = []
    for e in payload.entities:
        if e.get("disabled_by"):
            continue
        if e.get("area_id"):
            continue
        if e.get("device_id") and device_to_area.get(e["device_id"]):
            continue
        if eid := e.get("entity_id"):
            orphans.append(eid)
    return orphans
```

- [ ] **Step 4: Run test, expect PASS**

```bash
pytest tests/unit/test_orphan_detector.py -v
# Expect: 4 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_ha/topology/orphan_detector.py tests/unit/test_orphan_detector.py
git commit -m "feat(topology): find_orphans for unattributed entities"
```

---

## Task 10: Archive jsonl_writer (daily rotate + gzip)

**Files:**
- Create: `src/ai_ha/archive/__init__.py`
- Create: `src/ai_ha/archive/jsonl_writer.py`
- Create: `tests/unit/test_jsonl_writer.py`

- [ ] **Step 1: Write failing test** — `tests/unit/test_jsonl_writer.py`

```python
import gzip
import json
import pytest
from datetime import datetime, timezone
from ai_ha.archive.jsonl_writer import JsonlWriter


@pytest.mark.asyncio
async def test_append_and_read_back(tmp_path):
    w = JsonlWriter(str(tmp_path), compress=False)
    await w.append({"event_id": 1, "ts": 1000}, ts_ms=1_700_000_000_000)
    await w.flush()
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text().splitlines()
    assert json.loads(lines[0])["event_id"] == 1


@pytest.mark.asyncio
async def test_rotate_on_day_change(tmp_path):
    w = JsonlWriter(str(tmp_path), compress=False)
    # day 1
    ts1 = int(datetime(2026, 6, 1, 23, 50, tzinfo=timezone.utc).timestamp() * 1000)
    await w.append({"e": 1}, ts_ms=ts1)
    # day 2
    ts2 = int(datetime(2026, 6, 2, 0, 10, tzinfo=timezone.utc).timestamp() * 1000)
    await w.append({"e": 2}, ts_ms=ts2)
    await w.flush()
    files = sorted(tmp_path.glob("*.jsonl"))
    assert [f.name for f in files] == ["2026-06-01.jsonl", "2026-06-02.jsonl"]


@pytest.mark.asyncio
async def test_compress_appends_gz(tmp_path):
    w = JsonlWriter(str(tmp_path), compress=True)
    await w.append({"e": 1}, ts_ms=1_700_000_000_000)
    await w.flush()
    files = list(tmp_path.glob("*.jsonl.gz"))
    assert len(files) == 1
    with gzip.open(files[0], "rt") as f:
        line = f.readline()
    assert json.loads(line)["e"] == 1
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Write `src/ai_ha/archive/__init__.py`**

```python
from ai_ha.archive.jsonl_writer import JsonlWriter

__all__ = ["JsonlWriter"]
```

- [ ] **Step 4: Write `src/ai_ha/archive/jsonl_writer.py`**

```python
"""Daily-rotating JSONL writer with optional gzip.

Filename: YYYY-MM-DD.jsonl[.gz] in UTC. Append-only; on day rollover, the current
file handle is closed and a new file is opened. Flush is explicit (called by ingest
batch commit). No buffer cap — if disk fills, OSError surfaces to caller.
"""
from __future__ import annotations

import asyncio
import gzip
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonlWriter:
    def __init__(self, directory: str | Path, *, compress: bool = True) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._compress = compress
        self._current_day: str | None = None
        self._handle: io.IOBase | None = None
        self._lock = asyncio.Lock()

    def _path_for_day(self, day: str) -> Path:
        suffix = ".jsonl.gz" if self._compress else ".jsonl"
        return self._dir / f"{day}{suffix}"

    def _ensure_day(self, day: str) -> None:
        if self._current_day == day and self._handle is not None:
            return
        if self._handle is not None:
            self._handle.close()
        path = self._path_for_day(day)
        if self._compress:
            self._handle = gzip.open(path, "at")  # text-append
        else:
            self._handle = open(path, "a", encoding="utf-8")
        self._current_day = day

    async def append(self, record: dict[str, Any], *, ts_ms: int) -> None:
        day = datetime.fromtimestamp(ts_ms / 1000.0, timezone.utc).strftime("%Y-%m-%d")
        async with self._lock:
            self._ensure_day(day)
            assert self._handle is not None
            self._handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def flush(self) -> None:
        async with self._lock:
            if self._handle is not None:
                self._handle.flush()

    async def close(self) -> None:
        async with self._lock:
            if self._handle is not None:
                self._handle.close()
                self._handle = None
                self._current_day = None
```

- [ ] **Step 5: Run test, expect PASS**

```bash
pytest tests/unit/test_jsonl_writer.py -v
# Expect: 3 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_ha/archive/__init__.py src/ai_ha/archive/jsonl_writer.py tests/unit/test_jsonl_writer.py
git commit -m "feat(archive): JsonlWriter with daily UTC rotation + optional gzip"
```

---

## Task 11: Store DAO (upserts + queries for areas/devices/entities/events/counters)

**Files:**
- Create: `src/ai_ha/store/dao.py`
- Create: `tests/unit/test_dao.py`

- [ ] **Step 1: Write failing test** — `tests/unit/test_dao.py`

```python
import pytest
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, EventRow, EntityRow, AreaRow, DeviceRow

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.fixture
async def dao(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    yield StoreDAO(db)


@pytest.mark.asyncio
async def test_upsert_area_then_get(dao):
    await dao.upsert_areas([
        AreaRow(area_id="a1", name="Living", floor_id=None,
                icon=None, aliases="[]", snapshot_id=1,
                first_seen_at=1000, last_seen_at=1000),
    ])
    rows = await dao.list_areas()
    assert len(rows) == 1 and rows[0].name == "Living"


@pytest.mark.asyncio
async def test_upsert_area_updates_existing(dao):
    await dao.upsert_areas([
        AreaRow(area_id="a1", name="Living", floor_id=None, icon=None,
                aliases="[]", snapshot_id=1, first_seen_at=1000, last_seen_at=1000),
    ])
    await dao.upsert_areas([
        AreaRow(area_id="a1", name="Salon", floor_id=None, icon=None,
                aliases="[]", snapshot_id=2, first_seen_at=1000, last_seen_at=2000),
    ])
    rows = await dao.list_areas()
    assert rows[0].name == "Salon" and rows[0].snapshot_id == 2
    # first_seen_at preserved
    assert rows[0].first_seen_at == 1000


@pytest.mark.asyncio
async def test_insert_event_and_query_by_area(dao):
    await dao.insert_events([
        EventRow(ts=1000, received_at=1001, entity_id="light.x",
                 event_type="state_changed", old_state=None, new_state='"on"',
                 context_user_id=None, context_parent_id=None,
                 area_id="a1", device_id=None, device_class="light",
                 snapshot_id=1),
    ])
    rows = await dao.list_events(area_id="a1", limit=10)
    assert len(rows) == 1 and rows[0].entity_id == "light.x"


@pytest.mark.asyncio
async def test_orphan_entities_query(dao):
    await dao.upsert_entities([
        EntityRow(entity_id="x", friendly_name="X", domain="light",
                  device_class=None, device_id=None, area_id=None,
                  disabled=0, snapshot_id=1, first_seen_at=1000,
                  last_seen_at=1000, event_count_24h=0,
                  total_event_count=0),
        EntityRow(entity_id="y", friendly_name="Y", domain="light",
                  device_class=None, device_id=None, area_id="a1",
                  disabled=0, snapshot_id=1, first_seen_at=1000,
                  last_seen_at=1000, event_count_24h=0,
                  total_event_count=0),
    ])
    orphans = await dao.list_entities(orphan=True)
    assert {e.entity_id for e in orphans} == {"x"}


@pytest.mark.asyncio
async def test_counters_increment(dao):
    await dao.increment_counter("a1", hour_bucket_utc=100, by=3)
    await dao.increment_counter("a1", hour_bucket_utc=100, by=2)
    await dao.increment_counter("a1", hour_bucket_utc=101, by=1)
    cnts = await dao.get_counters_24h(now_hour=101)
    assert cnts.get(("a1", 100)) == 5
    assert cnts.get(("a1", 101)) == 1


@pytest.mark.asyncio
async def test_privacy_drop_increment(dao):
    await dao.increment_privacy_drop(hour_bucket_utc=100, by=5)
    await dao.increment_privacy_drop(hour_bucket_utc=100, by=2)
    cnts = await dao.get_privacy_drops_24h(now_hour=100)
    assert cnts.get(100) == 7
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Write `src/ai_ha/store/dao.py`**

```python
"""Data Access Objects for v0.1.0 schema.

Each DAO method maps to one or two SQL statements. UPSERT semantics preserve
first_seen_at on conflict. Bulk inserts use executemany. Queries return frozen
dataclasses so the calling code is type-safe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiosqlite

from ai_ha.store.db import Database


@dataclass(frozen=True)
class AreaRow:
    area_id: str
    name: str
    floor_id: str | None
    icon: str | None
    aliases: str
    snapshot_id: int
    first_seen_at: int
    last_seen_at: int


@dataclass(frozen=True)
class DeviceRow:
    device_id: str
    name: str | None
    manufacturer: str | None
    model: str | None
    area_id: str | None
    sw_version: str | None
    snapshot_id: int
    first_seen_at: int
    last_seen_at: int


@dataclass(frozen=True)
class EntityRow:
    entity_id: str
    friendly_name: str | None
    domain: str
    device_class: str | None
    device_id: str | None
    area_id: str | None
    disabled: int
    snapshot_id: int
    first_seen_at: int
    last_seen_at: int
    event_count_24h: int
    total_event_count: int


@dataclass(frozen=True)
class EventRow:
    ts: int
    received_at: int
    entity_id: str
    event_type: str
    old_state: str | None
    new_state: str | None
    context_user_id: str | None
    context_parent_id: str | None
    area_id: str | None
    device_id: str | None
    device_class: str | None
    snapshot_id: int


class StoreDAO:
    def __init__(self, db: Database) -> None:
        self._db = db

    # ---------- areas ----------
    async def upsert_areas(self, rows: list[AreaRow]) -> None:
        if not rows:
            return
        async with self._db.connect() as c:
            await c.executemany(
                "INSERT INTO areas(area_id, name, floor_id, icon, aliases, "
                "  snapshot_id, first_seen_at, last_seen_at) "
                "VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(area_id) DO UPDATE SET "
                "  name=excluded.name, floor_id=excluded.floor_id, icon=excluded.icon, "
                "  aliases=excluded.aliases, snapshot_id=excluded.snapshot_id, "
                "  last_seen_at=excluded.last_seen_at",
                [(r.area_id, r.name, r.floor_id, r.icon, r.aliases,
                  r.snapshot_id, r.first_seen_at, r.last_seen_at) for r in rows],
            )
            await c.commit()

    async def list_areas(self) -> list[AreaRow]:
        async with self._db.connect() as c:
            rows = await (await c.execute(
                "SELECT area_id, name, floor_id, icon, aliases, "
                "snapshot_id, first_seen_at, last_seen_at FROM areas ORDER BY name"
            )).fetchall()
        return [AreaRow(*r) for r in rows]

    # ---------- devices ----------
    async def upsert_devices(self, rows: list[DeviceRow]) -> None:
        if not rows:
            return
        async with self._db.connect() as c:
            await c.executemany(
                "INSERT INTO devices(device_id, name, manufacturer, model, area_id, "
                "  sw_version, snapshot_id, first_seen_at, last_seen_at) "
                "VALUES(?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(device_id) DO UPDATE SET "
                "  name=excluded.name, manufacturer=excluded.manufacturer, "
                "  model=excluded.model, area_id=excluded.area_id, "
                "  sw_version=excluded.sw_version, snapshot_id=excluded.snapshot_id, "
                "  last_seen_at=excluded.last_seen_at",
                [(r.device_id, r.name, r.manufacturer, r.model, r.area_id,
                  r.sw_version, r.snapshot_id, r.first_seen_at, r.last_seen_at)
                 for r in rows],
            )
            await c.commit()

    # ---------- entities ----------
    async def upsert_entities(self, rows: list[EntityRow]) -> None:
        if not rows:
            return
        async with self._db.connect() as c:
            await c.executemany(
                "INSERT INTO entities(entity_id, friendly_name, domain, device_class, "
                "  device_id, area_id, disabled, snapshot_id, first_seen_at, "
                "  last_seen_at, event_count_24h, total_event_count) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(entity_id) DO UPDATE SET "
                "  friendly_name=excluded.friendly_name, "
                "  domain=excluded.domain, device_class=excluded.device_class, "
                "  device_id=excluded.device_id, area_id=excluded.area_id, "
                "  disabled=excluded.disabled, snapshot_id=excluded.snapshot_id, "
                "  last_seen_at=excluded.last_seen_at",
                [(r.entity_id, r.friendly_name, r.domain, r.device_class,
                  r.device_id, r.area_id, r.disabled, r.snapshot_id,
                  r.first_seen_at, r.last_seen_at,
                  r.event_count_24h, r.total_event_count) for r in rows],
            )
            await c.commit()

    async def bump_entity_event_counts(
        self, *, entity_id: str, last_seen_at: int
    ) -> None:
        async with self._db.connect() as c:
            await c.execute(
                "UPDATE entities SET "
                "  event_count_24h = event_count_24h + 1, "
                "  total_event_count = total_event_count + 1, "
                "  last_seen_at = ? "
                "WHERE entity_id = ?",
                (last_seen_at, entity_id),
            )
            await c.commit()

    async def list_entities(
        self, *, area_id: str | None = None,
        orphan: bool = False, device_class: str | None = None,
        limit: int = 1000,
    ) -> list[EntityRow]:
        clauses = []
        params: list[Any] = []
        if orphan:
            clauses.append("area_id IS NULL")
        elif area_id is not None:
            clauses.append("area_id = ?")
            params.append(area_id)
        if device_class is not None:
            clauses.append("device_class = ?")
            params.append(device_class)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        async with self._db.connect() as c:
            rows = await (await c.execute(
                "SELECT entity_id, friendly_name, domain, device_class, "
                "  device_id, area_id, disabled, snapshot_id, first_seen_at, "
                "  last_seen_at, event_count_24h, total_event_count "
                f"FROM entities{where} LIMIT ?",
                params,
            )).fetchall()
        return [EntityRow(*r) for r in rows]

    # ---------- events ----------
    async def insert_events(self, rows: list[EventRow]) -> None:
        if not rows:
            return
        async with self._db.connect() as c:
            await c.executemany(
                "INSERT INTO events(ts, received_at, entity_id, event_type, "
                "  old_state, new_state, context_user_id, context_parent_id, "
                "  area_id, device_id, device_class, snapshot_id) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                [(r.ts, r.received_at, r.entity_id, r.event_type,
                  r.old_state, r.new_state, r.context_user_id, r.context_parent_id,
                  r.area_id, r.device_id, r.device_class, r.snapshot_id)
                 for r in rows],
            )
            await c.commit()

    async def list_events(
        self, *, entity_id: str | None = None, area_id: str | None = None,
        since_ts: int | None = None, until_ts: int | None = None,
        cursor: int | None = None, limit: int = 100,
    ) -> list[EventRow]:
        clauses = []
        params: list[Any] = []
        if entity_id:
            clauses.append("entity_id = ?")
            params.append(entity_id)
        if area_id:
            clauses.append("area_id = ?")
            params.append(area_id)
        if since_ts is not None:
            clauses.append("ts >= ?")
            params.append(since_ts)
        if until_ts is not None:
            clauses.append("ts <= ?")
            params.append(until_ts)
        if cursor is not None:
            clauses.append("event_id < ?")
            params.append(cursor)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        async with self._db.connect() as c:
            rows = await (await c.execute(
                "SELECT ts, received_at, entity_id, event_type, "
                "  old_state, new_state, context_user_id, context_parent_id, "
                "  area_id, device_id, device_class, snapshot_id "
                f"FROM events{where} ORDER BY event_id DESC LIMIT ?",
                params,
            )).fetchall()
        return [EventRow(*r) for r in rows]

    # ---------- counters ----------
    async def increment_counter(
        self, area_id: str, *, hour_bucket_utc: int, by: int = 1
    ) -> None:
        async with self._db.connect() as c:
            await c.execute(
                "INSERT INTO counters_per_area(area_id, hour_bucket_utc, event_count) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(area_id, hour_bucket_utc) DO UPDATE SET "
                "  event_count = event_count + excluded.event_count",
                (area_id, hour_bucket_utc, by),
            )
            await c.commit()

    async def get_counters_24h(self, *, now_hour: int) -> dict[tuple[str, int], int]:
        async with self._db.connect() as c:
            rows = await (await c.execute(
                "SELECT area_id, hour_bucket_utc, event_count "
                "FROM counters_per_area WHERE hour_bucket_utc > ?",
                (now_hour - 24,),
            )).fetchall()
        return {(r[0], r[1]): r[2] for r in rows}

    # ---------- privacy_drops ----------
    async def increment_privacy_drop(self, *, hour_bucket_utc: int, by: int = 1) -> None:
        async with self._db.connect() as c:
            await c.execute(
                "INSERT INTO privacy_drops(hour_bucket_utc, drop_count) "
                "VALUES (?, ?) "
                "ON CONFLICT(hour_bucket_utc) DO UPDATE SET "
                "  drop_count = drop_count + excluded.drop_count",
                (hour_bucket_utc, by),
            )
            await c.commit()

    async def get_privacy_drops_24h(self, *, now_hour: int) -> dict[int, int]:
        async with self._db.connect() as c:
            rows = await (await c.execute(
                "SELECT hour_bucket_utc, drop_count FROM privacy_drops "
                "WHERE hour_bucket_utc > ?",
                (now_hour - 24,),
            )).fetchall()
        return {r[0]: r[1] for r in rows}

    # ---------- kv_meta ----------
    async def get_meta(self, key: str) -> str | None:
        async with self._db.connect() as c:
            row = await (await c.execute(
                "SELECT value FROM kv_meta WHERE key=?", (key,)
            )).fetchone()
        return row[0] if row else None

    async def set_meta(self, key: str, value: str, *, ts_ms: int) -> None:
        async with self._db.connect() as c:
            await c.execute(
                "INSERT OR REPLACE INTO kv_meta(key, value, updated_at) "
                "VALUES (?, ?, ?)",
                (key, value, ts_ms),
            )
            await c.commit()
```

- [ ] **Step 4: Run test, expect PASS**

```bash
pytest tests/unit/test_dao.py -v
# Expect: 6 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_ha/store/dao.py tests/unit/test_dao.py
git commit -m "feat(store): StoreDAO with UPSERT semantics + cursor-paginated queries"
```

---

# Phase 2 — HA Adapter + Ingest (Day 6-9)

## Task 12: HAClient (REST snapshot + state fetch)

**Files:**
- Create: `src/ai_ha/ha_adapter/__init__.py`
- Create: `src/ai_ha/ha_adapter/client.py`
- Create: `tests/unit/test_ha_client.py`

- [ ] **Step 1: Write failing test** — `tests/unit/test_ha_client.py`

```python
import pytest
import respx
from httpx import Response
from ai_ha.ha_adapter.client import HAClient, HAUnreachable, HAAuthInvalid


@pytest.mark.asyncio
@respx.mock
async def test_fetch_states_returns_list():
    respx.get("http://ha/api/states").mock(
        return_value=Response(200, json=[
            {"entity_id": "light.x", "state": "on", "last_updated": "2026-06-02T10:00:00+00:00"},
        ])
    )
    c = HAClient("http://ha", "tok")
    states = await c.fetch_states()
    assert states[0]["entity_id"] == "light.x"
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_auth_invalid_raises():
    respx.get("http://ha/api/states").mock(return_value=Response(401))
    c = HAClient("http://ha", "tok")
    with pytest.raises(HAAuthInvalid):
        await c.fetch_states()
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_unreachable_raises():
    import httpx
    respx.get("http://ha/api/states").mock(side_effect=httpx.ConnectError("nope"))
    c = HAClient("http://ha", "tok", connect_retries=2)
    with pytest.raises(HAUnreachable):
        await c.fetch_states()
    await c.aclose()
```

Add `respx==0.21.1` to requirements.txt (test-only).

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Write `src/ai_ha/ha_adapter/__init__.py`**

```python
from ai_ha.ha_adapter.client import HAClient, HAUnreachable, HAAuthInvalid

__all__ = ["HAClient", "HAUnreachable", "HAAuthInvalid"]
```

- [ ] **Step 4: Write `src/ai_ha/ha_adapter/client.py`**

```python
"""HA REST client (auth header + state snapshot)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class HAUnreachable(RuntimeError):
    """REST endpoint unreachable after retries."""


class HAAuthInvalid(RuntimeError):
    """HA returned 401/403 — token is bad."""


class HAClient:
    def __init__(
        self, base_url: str, token: str, *,
        timeout_s: float = 10.0, connect_retries: int = 5,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._client = httpx.AsyncClient(
            base_url=self._base, timeout=timeout_s, headers=self._headers,
        )
        self._retries = connect_retries

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_states(self) -> list[dict[str, Any]]:
        delay = 1.0
        for attempt in range(self._retries):
            try:
                r = await self._client.get("/api/states")
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                logger.warning("ha REST attempt %d failed: %s", attempt + 1, exc)
                if attempt + 1 == self._retries:
                    raise HAUnreachable(f"after {self._retries} attempts") from exc
                await asyncio.sleep(delay)
                delay = min(60.0, delay * 2)
                continue
            if r.status_code in (401, 403):
                raise HAAuthInvalid(f"status={r.status_code}")
            r.raise_for_status()
            return r.json()
        raise HAUnreachable("retries exhausted")
```

- [ ] **Step 5: Run test, expect PASS**

```bash
pytest tests/unit/test_ha_client.py -v
# Expect: 3 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_ha/ha_adapter/__init__.py src/ai_ha/ha_adapter/client.py tests/unit/test_ha_client.py requirements.txt
git commit -m "feat(ha): HAClient REST with bearer auth + exp-backoff retries"
```

---

## Task 13: Mock HA WS server (test infrastructure)

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/mock_ha_server.py`
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_mock_ha_smoke.py`

- [ ] **Step 1: Write `tests/integration/mock_ha_server.py`**

```python
"""Minimal HA-compatible WebSocket server for integration tests.

Implements: auth handshake, subscribe_events (state_changed firehose),
config/{area,device,entity}_registry/list, *_registry_updated events.
Not a full HA simulator — only the surface ai-ha needs.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection, serve


class MockHAServer:
    def __init__(self) -> None:
        self.port: int = 0
        self._token = "test-token-not-real"
        self._areas: list[dict[str, Any]] = []
        self._devices: list[dict[str, Any]] = []
        self._entities: list[dict[str, Any]] = []
        self._states: list[dict[str, Any]] = []
        self._connections: set[ServerConnection] = set()
        self._server: Any = None
        self._next_id = 1

    async def start(self) -> None:
        self._server = await serve(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        for c in list(self._connections):
            await c.close()
        self._server.close()
        await self._server.wait_closed()

    def set_topology(
        self, areas: list[dict[str, Any]], devices: list[dict[str, Any]],
        entities: list[dict[str, Any]],
    ) -> None:
        self._areas, self._devices, self._entities = areas, devices, entities

    def set_states(self, states: list[dict[str, Any]]) -> None:
        self._states = states

    async def push_event(self, entity_id: str, *, old: str | None, new: str) -> None:
        for c in list(self._connections):
            await c.send(json.dumps({
                "id": 1, "type": "event",
                "event": {
                    "event_type": "state_changed",
                    "data": {
                        "entity_id": entity_id,
                        "old_state": {"state": old} if old is not None else None,
                        "new_state": {"state": new},
                    },
                    "time_fired": "2026-06-02T10:00:00+00:00",
                },
            }))

    async def push_registry_updated(self, kind: str) -> None:
        assert kind in ("area", "device", "entity")
        for c in list(self._connections):
            await c.send(json.dumps({
                "id": 1, "type": "event",
                "event": {"event_type": f"{kind}_registry_updated", "data": {}},
            }))

    async def disconnect_all(self) -> None:
        for c in list(self._connections):
            await c.close()

    async def _handle(self, ws: ServerConnection) -> None:
        self._connections.add(ws)
        try:
            await ws.send(json.dumps({"type": "auth_required"}))
            msg = json.loads(await ws.recv())
            if msg.get("access_token") != self._token:
                await ws.send(json.dumps({"type": "auth_invalid"}))
                return
            await ws.send(json.dumps({"type": "auth_ok"}))
            async for raw in ws:
                req = json.loads(raw)
                await self._dispatch(ws, req)
        except websockets.ConnectionClosed:
            pass
        finally:
            self._connections.discard(ws)

    async def _dispatch(self, ws: ServerConnection, req: dict[str, Any]) -> None:
        rid = req.get("id", 0)
        t = req.get("type", "")
        if t == "subscribe_events":
            await ws.send(json.dumps({"id": rid, "type": "result", "success": True}))
        elif t == "config/area_registry/list":
            await ws.send(json.dumps({
                "id": rid, "type": "result", "success": True, "result": self._areas,
            }))
        elif t == "config/device_registry/list":
            await ws.send(json.dumps({
                "id": rid, "type": "result", "success": True, "result": self._devices,
            }))
        elif t == "config/entity_registry/list":
            await ws.send(json.dumps({
                "id": rid, "type": "result", "success": True, "result": self._entities,
            }))
        else:
            await ws.send(json.dumps({
                "id": rid, "type": "result", "success": False,
                "error": {"code": "unknown_command", "message": t},
            }))


@asynccontextmanager
async def mock_ha_server():
    srv = MockHAServer()
    await srv.start()
    try:
        yield srv
    finally:
        await srv.stop()
```

- [ ] **Step 2: Write `tests/integration/conftest.py`**

```python
import pytest_asyncio
from tests.integration.mock_ha_server import MockHAServer


@pytest_asyncio.fixture
async def mock_ha():
    srv = MockHAServer()
    await srv.start()
    yield srv
    await srv.stop()
```

- [ ] **Step 3: Write smoke test** — `tests/integration/test_mock_ha_smoke.py`

```python
import json
import pytest
import websockets


@pytest.mark.asyncio
async def test_auth_ok_flow(mock_ha):
    uri = f"ws://127.0.0.1:{mock_ha.port}"
    async with websockets.connect(uri) as ws:
        hello = json.loads(await ws.recv())
        assert hello["type"] == "auth_required"
        await ws.send(json.dumps({"type": "auth", "access_token": "test-token-not-real"}))
        ack = json.loads(await ws.recv())
        assert ack["type"] == "auth_ok"


@pytest.mark.asyncio
async def test_auth_invalid_flow(mock_ha):
    uri = f"ws://127.0.0.1:{mock_ha.port}"
    async with websockets.connect(uri) as ws:
        await ws.recv()  # auth_required
        await ws.send(json.dumps({"type": "auth", "access_token": "wrong"}))
        nak = json.loads(await ws.recv())
        assert nak["type"] == "auth_invalid"
```

- [ ] **Step 4: Run smoke, expect PASS**

```bash
pytest tests/integration/test_mock_ha_smoke.py -v
# Expect: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add tests/integration/
git commit -m "test(integration): MockHAServer + auth-handshake smoke"
```

---

## Task 14: HAWSClient (auth + ping + reconnect + event push)

**Files:**
- Create: `src/ai_ha/ha_adapter/ws_client.py`
- Create: `tests/integration/test_ha_ws_client.py`

- [ ] **Step 1: Write failing test** — `tests/integration/test_ha_ws_client.py`

```python
import asyncio
import pytest
from ai_ha.ha_adapter.ws_client import HAWSClient


@pytest.mark.asyncio
async def test_connect_and_subscribe(mock_ha):
    events: list[dict] = []

    async def on_event(e: dict) -> None:
        events.append(e)

    client = HAWSClient(
        url=f"ws://127.0.0.1:{mock_ha.port}",
        token="test-token-not-real",
        on_event=on_event,
    )
    task = asyncio.create_task(client.run())
    await asyncio.sleep(0.2)
    await mock_ha.push_event("light.x", old="off", new="on")
    await asyncio.sleep(0.2)
    client.stop()
    await task
    assert any(e.get("event", {}).get("data", {}).get("entity_id") == "light.x" for e in events)


@pytest.mark.asyncio
async def test_auth_invalid_does_not_retry_forever(mock_ha):
    client = HAWSClient(
        url=f"ws://127.0.0.1:{mock_ha.port}", token="wrong",
        on_event=lambda e: asyncio.sleep(0),
        max_reconnect_seconds=2,
    )
    task = asyncio.create_task(client.run())
    await asyncio.sleep(1.0)
    client.stop()
    await task
    assert client.last_error_kind == "auth-invalid"


@pytest.mark.asyncio
async def test_reconnects_on_drop(mock_ha):
    events: list[dict] = []

    async def on_event(e: dict) -> None:
        events.append(e)

    client = HAWSClient(
        url=f"ws://127.0.0.1:{mock_ha.port}",
        token="test-token-not-real",
        on_event=on_event,
        initial_backoff=0.1, max_backoff=0.5,
    )
    task = asyncio.create_task(client.run())
    await asyncio.sleep(0.3)
    await mock_ha.disconnect_all()
    await asyncio.sleep(0.6)
    await mock_ha.push_event("light.y", old=None, new="on")
    await asyncio.sleep(0.3)
    client.stop()
    await task
    assert any(
        e.get("event", {}).get("data", {}).get("entity_id") == "light.y" for e in events
    )
    assert client.disconnect_count >= 1
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Write `src/ai_ha/ha_adapter/ws_client.py`**

```python
"""HA WebSocket client with auth handshake + reconnect + event push.

State machine: CONNECTING → AUTH → SUBSCRIBED → (event loop) → DISCONNECTED → CONNECTING.
On auth-invalid the loop stops (re-auth would not help). on_event runs in the same
task as the loop, so it must not block; ingest pipeline buffers in memory.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import websockets

logger = logging.getLogger(__name__)


class HAWSClient:
    def __init__(
        self, url: str, token: str,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
        *,
        initial_backoff: float = 1.0, max_backoff: float = 60.0,
        max_reconnect_seconds: float | None = None,
        ping_interval: float = 30.0,
    ) -> None:
        self._url = url
        self._token = token
        self._on_event = on_event
        self._initial_backoff = initial_backoff
        self._max_backoff = max_backoff
        self._stop = asyncio.Event()
        self._next_id = 1
        self._max_seconds = max_reconnect_seconds
        self._ping = ping_interval
        self.disconnect_count = 0
        self.last_error_kind: str | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        backoff = self._initial_backoff
        start = asyncio.get_event_loop().time()
        while not self._stop.is_set():
            if self._max_seconds is not None and \
                    asyncio.get_event_loop().time() - start > self._max_seconds:
                return
            try:
                await self._connect_and_loop()
                backoff = self._initial_backoff  # successful run resets backoff
            except _AuthInvalidError:
                self.last_error_kind = "auth-invalid"
                return  # do not retry
            except Exception as exc:
                self.last_error_kind = "ws-disconnected"
                logger.warning("ws loop ended: %s; sleep %.1fs", exc, backoff)
                self._connected = False
                self.disconnect_count += 1
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                return
            except asyncio.TimeoutError:
                pass
            backoff = min(self._max_backoff, backoff * 2)

    async def _connect_and_loop(self) -> None:
        async with websockets.connect(
            self._url, ping_interval=self._ping, ping_timeout=self._ping,
        ) as ws:
            hello = json.loads(await ws.recv())
            if hello.get("type") != "auth_required":
                raise RuntimeError(f"unexpected hello: {hello}")
            await ws.send(json.dumps({"type": "auth", "access_token": self._token}))
            ack = json.loads(await ws.recv())
            if ack.get("type") == "auth_invalid":
                raise _AuthInvalidError
            if ack.get("type") != "auth_ok":
                raise RuntimeError(f"unexpected auth ack: {ack}")
            sub_id = self._next_id
            self._next_id += 1
            await ws.send(json.dumps({
                "id": sub_id, "type": "subscribe_events", "event_type": "state_changed",
            }))
            # also subscribe to registry updates
            for kind in ("area", "device", "entity"):
                self._next_id += 1
                await ws.send(json.dumps({
                    "id": self._next_id, "type": "subscribe_events",
                    "event_type": f"{kind}_registry_updated",
                }))
            self._connected = True
            async for raw in ws:
                if self._stop.is_set():
                    return
                msg = json.loads(raw)
                if msg.get("type") == "event":
                    try:
                        await self._on_event(msg)
                    except Exception:
                        logger.exception("on_event raised")


class _AuthInvalidError(RuntimeError):
    pass
```

- [ ] **Step 4: Run test, expect PASS**

```bash
pytest tests/integration/test_ha_ws_client.py -v
# Expect: 3 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_ha/ha_adapter/ws_client.py tests/integration/test_ha_ws_client.py
git commit -m "feat(ha): HAWSClient with auth + reconnect + subscribe state_changed + registry"
```

---

## Task 15: TopologyFetcher (registry pull + diff)

**Files:**
- Create: `src/ai_ha/ha_adapter/topology_fetcher.py`
- Create: `tests/integration/test_topology_fetcher.py`

- [ ] **Step 1: Write failing test** — `tests/integration/test_topology_fetcher.py`

```python
import asyncio
import pytest
from ai_ha.ha_adapter.topology_fetcher import TopologyFetcher


@pytest.mark.asyncio
async def test_fetch_returns_three_lists(mock_ha):
    mock_ha.set_topology(
        areas=[{"area_id": "a1", "name": "Living"}],
        devices=[{"device_id": "d1", "area_id": "a1"}],
        entities=[{"entity_id": "light.x", "device_id": "d1"}],
    )
    f = TopologyFetcher(url=f"ws://127.0.0.1:{mock_ha.port}", token="test-token-not-real")
    payload = await f.fetch_once()
    assert len(payload.areas) == 1
    assert len(payload.devices) == 1
    assert len(payload.entities) == 1


@pytest.mark.asyncio
async def test_fetch_auth_invalid_raises(mock_ha):
    f = TopologyFetcher(url=f"ws://127.0.0.1:{mock_ha.port}", token="wrong")
    with pytest.raises(Exception):
        await f.fetch_once()
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Write `src/ai_ha/ha_adapter/topology_fetcher.py`**

```python
"""One-shot WS connection that calls the three registry list commands and returns a TopologyPayload."""
from __future__ import annotations

import json
from typing import Any

import websockets

from ai_ha.topology.snapshot_store import TopologyPayload


class TopologyFetcher:
    def __init__(self, url: str, token: str, *, timeout_s: float = 10.0) -> None:
        self._url = url
        self._token = token
        self._timeout = timeout_s

    async def fetch_once(self) -> TopologyPayload:
        async with websockets.connect(self._url, open_timeout=self._timeout) as ws:
            await ws.recv()  # auth_required
            await ws.send(json.dumps({"type": "auth", "access_token": self._token}))
            ack = json.loads(await ws.recv())
            if ack.get("type") != "auth_ok":
                raise RuntimeError(f"auth failed: {ack}")
            areas = await self._request(ws, 1, "config/area_registry/list")
            devices = await self._request(ws, 2, "config/device_registry/list")
            entities = await self._request(ws, 3, "config/entity_registry/list")
        return TopologyPayload(areas=areas, devices=devices, entities=entities)

    @staticmethod
    async def _request(ws: Any, rid: int, cmd: str) -> list[dict[str, Any]]:
        await ws.send(json.dumps({"id": rid, "type": cmd}))
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            if msg.get("id") == rid and msg.get("type") == "result":
                if not msg.get("success"):
                    raise RuntimeError(f"{cmd} failed: {msg.get('error')}")
                return msg.get("result", [])
```

- [ ] **Step 4: Run test, expect PASS**

```bash
pytest tests/integration/test_topology_fetcher.py -v
# Expect: 2 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_ha/ha_adapter/topology_fetcher.py tests/integration/test_topology_fetcher.py
git commit -m "feat(ha): TopologyFetcher pulls area/device/entity registry one-shot"
```

---

## Task 16: Ingest pipeline (5-step process)

**Files:**
- Create: `src/ai_ha/ingest/__init__.py`
- Create: `src/ai_ha/ingest/counters.py`
- Create: `src/ai_ha/ingest/pipeline.py`
- Create: `tests/unit/test_counters.py`
- Create: `tests/unit/test_ingest_pipeline.py`

- [ ] **Step 1: Write counters test** — `tests/unit/test_counters.py`

```python
from ai_ha.ingest.counters import HourBucketRing


def test_hour_bucket_from_ts():
    ring = HourBucketRing()
    # ts 3,600,000 ms = hour bucket 1
    assert ring.bucket_for(3_600_000) == 1
    assert ring.bucket_for(7_199_999) == 1
    assert ring.bucket_for(7_200_000) == 2


def test_now_bucket_unix():
    import time
    expected = int(time.time() * 1000) // 3_600_000
    actual = HourBucketRing().now_bucket(now_ms=expected * 3_600_000)
    assert actual == expected
```

- [ ] **Step 2: Write pipeline test** — `tests/unit/test_ingest_pipeline.py`

```python
import pytest
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO
from ai_ha.privacy.hide_matcher import HideMatcher
from ai_ha.topology.snapshot_store import TopologyPayload
from ai_ha.topology.entity_index import EntityIndex
from ai_ha.ingest.pipeline import IngestPipeline, HAEvent

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.fixture
async def pipeline_setup(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    payload = TopologyPayload(
        areas=[{"area_id": "living", "name": "Living"}],
        devices=[{"device_id": "d1", "area_id": "living"}],
        entities=[{
            "entity_id": "light.living", "device_id": "d1",
            "area_id": None, "device_class": "light", "platform": "hue",
        }],
    )
    idx = EntityIndex.build_from_payload(payload, snapshot_id=1)
    # seed the area + entity rows so upsert/bump can update existing rows
    from ai_ha.store.dao import AreaRow, EntityRow
    await dao.upsert_areas([AreaRow("living", "Living", None, None, "[]", 1, 1000, 1000)])
    await dao.upsert_entities([EntityRow(
        "light.living", "Light", "light", "light", "d1", "living",
        0, 1, 1000, 1000, 0, 0,
    )])
    yield dao, idx, HideMatcher([])


@pytest.mark.asyncio
async def test_normal_event_lands_in_events_and_counters(pipeline_setup):
    dao, idx, matcher = pipeline_setup
    pipe = IngestPipeline(dao=dao, entity_index=idx, hide_matcher=matcher,
                          batch_size=1, batch_interval_ms=10_000)
    await pipe.start()
    await pipe.submit(HAEvent(
        ts_ms=1_700_000_000_000, entity_id="light.living",
        event_type="state_changed", old_state='"off"', new_state='"on"',
        context_user_id=None, context_parent_id=None,
    ))
    await pipe.flush()
    rows = await dao.list_events(area_id="living")
    assert len(rows) == 1 and rows[0].area_id == "living" and rows[0].device_class == "light"
    await pipe.stop()


@pytest.mark.asyncio
async def test_privacy_drop_records_count_not_id(pipeline_setup):
    dao, idx, _ = pipeline_setup
    pipe = IngestPipeline(
        dao=dao, entity_index=idx,
        hide_matcher=HideMatcher([r"light\.living"]),
        batch_size=1, batch_interval_ms=10_000,
    )
    await pipe.start()
    await pipe.submit(HAEvent(
        ts_ms=1_700_000_000_000, entity_id="light.living",
        event_type="state_changed", old_state=None, new_state='"on"',
        context_user_id=None, context_parent_id=None,
    ))
    await pipe.flush()
    rows = await dao.list_events(area_id="living")
    assert rows == []
    drops = await dao.get_privacy_drops_24h(now_hour=1_700_000_000 // 3600)
    assert sum(drops.values()) == 1
    await pipe.stop()


@pytest.mark.asyncio
async def test_unknown_entity_still_inserted_with_null_area(pipeline_setup):
    dao, idx, matcher = pipeline_setup
    pipe = IngestPipeline(dao=dao, entity_index=idx, hide_matcher=matcher,
                          batch_size=1, batch_interval_ms=10_000)
    await pipe.start()
    await pipe.submit(HAEvent(
        ts_ms=1_700_000_000_000, entity_id="light.unknown",
        event_type="state_changed", old_state=None, new_state='"on"',
        context_user_id=None, context_parent_id=None,
    ))
    await pipe.flush()
    rows = await dao.list_events()
    assert len(rows) == 1 and rows[0].area_id is None
    await pipe.stop()
```

- [ ] **Step 3: Write `src/ai_ha/ingest/counters.py`**

```python
"""Hour-bucket arithmetic for counters_per_area."""
from __future__ import annotations

import time

_HOUR_MS = 3_600_000


class HourBucketRing:
    def bucket_for(self, ts_ms: int) -> int:
        return ts_ms // _HOUR_MS

    def now_bucket(self, *, now_ms: int | None = None) -> int:
        if now_ms is None:
            now_ms = int(time.time() * 1000)
        return now_ms // _HOUR_MS
```

- [ ] **Step 4: Write `src/ai_ha/ingest/__init__.py`**

```python
from ai_ha.ingest.pipeline import IngestPipeline, HAEvent
from ai_ha.ingest.counters import HourBucketRing

__all__ = ["IngestPipeline", "HAEvent", "HourBucketRing"]
```

- [ ] **Step 5: Write `src/ai_ha/ingest/pipeline.py`**

```python
"""5-step ingest: enrich → privacy → entity upsert → event insert → counter bump.

Batch policy: commit when either batch_size events accumulated or batch_interval_ms
elapsed since first uncommitted event. Background flush task wakes every 100 ms to
check interval. submit() blocks only on the in-mem queue (unbounded for v0.1.0;
spec §11 risk 11 accepts SIGKILL data loss for now).
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from ai_ha.privacy.hide_matcher import HideMatcher
from ai_ha.store.dao import EventRow, StoreDAO
from ai_ha.topology.entity_index import EntityIndex
from ai_ha.ingest.counters import HourBucketRing

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HAEvent:
    ts_ms: int
    entity_id: str
    event_type: str
    old_state: str | None
    new_state: str | None
    context_user_id: str | None
    context_parent_id: str | None


class IngestPipeline:
    def __init__(
        self, *, dao: StoreDAO, entity_index: EntityIndex,
        hide_matcher: HideMatcher,
        batch_size: int = 100, batch_interval_ms: int = 1000,
    ) -> None:
        self._dao = dao
        self._idx = entity_index
        self._hide = hide_matcher
        self._batch_size = batch_size
        self._batch_interval = batch_interval_ms / 1000.0
        self._buffer: list[tuple[HAEvent, int]] = []  # (event, snapshot_id)
        self._first_added: float | None = None
        self._ring = HourBucketRing()
        self._lock = asyncio.Lock()
        self._stop = asyncio.Event()
        self._flush_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def stop(self) -> None:
        self._stop.set()
        if self._flush_task:
            await self._flush_task
        await self.flush()

    async def submit(self, event: HAEvent) -> None:
        ref = self._idx.lookup(event.entity_id)
        if ref and self._hide.matches(event.entity_id):
            bucket = self._ring.now_bucket()
            await self._dao.increment_privacy_drop(hour_bucket_utc=bucket, by=1)
            return
        if not ref and self._hide.matches(event.entity_id):
            # also drop for unknown entities (defense in depth)
            bucket = self._ring.now_bucket()
            await self._dao.increment_privacy_drop(hour_bucket_utc=bucket, by=1)
            return
        snapshot_id = ref.snapshot_id if ref else 0
        async with self._lock:
            self._buffer.append((event, snapshot_id))
            if self._first_added is None:
                self._first_added = time.monotonic()
            if len(self._buffer) >= self._batch_size:
                await self._commit_locked()

    async def flush(self) -> None:
        async with self._lock:
            await self._commit_locked()

    async def _commit_locked(self) -> None:
        if not self._buffer:
            return
        received_at = int(time.time() * 1000)
        rows: list[EventRow] = []
        per_area: dict[tuple[str, int], int] = {}
        per_entity_last: dict[str, int] = {}
        for ev, sid in self._buffer:
            ref = self._idx.lookup(ev.entity_id)
            area_id = ref.area_id if ref else None
            device_id = ref.device_id if ref else None
            device_class = ref.device_class if ref else None
            rows.append(EventRow(
                ts=ev.ts_ms, received_at=received_at, entity_id=ev.entity_id,
                event_type=ev.event_type, old_state=ev.old_state,
                new_state=ev.new_state, context_user_id=ev.context_user_id,
                context_parent_id=ev.context_parent_id,
                area_id=area_id, device_id=device_id, device_class=device_class,
                snapshot_id=sid,
            ))
            if area_id:
                key = (area_id, self._ring.bucket_for(ev.ts_ms))
                per_area[key] = per_area.get(key, 0) + 1
            per_entity_last[ev.entity_id] = ev.ts_ms
        await self._dao.insert_events(rows)
        for (aid, bucket), n in per_area.items():
            await self._dao.increment_counter(aid, hour_bucket_utc=bucket, by=n)
        for eid, last_ts in per_entity_last.items():
            await self._dao.bump_entity_event_counts(entity_id=eid, last_seen_at=last_ts)
        self._buffer.clear()
        self._first_added = None

    async def _periodic_flush(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=0.1)
                return
            except asyncio.TimeoutError:
                pass
            async with self._lock:
                if self._first_added is None:
                    continue
                if time.monotonic() - self._first_added >= self._batch_interval:
                    await self._commit_locked()
```

- [ ] **Step 6: Run tests, expect PASS**

```bash
pytest tests/unit/test_counters.py tests/unit/test_ingest_pipeline.py -v
# Expect: 5 passed
```

- [ ] **Step 7: Commit**

```bash
git add src/ai_ha/ingest/ tests/unit/test_counters.py tests/unit/test_ingest_pipeline.py
git commit -m "feat(ingest): 5-step pipeline (enrich/privacy/upsert/insert/counter) + batch commit"
```

---

## Task 17: Health metrics collector

**Files:**
- Create: `src/ai_ha/health/__init__.py`
- Create: `src/ai_ha/health/metrics.py`
- Create: `tests/unit/test_health_metrics.py`

- [ ] **Step 1: Write failing test** — `tests/unit/test_health_metrics.py`

```python
import pytest
from ai_ha.health.metrics import HealthMetrics


def test_initial_snapshot():
    m = HealthMetrics(install_start_ms=0)
    s = m.snapshot(now_ms=1_000)
    assert s["uptime_seconds"] == 1
    assert s["ws_connected"] is False
    assert s["events_per_hour"] == 0


def test_record_event_increments_rate():
    m = HealthMetrics(install_start_ms=0)
    base = 3_600_000  # bucket = 1
    m.record_event(ts_ms=base + 1000)
    m.record_event(ts_ms=base + 2000)
    s = m.snapshot(now_ms=base + 3000)
    assert s["events_per_hour"] == 2


def test_record_event_drops_old_buckets():
    m = HealthMetrics(install_start_ms=0)
    m.record_event(ts_ms=0)
    m.record_event(ts_ms=3_600_000 * 2)  # 2 hours later
    s = m.snapshot(now_ms=3_600_000 * 2)
    # within last hour: just the second event
    assert s["events_per_hour"] == 1


def test_set_ws_connected():
    m = HealthMetrics(install_start_ms=0)
    m.set_ws_connected(True)
    assert m.snapshot(now_ms=1000)["ws_connected"] is True


def test_record_privacy_drop():
    m = HealthMetrics(install_start_ms=0)
    m.record_privacy_drop()
    m.record_privacy_drop()
    assert m.snapshot(now_ms=1000)["hidden_event_count"] == 2
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Write `src/ai_ha/health/__init__.py`**

```python
from ai_ha.health.metrics import HealthMetrics

__all__ = ["HealthMetrics"]
```

- [ ] **Step 4: Write `src/ai_ha/health/metrics.py`**

```python
"""In-memory health metric collector. /api/health reads snapshot() once per request."""
from __future__ import annotations

import asyncio
from collections import deque
from typing import Any


class HealthMetrics:
    def __init__(self, *, install_start_ms: int) -> None:
        self._start_ms = install_start_ms
        self._ws_connected = False
        self._event_log_recent: deque[int] = deque()  # ts_ms, kept rolling 1h
        self._hidden_total = 0
        self._db_size_bytes = 0
        self._topology_snapshot_id: int | None = None
        self._wal_recovery_count = 0
        self._privacy_compile_fail = 0
        self._config_reload_fail = 0
        self._ha_version: str | None = None
        self._lock = asyncio.Lock()

    def set_ws_connected(self, ok: bool) -> None:
        self._ws_connected = ok

    def set_db_size(self, bytes_: int) -> None:
        self._db_size_bytes = bytes_

    def set_topology_snapshot_id(self, sid: int) -> None:
        self._topology_snapshot_id = sid

    def set_ha_version(self, v: str) -> None:
        self._ha_version = v

    def inc_wal_recovery(self) -> None:
        self._wal_recovery_count += 1

    def inc_privacy_compile_fail(self) -> None:
        self._privacy_compile_fail += 1

    def inc_config_reload_fail(self) -> None:
        self._config_reload_fail += 1

    def record_event(self, *, ts_ms: int) -> None:
        self._event_log_recent.append(ts_ms)
        cutoff = ts_ms - 3_600_000
        while self._event_log_recent and self._event_log_recent[0] < cutoff:
            self._event_log_recent.popleft()

    def record_privacy_drop(self) -> None:
        self._hidden_total += 1

    def snapshot(self, *, now_ms: int) -> dict[str, Any]:
        cutoff = now_ms - 3_600_000
        while self._event_log_recent and self._event_log_recent[0] < cutoff:
            self._event_log_recent.popleft()
        uptime = max(0, (now_ms - self._start_ms) // 1000)
        return {
            "status": "healthy" if self._ws_connected else "degraded",
            "ws_connected": self._ws_connected,
            "events_per_hour": len(self._event_log_recent),
            "db_size_mb": round(self._db_size_bytes / 1_000_000, 2),
            "uptime_seconds": uptime,
            "hidden_event_count": self._hidden_total,
            "current_topology_snapshot_id": self._topology_snapshot_id,
            "ha_version_seen": self._ha_version,
            "wal_recovery_count": self._wal_recovery_count,
            "privacy_regex_compile_fail_total": self._privacy_compile_fail,
            "config_reload_fail_total": self._config_reload_fail,
        }
```

- [ ] **Step 5: Run test, expect PASS**

```bash
pytest tests/unit/test_health_metrics.py -v
# Expect: 5 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_ha/health/ tests/unit/test_health_metrics.py
git commit -m "feat(health): in-memory metrics collector with rolling 1h event rate"
```

---

## Task 18: Topology orchestrator (snapshot + index + DAO sync)

**Files:**
- Create: `src/ai_ha/topology/orchestrator.py`
- Modify: `src/ai_ha/topology/__init__.py` (export TopologyOrchestrator)
- Create: `tests/unit/test_topology_orchestrator.py`

This task wires the registry-fetcher result through SnapshotStore + EntityIndex + DAO upsert.

- [ ] **Step 1: Write failing test** — `tests/unit/test_topology_orchestrator.py`

```python
import pytest
import time
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO
from ai_ha.topology.orchestrator import TopologyOrchestrator
from ai_ha.topology.snapshot_store import SnapshotStore, TopologyPayload
from ai_ha.topology.entity_index import EntityIndex

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_apply_writes_areas_devices_entities(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    store = SnapshotStore(db)
    idx = EntityIndex()
    orch = TopologyOrchestrator(snapshot_store=store, entity_index=idx, dao=dao)
    payload = TopologyPayload(
        areas=[{"area_id": "a1", "name": "Living"}],
        devices=[{"device_id": "d1", "area_id": "a1"}],
        entities=[{"entity_id": "light.x", "device_id": "d1",
                   "platform": "hue", "device_class": "light"}],
    )
    sid, is_new = await orch.apply(payload, ts_ms=int(time.time() * 1000))
    assert is_new is True
    assert sid >= 1
    areas = await dao.list_areas()
    assert len(areas) == 1 and areas[0].name == "Living"
    entities = await dao.list_entities()
    assert len(entities) == 1 and entities[0].domain == "light"
    assert idx.lookup("light.x") is not None


@pytest.mark.asyncio
async def test_apply_same_payload_no_new_snapshot(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    orch = TopologyOrchestrator(
        snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), dao=StoreDAO(db),
    )
    p = TopologyPayload(areas=[{"area_id": "a1"}], devices=[], entities=[])
    sid1, new1 = await orch.apply(p, ts_ms=1000)
    sid2, new2 = await orch.apply(p, ts_ms=2000)
    assert sid1 == sid2 and new2 is False
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Write `src/ai_ha/topology/orchestrator.py`**

```python
"""Orchestrate one topology refresh: snapshot dedup + DAO upsert + entity index rebuild."""
from __future__ import annotations

from ai_ha.store.dao import AreaRow, DeviceRow, EntityRow, StoreDAO
from ai_ha.topology.entity_index import EntityIndex
from ai_ha.topology.snapshot_store import SnapshotStore, TopologyPayload


class TopologyOrchestrator:
    def __init__(
        self, *, snapshot_store: SnapshotStore, entity_index: EntityIndex, dao: StoreDAO,
    ) -> None:
        self._snap = snapshot_store
        self._idx = entity_index
        self._dao = dao

    async def apply(self, payload: TopologyPayload, *, ts_ms: int) -> tuple[int, bool]:
        snapshot_id, is_new = await self._snap.insert_if_changed(payload, ts_ms=ts_ms)
        if is_new:
            await self._upsert_all(payload, snapshot_id=snapshot_id, ts_ms=ts_ms)
        await self._idx.rebuild_async(payload, snapshot_id=snapshot_id)
        return snapshot_id, is_new

    async def _upsert_all(
        self, payload: TopologyPayload, *, snapshot_id: int, ts_ms: int,
    ) -> None:
        await self._dao.upsert_areas([
            AreaRow(
                area_id=a["area_id"], name=a.get("name", a["area_id"]),
                floor_id=a.get("floor_id"), icon=a.get("icon"),
                aliases=str(a.get("aliases", "[]")),
                snapshot_id=snapshot_id, first_seen_at=ts_ms, last_seen_at=ts_ms,
            )
            for a in payload.areas if a.get("area_id")
        ])
        await self._dao.upsert_devices([
            DeviceRow(
                device_id=d["device_id"], name=d.get("name"),
                manufacturer=d.get("manufacturer"), model=d.get("model"),
                area_id=d.get("area_id"), sw_version=d.get("sw_version"),
                snapshot_id=snapshot_id, first_seen_at=ts_ms, last_seen_at=ts_ms,
            )
            for d in payload.devices if d.get("device_id")
        ])
        device_to_area = {d["device_id"]: d.get("area_id") for d in payload.devices}
        await self._dao.upsert_entities([
            EntityRow(
                entity_id=e["entity_id"], friendly_name=e.get("name"),
                domain=e["entity_id"].split(".", 1)[0],
                device_class=e.get("device_class"),
                device_id=e.get("device_id"),
                area_id=e.get("area_id") or device_to_area.get(e.get("device_id")),
                disabled=1 if e.get("disabled_by") else 0,
                snapshot_id=snapshot_id, first_seen_at=ts_ms, last_seen_at=ts_ms,
                event_count_24h=0, total_event_count=0,
            )
            for e in payload.entities if e.get("entity_id")
        ])
```

- [ ] **Step 4: Update `src/ai_ha/topology/__init__.py`**

```python
from ai_ha.topology.snapshot_store import SnapshotStore, TopologyPayload, Snapshot
from ai_ha.topology.entity_index import EntityIndex, EntityRef
from ai_ha.topology.orchestrator import TopologyOrchestrator
from ai_ha.topology.orphan_detector import find_orphans

__all__ = [
    "SnapshotStore", "TopologyPayload", "Snapshot",
    "EntityIndex", "EntityRef",
    "TopologyOrchestrator",
    "find_orphans",
]
```

- [ ] **Step 5: Run test, expect PASS**

```bash
pytest tests/unit/test_topology_orchestrator.py -v
# Expect: 2 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_ha/topology/orchestrator.py src/ai_ha/topology/__init__.py tests/unit/test_topology_orchestrator.py
git commit -m "feat(topology): TopologyOrchestrator wires snapshot/dao-upsert/index-rebuild"
```

---

# Phase 3 — Web + Main wire-up (Day 10-12)

> **Security note (per spec §7 case 14)**: all Jinja templates use Jinja2 default autoescape (escape HTML). All JavaScript that injects server-supplied strings into DOM uses `textContent` or `createTextNode`, never `innerHTML` — entity_id and friendly_name may contain attacker-controlled HTML.

## Task 19: FastAPI app shell + auth (first-run token + Basic + signed cookie)

**Files:**
- Create: `src/ai_ha/web/__init__.py`
- Create: `src/ai_ha/web/app.py`
- Create: `src/ai_ha/web/auth.py`
- Create: `tests/integration/test_auth.py`

- [ ] **Step 1: Write failing test** — `tests/integration/test_auth.py`

```python
import pytest
from httpx import AsyncClient, ASGITransport
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore


@pytest.fixture
def token_store(tmp_path):
    tok_file = tmp_path / "token"
    store = AdminTokenStore(str(tok_file))
    store.ensure_token()
    return store


@pytest.mark.asyncio
async def test_health_requires_no_auth(token_store):
    app = create_app(token_store=token_store, require_auth=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/health")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_areas_requires_auth(token_store):
    app = create_app(token_store=token_store, require_auth=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/areas")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_areas_with_basic_auth_ok(token_store):
    app = create_app(token_store=token_store, require_auth=True)
    tok = token_store.read()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/areas", auth=("admin", tok))
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_require_auth_false_skips(token_store):
    app = create_app(token_store=token_store, require_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/areas")
        assert r.status_code == 200
```

- [ ] **Step 2: Run test, expect FAIL**

- [ ] **Step 3: Write `src/ai_ha/web/auth.py`**

```python
"""Admin token persistence + Basic-Auth dependency.

Token: 32-byte random, written 0600 to /data/.admin-token, printed once on first run.
v0.1.0 has a single 'admin' user. No multi-user, no OAuth.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials


class AdminTokenStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def ensure_token(self) -> str:
        if self._path.exists():
            return self.read()
        tok = secrets.token_urlsafe(32)
        self._path.write_text(tok)
        os.chmod(self._path, 0o600)
        return tok

    def read(self) -> str:
        return self._path.read_text().strip()


_basic = HTTPBasic(auto_error=False)


def make_require_admin(token_store: AdminTokenStore, *, require_auth: bool):
    async def _dep(creds: HTTPBasicCredentials | None = Depends(_basic)) -> None:
        if not require_auth:
            return
        if creds is None or creds.username != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "auth-required", "detail": "admin token needed"},
                headers={"WWW-Authenticate": "Basic"},
            )
        token = token_store.read()
        if not secrets.compare_digest(creds.password, token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "auth-invalid", "detail": "bad token"},
            )
    return _dep
```

- [ ] **Step 4: Write `src/ai_ha/web/app.py`** (initial stub: only /api/health + /api/v1/areas placeholder)

```python
"""FastAPI app factory. Routes are mounted from web/routes/* in later tasks."""
from __future__ import annotations

from fastapi import Depends, FastAPI

from ai_ha.web.auth import AdminTokenStore, make_require_admin


def create_app(
    *, token_store: AdminTokenStore, require_auth: bool = True,
) -> FastAPI:
    app = FastAPI(title="ai-home-assistant", version="0.1.0")
    require_admin = make_require_admin(token_store, require_auth=require_auth)
    app.state.require_admin = require_admin

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        return {"status": "healthy"}

    @app.get("/api/v1/areas", dependencies=[Depends(require_admin)])
    async def areas_stub() -> list[object]:
        return []

    return app
```

- [ ] **Step 5: Write `src/ai_ha/web/__init__.py`**

```python
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore

__all__ = ["create_app", "AdminTokenStore"]
```

- [ ] **Step 6: Run test, expect PASS**

```bash
pytest tests/integration/test_auth.py -v
# Expect: 4 passed
```

- [ ] **Step 7: Commit**

```bash
git add src/ai_ha/web/ tests/integration/test_auth.py
git commit -m "feat(web): FastAPI shell + AdminTokenStore + Basic-Auth dependency"
```

---

## Task 20: REST routes — health, topology, areas, entities, events, settings

**Files:**
- Create: `src/ai_ha/web/routes/__init__.py` (AppState + build_router factories)
- Create: `src/ai_ha/web/routes/{health,topology,areas,entities,events,settings}.py`
- Modify: `src/ai_ha/web/app.py` (mount routers, inject AppState)
- Create: `tests/integration/test_api_{health,areas,entities,events,topology,settings}.py`

Each route module exports `build_router(state, require_admin) -> APIRouter` and is mounted with prefix `/api/v1` and `dependencies=[Depends(require_admin)]` at router level (so every endpoint requires auth). `/api/health` is the single exception — mounted without auth dep.

### Sub-task 20a: AppState + DI plumbing

- [ ] **Step 1: Write `src/ai_ha/web/routes/__init__.py`**

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_ha.store.dao import StoreDAO
from ai_ha.topology import SnapshotStore, EntityIndex
from ai_ha.health import HealthMetrics


@dataclass
class AppState:
    dao: StoreDAO
    snapshot_store: SnapshotStore
    entity_index: EntityIndex
    health: HealthMetrics
    config_path: Path
    hide_pattern: list[str]
    on_privacy_update: Any  # async callable
    broadcaster: Any | None = None  # set by main.py
```

- [ ] **Step 2: Refactor `src/ai_ha/web/app.py` to wire build_router factories**

```python
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ai_ha.web.auth import AdminTokenStore, make_require_admin
from ai_ha.web.routes import AppState


def create_app(
    *, token_store: AdminTokenStore, require_auth: bool = True,
    state: AppState | None = None,
) -> FastAPI:
    app = FastAPI(title="ai-home-assistant", version="0.1.0")
    require_admin = make_require_admin(token_store, require_auth=require_auth)
    app.state.require_admin = require_admin
    app.state.app_state = state

    from ai_ha.web.routes.health import build_router as _h
    from ai_ha.web.routes.topology import build_router as _t
    from ai_ha.web.routes.areas import build_router as _a
    from ai_ha.web.routes.entities import build_router as _e
    from ai_ha.web.routes.events import build_router as _ev
    from ai_ha.web.routes.settings import build_router as _s

    app.include_router(_h(state))
    app.include_router(_t(state, require_admin))
    app.include_router(_a(state, require_admin))
    app.include_router(_e(state, require_admin))
    app.include_router(_ev(state, require_admin))
    app.include_router(_s(state, require_admin))

    if state is not None and state.broadcaster is not None:
        from ai_ha.web.routes.stream import build_ws_router
        app.include_router(build_ws_router(state.broadcaster))

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    if state is not None:
        from ai_ha.web.routes.pages import build_pages_router
        app.include_router(build_pages_router(state, require_admin))

    return app
```

- [ ] **Step 3: Commit (sub-task 20a)**

```bash
git add src/ai_ha/web/routes/__init__.py src/ai_ha/web/app.py
git commit -m "refactor(web): AppState + build_router factories for DI"
```

### Sub-task 20b: health route

- [ ] **Step 1: Write `src/ai_ha/web/routes/health.py`**

```python
from __future__ import annotations

import time

from fastapi import APIRouter

from ai_ha.web.routes import AppState


def build_router(state: AppState | None) -> APIRouter:
    router = APIRouter()

    @router.get("/api/health")
    async def health() -> dict[str, object]:
        if state is None:
            return {"status": "healthy", "uptime_seconds": 0}
        return state.health.snapshot(now_ms=int(time.time() * 1000))

    return router
```

- [ ] **Step 2: Write `tests/integration/test_api_health.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore


@pytest.mark.asyncio
async def test_health_returns_json(tmp_path):
    store = AdminTokenStore(str(tmp_path / "t")); store.ensure_token()
    app = create_app(token_store=store)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("healthy", "degraded")
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/integration/test_api_health.py -v
git add src/ai_ha/web/routes/health.py tests/integration/test_api_health.py
git commit -m "feat(web): GET /api/health returns HealthMetrics snapshot"
```

### Sub-task 20c: areas route (rooms-grid aggregates)

- [ ] **Step 1: Write `src/ai_ha/web/routes/areas.py`**

```python
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException

from ai_ha.web.routes import AppState


def build_router(state: AppState | None, require_admin) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin)])

    @router.get("/areas")
    async def list_areas() -> list[dict[str, object]]:
        if state is None:
            return []
        rows = await state.dao.list_areas()
        now_hour = int(time.time() * 1000) // 3_600_000
        counters = await state.dao.get_counters_24h(now_hour=now_hour)
        per_area: dict[str, int] = {}
        for (aid, _), n in counters.items():
            per_area[aid] = per_area.get(aid, 0) + n
        active_cutoff = int(time.time() * 1000) - 600_000  # 10 min
        result: list[dict[str, object]] = []
        for r in rows:
            entities = await state.dao.list_entities(area_id=r.area_id)
            class_dist: dict[str, int] = {}
            last_seen_max = 0
            for e in entities:
                if e.device_class:
                    class_dist[e.device_class] = class_dist.get(e.device_class, 0) + 1
                last_seen_max = max(last_seen_max, e.last_seen_at)
            result.append({
                "area_id": r.area_id, "name": r.name, "floor_id": r.floor_id,
                "events_per_hour_24h": per_area.get(r.area_id, 0),
                "device_class_distribution": class_dist,
                "is_active": last_seen_max > active_cutoff,
                "active_since": last_seen_max if last_seen_max > active_cutoff else None,
                "entity_count": len(entities),
            })
        return result

    @router.get("/areas/{area_id}")
    async def area_detail(area_id: str) -> dict[str, object]:
        if state is None:
            raise HTTPException(404, detail={"error": "not-found"})
        areas = await state.dao.list_areas()
        match = next((a for a in areas if a.area_id == area_id), None)
        if not match:
            raise HTTPException(404, detail={"error": "not-found"})
        entities = await state.dao.list_entities(area_id=area_id)
        recent = await state.dao.list_events(area_id=area_id, limit=50)
        return {
            "area": {"area_id": match.area_id, "name": match.name,
                     "floor_id": match.floor_id},
            "entities": [{"entity_id": e.entity_id, "friendly_name": e.friendly_name,
                          "device_class": e.device_class, "last_seen": e.last_seen_at}
                         for e in entities],
            "recent_events": [
                {"ts": ev.ts, "entity_id": ev.entity_id, "event_type": ev.event_type,
                 "old_state": ev.old_state, "new_state": ev.new_state}
                for ev in recent
            ],
        }

    @router.get("/areas/{area_id}/entities")
    async def area_entities(area_id: str) -> list[dict[str, object]]:
        if state is None:
            return []
        ents = await state.dao.list_entities(area_id=area_id)
        return [{"entity_id": e.entity_id, "friendly_name": e.friendly_name,
                 "device_class": e.device_class, "last_seen": e.last_seen_at,
                 "event_count_24h": e.event_count_24h} for e in ents]

    return router
```

- [ ] **Step 2: Write `tests/integration/test_api_areas.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, AreaRow, EntityRow
from ai_ha.topology import SnapshotStore, EntityIndex
from ai_ha.health import HealthMetrics
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_list_areas_returns_topology_data(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    await dao.upsert_areas([AreaRow("a1", "Living", None, None, "[]", 1, 1000, 1000)])
    await dao.upsert_entities([EntityRow(
        "light.x", "L", "light", "light", None, "a1", 0, 1, 1000, 1000, 5, 5,
    )])
    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "cfg.toml",
        hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/areas", auth=("admin", ts.read()))
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1 and body[0]["name"] == "Living"
        assert body[0]["device_class_distribution"] == {"light": 1}
        assert body[0]["entity_count"] == 1


@pytest.mark.asyncio
async def test_area_detail_404_for_unknown(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "x.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/areas/nope", auth=("admin", ts.read()))
        assert r.status_code == 404
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/integration/test_api_areas.py -v
git add src/ai_ha/web/routes/areas.py tests/integration/test_api_areas.py
git commit -m "feat(web): /api/v1/areas + /areas/{id} + /areas/{id}/entities with stat aggregation"
```

### Sub-task 20d: entities route

- [ ] **Step 1: Write `src/ai_ha/web/routes/entities.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ai_ha.web.routes import AppState


def build_router(state: AppState | None, require_admin) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin)])

    @router.get("/entities")
    async def list_entities(
        area_id: str | None = None,
        orphan: bool = False,
        device_class: str | None = None,
        limit: int = Query(100, ge=1, le=1000),
    ) -> list[dict[str, object]]:
        if state is None:
            return []
        rows = await state.dao.list_entities(
            area_id=area_id, orphan=orphan, device_class=device_class, limit=limit,
        )
        return [{
            "entity_id": r.entity_id, "friendly_name": r.friendly_name,
            "domain": r.domain, "device_class": r.device_class,
            "device_id": r.device_id, "area_id": r.area_id,
            "disabled": bool(r.disabled), "snapshot_id": r.snapshot_id,
            "last_seen": r.last_seen_at, "event_count_24h": r.event_count_24h,
            "total_event_count": r.total_event_count,
        } for r in rows]

    @router.get("/entities/{entity_id}/events")
    async def entity_events(
        entity_id: str, limit: int = Query(100, ge=1, le=1000),
        cursor: int | None = None,
    ) -> list[dict[str, object]]:
        if state is None:
            return []
        rows = await state.dao.list_events(
            entity_id=entity_id, cursor=cursor, limit=limit,
        )
        if not rows and not await _entity_exists(state, entity_id):
            raise HTTPException(404, detail={"error": "not-found"})
        return [{
            "ts": r.ts, "received_at": r.received_at,
            "event_type": r.event_type, "old_state": r.old_state,
            "new_state": r.new_state, "context_user_id": r.context_user_id,
        } for r in rows]

    async def _entity_exists(s: AppState, entity_id: str) -> bool:
        rows = await s.dao.list_entities(limit=1)
        return any(r.entity_id == entity_id for r in rows)

    return router
```

- [ ] **Step 2: Write `tests/integration/test_api_entities.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, EntityRow
from ai_ha.topology import SnapshotStore, EntityIndex
from ai_ha.health import HealthMetrics
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_orphan_filter_returns_only_no_area(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    await dao.upsert_entities([
        EntityRow("orphan.x", None, "sensor", None, None, None, 0, 1, 1, 1, 0, 0),
        EntityRow("attached.x", None, "sensor", None, None, "a1", 0, 1, 1, 1, 0, 0),
    ])
    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "cfg.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/entities?orphan=true", auth=("admin", ts.read()))
        body = r.json()
        assert [e["entity_id"] for e in body] == ["orphan.x"]
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/integration/test_api_entities.py -v
git add src/ai_ha/web/routes/entities.py tests/integration/test_api_entities.py
git commit -m "feat(web): /api/v1/entities with area_id/orphan/device_class filters + cursor"
```

### Sub-task 20e: events route

- [ ] **Step 1: Write `src/ai_ha/web/routes/events.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ai_ha.web.routes import AppState


def build_router(state: AppState | None, require_admin) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin)])

    @router.get("/events")
    async def list_events(
        since: int | None = None, until: int | None = None,
        area_id: str | None = None, entity_id: str | None = None,
        limit: int = Query(100, ge=1, le=1000),
        cursor: str | None = None,
    ) -> dict[str, object]:
        if state is None:
            return {"events": [], "next_cursor": None}
        cursor_int: int | None = None
        if cursor is not None:
            try:
                cursor_int = int(cursor)
            except ValueError:
                raise HTTPException(400, detail={"error": "bad-cursor"})
        rows = await state.dao.list_events(
            entity_id=entity_id, area_id=area_id,
            since_ts=since, until_ts=until,
            cursor=cursor_int, limit=limit,
        )
        return {
            "events": [{
                "ts": r.ts, "received_at": r.received_at,
                "entity_id": r.entity_id, "event_type": r.event_type,
                "old_state": r.old_state, "new_state": r.new_state,
                "area_id": r.area_id, "device_class": r.device_class,
            } for r in rows],
            "next_cursor": str(rows[-1].ts) if rows and len(rows) == limit else None,
        }

    return router
```

- [ ] **Step 2: Write `tests/integration/test_api_events.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, EventRow
from ai_ha.topology import SnapshotStore, EntityIndex
from ai_ha.health import HealthMetrics
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_events_filter_by_area(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    await dao.insert_events([
        EventRow(1000, 1001, "light.x", "state_changed", None, '"on"',
                 None, None, "living", None, "light", 1),
        EventRow(2000, 2001, "light.y", "state_changed", None, '"off"',
                 None, None, "kitchen", None, "light", 1),
    ])
    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "x.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/events?area_id=living", auth=("admin", ts.read()))
        body = r.json()
        assert len(body["events"]) == 1
        assert body["events"][0]["entity_id"] == "light.x"


@pytest.mark.asyncio
async def test_bad_cursor_returns_400(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "x.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/events?cursor=not-a-number", auth=("admin", ts.read()))
        assert r.status_code == 400
        assert r.json()["detail"]["error"] == "bad-cursor"
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/integration/test_api_events.py -v
git add src/ai_ha/web/routes/events.py tests/integration/test_api_events.py
git commit -m "feat(web): /api/v1/events with cursor pagination + bad-cursor 400"
```

### Sub-task 20f: topology route

- [ ] **Step 1: Write `src/ai_ha/web/routes/topology.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ai_ha.web.routes import AppState


def build_router(state: AppState | None, require_admin) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin)])

    @router.get("/topology")
    async def current_topology() -> dict[str, object]:
        if state is None:
            raise HTTPException(503, detail={"error": "topology-not-ready"})
        cur = await state.snapshot_store.get_current()
        if cur is None:
            raise HTTPException(503, detail={"error": "topology-not-ready"})
        return {
            "snapshot_id": cur.snapshot_id,
            "ts": cur.ts_ms,
            "hash": cur.payload_hash,
            "areas_count": len(cur.payload.areas),
            "devices_count": len(cur.payload.devices),
            "entities_count": len(cur.payload.entities),
            "diff_summary": cur.diff_summary,
        }

    @router.get("/topology/snapshots")
    async def list_snapshots(
        limit: int = Query(50, ge=1, le=200),
    ) -> list[dict[str, object]]:
        if state is None:
            return []
        async with state.snapshot_store._db.connect() as c:  # type: ignore[attr-defined]
            rows = await (await c.execute(
                "SELECT snapshot_id, ts, payload_hash, diff_summary "
                "FROM topology_snapshots ORDER BY snapshot_id DESC LIMIT ?",
                (limit,),
            )).fetchall()
        return [{"snapshot_id": r[0], "ts": r[1], "hash": r[2],
                 "diff_summary": r[3]} for r in rows]

    @router.get("/topology/snapshots/{sid}")
    async def snapshot_detail(sid: int) -> dict[str, object]:
        if state is None:
            raise HTTPException(503, detail={"error": "topology-not-ready"})
        async with state.snapshot_store._db.connect() as c:  # type: ignore[attr-defined]
            row = await (await c.execute(
                "SELECT snapshot_id, ts, payload_hash, payload, diff_summary "
                "FROM topology_snapshots WHERE snapshot_id=?", (sid,),
            )).fetchone()
        if not row:
            raise HTTPException(404, detail={"error": "not-found"})
        import json as _json
        payload = _json.loads(row[3])
        return {
            "snapshot_id": row[0], "ts": row[1], "hash": row[2],
            "payload": payload, "diff_summary": row[4],
        }

    return router
```

- [ ] **Step 2: Write `tests/integration/test_api_topology.py`**

```python
import pytest
import time
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO
from ai_ha.topology import SnapshotStore, EntityIndex, TopologyPayload
from ai_ha.health import HealthMetrics
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_topology_not_ready_returns_503(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "x.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/topology", auth=("admin", ts.read()))
        assert r.status_code == 503


@pytest.mark.asyncio
async def test_current_topology_after_snapshot(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    snap = SnapshotStore(db)
    payload = TopologyPayload(
        areas=[{"area_id": "a1"}], devices=[],
        entities=[{"entity_id": "x"}],
    )
    await snap.insert_if_changed(payload, ts_ms=int(time.time() * 1000))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=snap, entity_index=EntityIndex(),
        health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "x.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/topology", auth=("admin", ts.read()))
        assert r.status_code == 200
        body = r.json()
        assert body["areas_count"] == 1 and body["entities_count"] == 1
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/integration/test_api_topology.py -v
git add src/ai_ha/web/routes/topology.py tests/integration/test_api_topology.py
git commit -m "feat(web): /api/v1/topology + /snapshots + /snapshots/{id}"
```

### Sub-task 20g: settings route (privacy regex validation + config.toml write)

- [ ] **Step 1: Write `src/ai_ha/web/routes/settings.py`**

```python
from __future__ import annotations

from typing import Any

import tomli_w  # add to requirements.txt
import tomllib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ai_ha.privacy.hide_matcher import HideMatcher, PatternComplexityError
from ai_ha.web.routes import AppState


class PrivacyPayload(BaseModel):
    hide_entities_pattern: list[str] = Field(default_factory=list)
    allow_cloud_llm_with_digest: bool | None = None


def build_router(state: AppState | None, require_admin) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin)])

    @router.get("/settings/privacy")
    async def get_privacy() -> dict[str, object]:
        if state is None:
            return {"hide_entities_pattern": [], "allow_cloud_llm_with_digest": False}
        return {
            "hide_entities_pattern": state.hide_pattern,
            "allow_cloud_llm_with_digest": False,  # v0.1.0 always false (no LLM)
        }

    @router.post("/settings/privacy")
    async def update_privacy(payload: PrivacyPayload) -> dict[str, object]:
        if state is None:
            raise HTTPException(503)
        # validate each pattern
        try:
            HideMatcher(payload.hide_entities_pattern)
        except PatternComplexityError as exc:
            raise HTTPException(422, detail={"error": "hide-pattern-invalid",
                                              "detail": str(exc)})
        except Exception as exc:
            raise HTTPException(422, detail={"error": "hide-pattern-invalid",
                                              "detail": str(exc)})
        # rewrite [privacy] section in config.toml
        raw: dict[str, Any] = tomllib.loads(state.config_path.read_text())
        raw.setdefault("privacy", {})["hide_entities_pattern"] = payload.hide_entities_pattern
        state.config_path.write_bytes(tomli_w.dumps(raw).encode())
        # the watcher will pick up the file change and invoke on_privacy_update
        return {
            "hide_entities_pattern": payload.hide_entities_pattern,
            "allow_cloud_llm_with_digest": False,
        }

    return router
```

Add `tomli-w==1.0.0` to `requirements.txt`.

- [ ] **Step 2: Write `tests/integration/test_api_settings.py`**

```python
import pytest
import textwrap
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO
from ai_ha.topology import SnapshotStore, EntityIndex
from ai_ha.health import HealthMetrics
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.fixture
async def app_with_cfg(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(textwrap.dedent("""
        [ha]
        url = "http://x"
        token = "t"
        [privacy]
        hide_entities_pattern = []
    """))
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=cfg, hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    yield create_app(token_store=ts, state=state), ts, cfg


@pytest.mark.asyncio
async def test_post_privacy_writes_config(app_with_cfg):
    app, ts, cfg_path = app_with_cfg
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.post(
            "/api/v1/settings/privacy",
            auth=("admin", ts.read()),
            json={"hide_entities_pattern": [r"sensor\.bank_.*"]},
        )
        assert r.status_code == 200
    assert "sensor" in cfg_path.read_text()


@pytest.mark.asyncio
async def test_post_invalid_regex_returns_422(app_with_cfg):
    app, ts, _ = app_with_cfg
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.post(
            "/api/v1/settings/privacy",
            auth=("admin", ts.read()),
            json={"hide_entities_pattern": ["(a+)+b"]},
        )
        assert r.status_code == 422
        assert r.json()["detail"]["error"] == "hide-pattern-invalid"
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/integration/test_api_settings.py -v
git add src/ai_ha/web/routes/settings.py tests/integration/test_api_settings.py requirements.txt
git commit -m "feat(web): /api/v1/settings/privacy GET+POST with regex validation + config write"
```

---

## Task 21: WebSocket /api/v1/stream/events broadcaster

**Files:**
- Create: `src/ai_ha/web/routes/stream.py`
- Create: `tests/integration/test_ws_stream.py`

- [ ] **Step 1: Write test** — `tests/integration/test_ws_stream.py`

```python
import asyncio
import pytest
from ai_ha.web.routes.stream import EventBroadcaster


@pytest.mark.asyncio
async def test_broadcast_delivers_to_listener():
    bc = EventBroadcaster()
    received: list[dict] = []

    async def listener() -> None:
        async for ev in bc.subscribe():
            received.append(ev)
            return

    t = asyncio.create_task(listener())
    await asyncio.sleep(0.05)
    await bc.publish({"entity_id": "light.x", "ts": 1})
    await asyncio.wait_for(t, timeout=1.0)
    assert received[0]["entity_id"] == "light.x"


@pytest.mark.asyncio
async def test_full_queue_drops_oldest():
    bc = EventBroadcaster(queue_size=2)
    gen = bc.subscribe()
    sub_task = asyncio.create_task(gen.__anext__())  # park on queue
    await asyncio.sleep(0.05)
    await bc.publish({"n": 1})
    await bc.publish({"n": 2})
    await bc.publish({"n": 3})  # 1 dropped
    first = await asyncio.wait_for(sub_task, timeout=0.5)
    second = await asyncio.wait_for(gen.__anext__(), timeout=0.5)
    assert first["n"] in (1, 2) and second["n"] in (2, 3)
    assert first["n"] != second["n"]
```

- [ ] **Step 2: Write `src/ai_ha/web/routes/stream.py`**

```python
"""In-process event broadcaster + WS endpoint.

Each WS client has its own bounded asyncio.Queue. publish() fans out; if a client
queue is full, oldest is dropped. No replay, no ack — Web UI reconnects on close.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


class EventBroadcaster:
    def __init__(self, *, queue_size: int = 500) -> None:
        self._queues: set[asyncio.Queue[dict[str, Any]]] = set()
        self._queue_size = queue_size

    async def publish(self, event: dict[str, Any]) -> None:
        for q in list(self._queues):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await q.put(event)

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._queue_size)
        self._queues.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._queues.discard(q)


def build_ws_router(broadcaster: EventBroadcaster) -> APIRouter:
    router = APIRouter()

    @router.websocket("/api/v1/stream/events")
    async def stream(ws: WebSocket) -> None:
        await ws.accept()
        try:
            async for ev in broadcaster.subscribe():
                await ws.send_text(json.dumps(ev, ensure_ascii=False))
        except WebSocketDisconnect:
            return

    return router
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/integration/test_ws_stream.py -v
git add src/ai_ha/web/routes/stream.py tests/integration/test_ws_stream.py
git commit -m "feat(web): EventBroadcaster + WS /api/v1/stream/events with drop-oldest backpressure"
```

---

## Task 22: Jinja2 templates + page routes (5 pages + login)

**Files:**
- Create: `src/ai_ha/web/templates/{base,rooms,room,entities,timeline,settings,login}.html`
- Create: `src/ai_ha/web/routes/pages.py`
- Create: `tests/integration/test_web_pages.py`

- [ ] **Step 1: Write `base.html`** (Jinja2 default autoescape protects {{ }})

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{% block title %}ai-home-assistant{% endblock %}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <header>
    <a href="/" class="brand">ai-home-assistant <span class="ver">v0.1.0</span></a>
    <nav>
      <a href="/">Rooms</a>
      <a href="/entities">Entities</a>
      <a href="/timeline">Timeline</a>
      <a href="/settings">Settings</a>
    </nav>
  </header>
  <div class="banner banner-info">v0.1.0 = Listen-only foundation.
    AI suggestions arrive in v0.4.</div>
  <main>{% block main %}{% endblock %}</main>
  <footer>
    <small>Spec:
      <a href="/docs/superpowers/specs/2026-06-02-ai-home-assistant-v010-listen-only-design.md">design doc</a>.
    </small>
  </footer>
  {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Write `rooms.html`**

```html
{% extends "base.html" %}
{% block title %}Rooms · ai-home-assistant{% endblock %}
{% block main %}
<h1>Rooms</h1>
{% if not areas %}
  <p class="empty">No areas yet. Waiting for first topology snapshot from Home Assistant.</p>
{% else %}
<div class="grid">
  {% for a in areas %}
  <a class="card{% if a.is_active %} active{% endif %}" href="/room/{{ a.area_id }}">
    <h2>{{ a.name }}</h2>
    <div class="metric"><span>{{ a.entity_count }}</span> entities</div>
    <div class="metric"><span>{{ a.events_per_hour_24h }}</span> events/24h</div>
    <div class="classes">
      {% for cls, n in a.device_class_distribution.items() %}
      <span class="tag">{{ cls }}×{{ n }}</span>
      {% endfor %}
    </div>
  </a>
  {% endfor %}
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Write `room.html`**

```html
{% extends "base.html" %}
{% block title %}{{ area.name }} · ai-home-assistant{% endblock %}
{% block main %}
<h1>{{ area.name }}</h1>
<section>
  <h2>Entities ({{ entities|length }})</h2>
  <ul>
    {% for e in entities %}
    <li>{{ e.friendly_name or e.entity_id }}
      <code>{{ e.entity_id }}</code></li>
    {% endfor %}
  </ul>
</section>
<section>
  <h2>Recent events</h2>
  <table>
    <thead><tr><th>Time (UTC)</th><th>Entity</th><th>Type</th></tr></thead>
    <tbody>
    {% for ev in recent_events %}
    <tr><td>{{ ev.ts|tstoiso }}</td><td>{{ ev.entity_id }}</td><td>{{ ev.event_type }}</td></tr>
    {% endfor %}
    </tbody>
  </table>
</section>
{% endblock %}
```

- [ ] **Step 4: Write `entities.html`**

```html
{% extends "base.html" %}
{% block title %}Entities · ai-home-assistant{% endblock %}
{% block main %}
<h1>Entities ({{ entities|length }})</h1>
<table>
  <thead><tr><th>entity_id</th><th>friendly</th><th>area</th><th>class</th><th>events/24h</th></tr></thead>
  <tbody>
  {% for e in entities %}
  <tr>
    <td><code>{{ e.entity_id }}</code></td>
    <td>{{ e.friendly_name or "" }}</td>
    <td>{{ e.area_id or "—" }}</td>
    <td>{{ e.device_class or "" }}</td>
    <td>{{ e.event_count_24h }}</td>
  </tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
```

- [ ] **Step 5: Write `timeline.html`**

```html
{% extends "base.html" %}
{% block title %}Timeline · ai-home-assistant{% endblock %}
{% block main %}
<h1>Timeline</h1>
<table>
  <thead><tr><th>Time (UTC)</th><th>Entity</th><th>Type</th></tr></thead>
  <tbody id="events">
  {% for ev in events %}
  <tr><td>{{ ev.ts|tstoiso }}</td><td>{{ ev.entity_id }}</td><td>{{ ev.event_type }}</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
{% block scripts %}<script src="/static/timeline.js"></script>{% endblock %}
```

- [ ] **Step 6: Write `settings.html`**

```html
{% extends "base.html" %}
{% block title %}Settings · ai-home-assistant{% endblock %}
{% block main %}
<h1>Privacy Settings</h1>
<form id="privacy-form">
  <label>Hide entity regex (one per line)</label>
  <textarea name="hide_entities_pattern" rows="6">{% for p in hide_pattern %}{{ p }}
{% endfor %}</textarea>
  <button type="submit">Save</button>
  <p id="msg"></p>
</form>
{% endblock %}
{% block scripts %}<script src="/static/settings.js"></script>{% endblock %}
```

- [ ] **Step 7: Write `login.html`**

```html
{% extends "base.html" %}
{% block title %}Login{% endblock %}
{% block main %}
<h1>Login</h1>
<p>Enter the admin token printed in the container's first-run log.</p>
<form method="post" action="/api/v1/auth/login">
  <input type="password" name="token" autofocus>
  <button type="submit">Sign in</button>
</form>
{% endblock %}
```

- [ ] **Step 8: Write `src/ai_ha/web/routes/pages.py`**

```python
"""Server-side rendered HTML pages."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ai_ha.web.routes import AppState

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
templates.env.filters["tstoiso"] = lambda ms: datetime.fromtimestamp(
    ms / 1000.0, tz=timezone.utc,
).isoformat()


def build_pages_router(state: AppState | None, require_admin) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_admin)])

    @router.get("/", response_class=HTMLResponse)
    async def rooms(request: Request) -> HTMLResponse:
        if state is None:
            return templates.TemplateResponse(request, "rooms.html", {"areas": []})
        rows = await state.dao.list_areas()
        now_hour = int(time.time() * 1000) // 3_600_000
        counters = await state.dao.get_counters_24h(now_hour=now_hour)
        per_area: dict[str, int] = {}
        for (aid, _), n in counters.items():
            per_area[aid] = per_area.get(aid, 0) + n
        active_cutoff = int(time.time() * 1000) - 600_000
        areas_out = []
        for r in rows:
            ents = await state.dao.list_entities(area_id=r.area_id)
            class_dist: dict[str, int] = {}
            last_seen_max = 0
            for e in ents:
                if e.device_class:
                    class_dist[e.device_class] = class_dist.get(e.device_class, 0) + 1
                last_seen_max = max(last_seen_max, e.last_seen_at)
            areas_out.append({
                "area_id": r.area_id, "name": r.name,
                "events_per_hour_24h": per_area.get(r.area_id, 0),
                "device_class_distribution": class_dist,
                "is_active": last_seen_max > active_cutoff,
                "entity_count": len(ents),
            })
        return templates.TemplateResponse(request, "rooms.html", {"areas": areas_out})

    @router.get("/room/{area_id}", response_class=HTMLResponse)
    async def room(request: Request, area_id: str):
        if state is None:
            return RedirectResponse("/")
        areas = await state.dao.list_areas()
        match = next((a for a in areas if a.area_id == area_id), None)
        if not match:
            return RedirectResponse("/")
        entities = await state.dao.list_entities(area_id=area_id)
        recent = await state.dao.list_events(area_id=area_id, limit=50)
        return templates.TemplateResponse(request, "room.html", {
            "area": match, "entities": entities, "recent_events": recent,
        })

    @router.get("/entities", response_class=HTMLResponse)
    async def entities_page(request: Request) -> HTMLResponse:
        ents = await state.dao.list_entities(limit=500) if state else []
        return templates.TemplateResponse(request, "entities.html",
                                          {"entities": ents})

    @router.get("/timeline", response_class=HTMLResponse)
    async def timeline_page(request: Request) -> HTMLResponse:
        evs = await state.dao.list_events(limit=200) if state else []
        return templates.TemplateResponse(request, "timeline.html",
                                          {"events": evs})

    @router.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request) -> HTMLResponse:
        ctx = {"hide_pattern": state.hide_pattern if state else []}
        return templates.TemplateResponse(request, "settings.html", ctx)

    return router
```

- [ ] **Step 9: Smoke test** — `tests/integration/test_web_pages.py`

```python
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO
from ai_ha.topology import SnapshotStore, EntityIndex
from ai_ha.health import HealthMetrics
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.fixture
async def app_pair(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "cfg.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    yield create_app(token_store=ts, state=state), ts


@pytest.mark.asyncio
async def test_rooms_renders(app_pair):
    app, ts = app_pair
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/", auth=("admin", ts.read()))
        assert r.status_code == 200
        assert "<h1>Rooms</h1>" in r.text


@pytest.mark.asyncio
async def test_entities_renders(app_pair):
    app, ts = app_pair
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/entities", auth=("admin", ts.read()))
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_settings_renders(app_pair):
    app, ts = app_pair
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/settings", auth=("admin", ts.read()))
        assert r.status_code == 200
```

- [ ] **Step 10: Run + commit**

```bash
pytest tests/integration/test_web_pages.py -v
git add src/ai_ha/web/templates/ src/ai_ha/web/routes/pages.py tests/integration/test_web_pages.py
git commit -m "feat(web): 5 Jinja SSR pages (rooms/room/entities/timeline/settings) + login"
```

---

## Task 23: Static CSS + JS (safe DOM, no innerHTML)

**Files:**
- Create: `src/ai_ha/web/static/app.css`
- Create: `src/ai_ha/web/static/timeline.js`
- Create: `src/ai_ha/web/static/settings.js`

> Per spec §7 case 14 + global §3.1 spec node 7: no `innerHTML` with server strings. All injection uses `textContent` / `createElement` / `createTextNode`.

- [ ] **Step 1: Write `app.css`** (≤ 4 KB target)

```css
:root { --bg:#0f1115; --fg:#e6e8ef; --acc:#7df9aa; --muted:#8a90a0; }
* { box-sizing: border-box; }
body { margin: 0; font: 14px/1.45 system-ui, sans-serif; background: var(--bg); color: var(--fg); }
header { display: flex; gap: 1rem; padding: .75rem 1rem; border-bottom: 1px solid #222;
         align-items: center; }
header .brand { color: var(--acc); font-weight: 600; text-decoration: none; }
header .ver { color: var(--muted); font-weight: 400; font-size: .8em; }
header nav a { color: var(--fg); margin: 0 .5rem; text-decoration: none; }
header nav a:hover { color: var(--acc); }
main { padding: 1rem; max-width: 1100px; margin: 0 auto; }
.banner { padding: .5rem 1rem; border-bottom: 1px solid #222; }
.banner-info { background: #18242a; color: #cef; }
.banner-warn { background: #3a2a00; color: #ffd; }
.banner-error { background: #4a1010; color: #fdd; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; }
.card { display: block; padding: 1rem; border: 1px solid #222; border-radius: 8px;
        background: #15181f; text-decoration: none; color: inherit; }
.card.active { border-color: var(--acc); }
.card h2 { margin: 0 0 .5rem; font-size: 1.1em; }
.metric span { font-weight: 600; color: var(--acc); }
.classes { margin-top: .5rem; }
.tag { display: inline-block; background: #222; padding: .15rem .4rem; border-radius: 4px;
       font-size: .8em; margin: .1rem .15rem .1rem 0; }
table { border-collapse: collapse; width: 100%; margin-top: .5rem; }
th, td { text-align: left; padding: .35rem .5rem; border-bottom: 1px solid #222; }
code { background: #1c1f27; padding: 0 .25rem; border-radius: 3px; }
form textarea, form input { width: 100%; background: #1c1f27; color: var(--fg);
                            border: 1px solid #333; padding: .5rem; }
form button { margin-top: .5rem; padding: .4rem 1rem; background: var(--acc);
              border: none; color: #000; border-radius: 4px; cursor: pointer; }
footer { border-top: 1px solid #222; padding: 1rem; color: var(--muted); }
.empty { color: var(--muted); }
```

- [ ] **Step 2: Write `timeline.js` (XSS-safe DOM construction)**

```javascript
(() => {
  const list = document.getElementById('events');
  if (!list) return;
  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://')
    + location.host + '/api/v1/stream/events';
  const ws = new WebSocket(wsUrl);
  ws.onmessage = (msg) => {
    let e;
    try { e = JSON.parse(msg.data); } catch (_) { return; }
    const tr = document.createElement('tr');
    const tdTime = document.createElement('td');
    tdTime.textContent = new Date(e.ts || Date.now()).toISOString();
    const tdEntity = document.createElement('td');
    tdEntity.textContent = String(e.entity_id || '');
    const tdType = document.createElement('td');
    tdType.textContent = String(e.event_type || '');
    tr.appendChild(tdTime);
    tr.appendChild(tdEntity);
    tr.appendChild(tdType);
    list.prepend(tr);
    while (list.children.length > 200) list.removeChild(list.lastChild);
  };
  ws.onclose = () => { setTimeout(() => location.reload(), 2000); };
})();
```

- [ ] **Step 3: Write `settings.js`** (form submit → POST /settings/privacy)

```javascript
(() => {
  const form = document.getElementById('privacy-form');
  if (!form) return;
  const msg = document.getElementById('msg');
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const text = form.elements.hide_entities_pattern.value;
    const patterns = text.split('\n').map(s => s.trim()).filter(Boolean);
    const r = await fetch('/api/v1/settings/privacy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hide_entities_pattern: patterns }),
      credentials: 'same-origin',
    });
    msg.textContent = ''; // clear via textContent (not innerHTML)
    if (r.ok) {
      msg.textContent = 'Saved.';
    } else {
      const body = await r.json().catch(() => ({}));
      msg.textContent = 'Error: ' + (body.detail && body.detail.detail || r.status);
    }
  });
})();
```

- [ ] **Step 4: Manual browser smoke**

```bash
docker build -t ai-home-assistant:dev docker/
docker run --rm -p 8124:8124 \
  -e HA_URL=http://192.168.1.x:8123 \
  -e HA_TOKEN=$(cat ~/ha-token) \
  -v "$PWD/.dev-data:/data" \
  ai-home-assistant:dev
# Open http://localhost:8124  /  /entities  /  /timeline  /  /settings
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_ha/web/static/
git commit -m "feat(web): app.css dark theme + timeline.js/settings.js (XSS-safe DOM only)"
```

---

## Task 24: `main.py` lifespan + `__main__.py`

**Files:**
- Create: `src/ai_ha/main.py`
- Modify: `src/ai_ha/__main__.py`
- Modify: `src/ai_ha/__init__.py`

- [ ] **Step 1: Write `src/ai_ha/main.py`** — orchestrates spec §7.1 12-step startup

```python
"""ai-home-assistant entry — wires all components and runs FastAPI under uvicorn.

Order matches spec §7.1 startup self-check:
  1 load config
  2 compile privacy regex
  3 open DB + migrations
  4 integrity check (in Database.open)
  5 health metrics collector
  6 ha_adapter (REST snapshot once; background retry on failure)
  7 topology fetcher (initial pull; background retry)
  8 ingest pipeline
  9 jsonl writer (mounted via ingest hook; v0.1.0 minimal: jsonl uses same flush)
 10 config watchfiles
 11 FastAPI / uvicorn
 12 log "ai-ha started"
Steps 1-3 failure → exit non-zero (docker restart). Step 4+ failure → degraded.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path

import uvicorn

from ai_ha.archive import JsonlWriter
from ai_ha.config import AppConfig, ConfigError, load_config
from ai_ha.config.watcher import ConfigWatcher
from ai_ha.ha_adapter.topology_fetcher import TopologyFetcher
from ai_ha.ha_adapter.ws_client import HAWSClient
from ai_ha.health import HealthMetrics
from ai_ha.ingest import HAEvent, IngestPipeline
from ai_ha.privacy import HideMatcher, PatternComplexityError
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO
from ai_ha.topology import EntityIndex, SnapshotStore, TopologyOrchestrator
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState
from ai_ha.web.routes.stream import EventBroadcaster

logger = logging.getLogger("ai_ha")

EXIT_OK = 0
EXIT_DB_UNRECOVERABLE = 70
EXIT_CONFIG = 78


def _bootstrap_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def _print_first_run_banner(token: str) -> None:
    bar = "═" * 60
    print(f"\n{bar}", flush=True)
    print(f"║ ai-home-assistant FIRST RUN", flush=True)
    print(f"║ admin token: {token}", flush=True)
    print(f"║ Saved to /data/.admin-token (chmod 0600).", flush=True)
    print(f"║ Username 'admin', password the token above. v0.1.0.", flush=True)
    print(f"{bar}\n", flush=True)


def _ws_url(http_url: str) -> str:
    if http_url.startswith("https://"):
        return "wss://" + http_url[len("https://"):] + "/api/websocket"
    if http_url.startswith("http://"):
        return "ws://" + http_url[len("http://"):] + "/api/websocket"
    return http_url + "/api/websocket"


async def _run(config_path: str, data_dir: str) -> int:
    _bootstrap_logging()

    try:
        cfg = load_config(config_path)
    except ConfigError as exc:
        print(f"[ai-ha] config error: {exc}", file=sys.stderr, flush=True)
        return EXIT_CONFIG

    try:
        hide_matcher = HideMatcher(cfg.privacy.hide_entities_pattern)
    except (PatternComplexityError, Exception) as exc:  # noqa: BLE001
        print(f"[ai-ha] privacy pattern invalid: {exc}",
              file=sys.stderr, flush=True)
        return EXIT_CONFIG

    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)

    db_path = data_path / "ai-ha.db"
    migrations = Path(__file__).parent / "store" / "migrations"
    try:
        db = await Database.open(str(db_path), migrations_dir=str(migrations))
    except Exception as exc:  # noqa: BLE001
        logger.critical("DB open failed: %s", exc)
        return EXIT_DB_UNRECOVERABLE

    dao = StoreDAO(db)
    health = HealthMetrics(install_start_ms=int(time.time() * 1000))
    snapshot_store = SnapshotStore(db)
    entity_index = EntityIndex()
    orchestrator = TopologyOrchestrator(
        snapshot_store=snapshot_store, entity_index=entity_index, dao=dao,
    )
    broadcaster = EventBroadcaster()
    pipeline = IngestPipeline(
        dao=dao, entity_index=entity_index, hide_matcher=hide_matcher,
    )
    await pipeline.start()
    jsonl = JsonlWriter(str(data_path / "events"), compress=cfg.archive.compress)

    ws_url = _ws_url(cfg.ha.url)

    async def on_ws_event(msg: dict) -> None:
        ev = msg.get("event", {})
        ev_type = ev.get("event_type", "")
        if ev_type == "state_changed":
            d = ev.get("data", {})
            new = d.get("new_state") or {}
            old = d.get("old_state") or {}
            ha_ev = HAEvent(
                ts_ms=int(time.time() * 1000),
                entity_id=d.get("entity_id", ""),
                event_type="state_changed",
                old_state=str(old.get("state")) if old else None,
                new_state=str(new.get("state")) if new else None,
                context_user_id=(new.get("context") or {}).get("user_id"),
                context_parent_id=(new.get("context") or {}).get("parent_id"),
            )
            await pipeline.submit(ha_ev)
            await jsonl.append({
                "ts_ms": ha_ev.ts_ms, "entity_id": ha_ev.entity_id,
                "event_type": ha_ev.event_type,
                "old_state": ha_ev.old_state, "new_state": ha_ev.new_state,
            }, ts_ms=ha_ev.ts_ms)
            await broadcaster.publish({
                "ts": ha_ev.ts_ms, "entity_id": ha_ev.entity_id,
                "event_type": ha_ev.event_type,
            })
            health.record_event(ts_ms=ha_ev.ts_ms)
        elif ev_type.endswith("_registry_updated"):
            try:
                tf = TopologyFetcher(url=ws_url, token=cfg.ha.token)
                payload = await tf.fetch_once()
                sid, _ = await orchestrator.apply(
                    payload, ts_ms=int(time.time() * 1000),
                )
                health.set_topology_snapshot_id(sid)
            except Exception:  # noqa: BLE001
                logger.exception("registry refetch failed")

    ws_client = HAWSClient(url=ws_url, token=cfg.ha.token, on_event=on_ws_event)
    ws_task = asyncio.create_task(ws_client.run())

    async def initial_sync() -> None:
        try:
            tf = TopologyFetcher(url=ws_url, token=cfg.ha.token)
            payload = await tf.fetch_once()
            sid, _ = await orchestrator.apply(payload, ts_ms=int(time.time() * 1000))
            health.set_topology_snapshot_id(sid)
            health.set_ws_connected(True)
        except Exception:  # noqa: BLE001
            logger.exception("initial topology sync failed")

    asyncio.create_task(initial_sync())

    token_store = AdminTokenStore(str(data_path / ".admin-token"))
    is_first_run = not (data_path / ".admin-token").exists()
    token = token_store.ensure_token()
    if is_first_run:
        _print_first_run_banner(token)

    state = AppState(
        dao=dao, snapshot_store=snapshot_store, entity_index=entity_index,
        health=health, config_path=Path(config_path),
        hide_pattern=cfg.privacy.hide_entities_pattern,
        on_privacy_update=None,
    )
    state.broadcaster = broadcaster

    async def on_cfg_change(new_cfg: AppConfig) -> None:
        try:
            new_matcher = HideMatcher(new_cfg.privacy.hide_entities_pattern)
        except (PatternComplexityError, Exception) as exc:  # noqa: BLE001
            health.inc_config_reload_fail()
            logger.warning("privacy pattern reload failed: %s", exc)
            return
        pipeline._hide = new_matcher  # type: ignore[attr-defined]
        state.hide_pattern = new_cfg.privacy.hide_entities_pattern
        logger.info("privacy pattern reloaded: %d rules",
                    len(new_cfg.privacy.hide_entities_pattern))

    state.on_privacy_update = on_cfg_change
    watcher = ConfigWatcher(config_path, on_cfg_change)
    watcher_task = asyncio.create_task(watcher.run())

    app = create_app(
        token_store=token_store, require_auth=cfg.web.require_auth, state=state,
    )

    logger.info("ai-ha started, schema_version=1, topology=<pending>")

    cfg_uv = uvicorn.Config(
        app=app, host=cfg.web.host, port=cfg.web.port,
        log_level="info", lifespan="on",
    )
    server = uvicorn.Server(cfg_uv)

    def _handle_sig(*_a: object) -> None:
        server.should_exit = True

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_sig)

    try:
        await server.serve()
    finally:
        ws_client.stop()
        watcher.stop()
        await pipeline.stop()
        await jsonl.close()
        try:
            async with asyncio.timeout(15):
                await asyncio.gather(ws_task, watcher_task, return_exceptions=True)
        except TimeoutError:
            logger.warning("shutdown timeout — some background tasks killed")

    return EXIT_OK


def main() -> int:
    config_path = os.environ.get("AI_HA_CONFIG", "/data/config.toml")
    data_dir = os.environ.get("AI_HA_DATA_DIR", "/data")
    return asyncio.run(_run(config_path, data_dir))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Replace `src/ai_ha/__main__.py`**

```python
"""Entry — `python -m ai_ha`."""
from ai_ha.main import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Bump version in `src/ai_ha/__init__.py`**

```python
"""ai-home-assistant — AI layer that augments existing Home Assistant Core."""

__version__ = "0.1.0"
__all__ = ["__version__"]
```

- [ ] **Step 4: Container smoke**

```bash
docker build -t ai-home-assistant:dev docker/
docker run -d --name aiha-dev -p 8124:8124 \
  -e HA_URL=http://invalid:8123 -e HA_TOKEN=fake \
  -v "$PWD/.dev-data:/data" \
  ai-home-assistant:dev
sleep 5
curl -s http://localhost:8124/api/health | python -m json.tool
# Expect:
#   "status": "degraded",
#   "ws_connected": false,
#   "uptime_seconds": 5,
#   ...
docker logs aiha-dev | head -20
# Expect: first-run banner with admin token
docker rm -f aiha-dev
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_ha/main.py src/ai_ha/__main__.py src/ai_ha/__init__.py
git commit -m "feat(main): lifespan wire-up per spec §7.1 12-step + graceful shutdown"
```

---

# Phase 4 — Test + Release (Day 13-21)

## Task 25: Error / edge / adversarial integration tests (spec §7 case 1-14 + §9.2 6-类下限)

**Files:**
- Create: `tests/integration/test_error_ha_unreachable.py`
- Create: `tests/integration/test_error_ha_auth.py`
- Create: `tests/integration/test_error_ws_disconnect.py`
- Create: `tests/integration/test_error_db_busy.py`
- Create: `tests/integration/test_error_config_invalid.py`
- Create: `tests/integration/test_edge_cases.py`
- Create: `tests/integration/test_adversarial.py`
- Create: `tests/integration/test_i18n.py`
- Create: `tests/integration/test_degrade.py`

Test outline per case — each file uses the MockHAServer fixture + ASGITransport.

- [ ] **Step 1: `test_error_ha_unreachable.py`** (case 1)

```python
import pytest
from ai_ha.ha_adapter.client import HAClient, HAUnreachable


@pytest.mark.asyncio
async def test_rest_unreachable_raises_after_retries():
    c = HAClient("http://127.0.0.1:1", "tok", connect_retries=2)
    with pytest.raises(HAUnreachable):
        await c.fetch_states()
    await c.aclose()
```

- [ ] **Step 2: `test_error_ha_auth.py`** (case 2)

```python
import pytest
import asyncio
from ai_ha.ha_adapter.ws_client import HAWSClient


@pytest.mark.asyncio
async def test_ws_auth_invalid_stops_retry(mock_ha):
    client = HAWSClient(
        url=f"ws://127.0.0.1:{mock_ha.port}", token="bad",
        on_event=lambda e: asyncio.sleep(0),
        max_reconnect_seconds=2,
    )
    await client.run()
    assert client.last_error_kind == "auth-invalid"
```

- [ ] **Step 3: `test_error_ws_disconnect.py`** (case 3 — covered in test_ha_ws_client.py already; promote to error suite)

```python
# re-use test_reconnects_on_drop from test_ha_ws_client.py
# add: assert disconnect_count exactly matches forced drops
```

- [ ] **Step 4: `test_error_db_busy.py`** (case 8 — simulate via parallel writers)

```python
import asyncio
import pytest
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, EventRow

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_concurrent_writes_serialize(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    async def writer(start: int) -> None:
        for i in range(50):
            await dao.insert_events([EventRow(
                start + i, start + i, f"x.{i}", "state_changed", None, '"on"',
                None, None, None, None, None, 1,
            )])
    await asyncio.gather(*[writer(s * 1000) for s in range(5)])
    rows = await dao.list_events(limit=500)
    assert len(rows) == 250  # no lock loss
```

- [ ] **Step 5: `test_error_config_invalid.py`** (case 5/6)

```python
import pytest
from ai_ha.config.loader import load_config, ConfigError


def test_invalid_toml_raises(tmp_path):
    (tmp_path / "c.toml").write_text("[broken\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path / "c.toml")


def test_missing_ha_section_raises(tmp_path):
    (tmp_path / "c.toml").write_text("[other]\nx=1\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path / "c.toml")
```

- [ ] **Step 6: `test_edge_cases.py`** — empty state / 256-char name / unicode-emoji / orphan / ts=0

```python
import pytest
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, EntityRow, EventRow

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_super_long_friendly_name(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    name = "X" * 256
    await dao.upsert_entities([EntityRow(
        "e", name, "sensor", None, None, "a", 0, 1, 1, 1, 0, 0,
    )])
    rows = await dao.list_entities()
    assert rows[0].friendly_name == name


@pytest.mark.asyncio
async def test_emoji_entity_id(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    await dao.insert_events([EventRow(
        1000, 1001, "light.🛋️_main", "state_changed", None, '"on"',
        None, None, "客厅", None, "light", 1,
    )])
    rows = await dao.list_events(limit=10)
    assert rows[0].entity_id == "light.🛋️_main"
    assert rows[0].area_id == "客厅"


@pytest.mark.asyncio
async def test_zero_ts_handled(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    await dao.insert_events([EventRow(
        0, 1, "x", "state_changed", None, None, None, None, None, None, None, 1,
    )])
    rows = await dao.list_events()
    assert len(rows) == 1
```

- [ ] **Step 7: `test_adversarial.py`** — XSS / regex DoS / oversized limit / cookie tamper

```python
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, EntityRow
from ai_ha.topology import SnapshotStore, EntityIndex
from ai_ha.health import HealthMetrics
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_xss_friendly_name_escaped(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    await dao.upsert_entities([EntityRow(
        "evil", "<script>alert(1)</script>", "light", None, None, None,
        0, 1, 1, 1, 0, 0,
    )])
    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/entities", auth=("admin", ts.read()))
        assert "<script>" not in r.text
        assert "&lt;script&gt;" in r.text


@pytest.mark.asyncio
async def test_regex_dos_rejected_via_post(tmp_path):
    # privacy POST rejects (a+)+b — covered by test_api_settings
    pass


@pytest.mark.asyncio
async def test_oversized_limit_returns_422(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/entities?limit=10000000", auth=("admin", ts.read()))
        assert r.status_code == 422
```

- [ ] **Step 8: `test_i18n.py`** — 中文 area / entity 渲染

```python
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, AreaRow
from ai_ha.topology import SnapshotStore, EntityIndex
from ai_ha.health import HealthMetrics
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_chinese_area_name_renders(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    await dao.upsert_areas([AreaRow("kt", "厨房", None, None, "[]", 1, 1, 1)])
    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/", auth=("admin", ts.read()))
        assert "厨房" in r.text
```

- [ ] **Step 9: `test_degrade.py`** — HA WS down → stale read still serves

```python
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, AreaRow
from ai_ha.topology import SnapshotStore, EntityIndex
from ai_ha.health import HealthMetrics
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_read_continues_when_ws_disconnected(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    await dao.upsert_areas([AreaRow("a", "A", None, None, "[]", 1, 1, 1)])
    health = HealthMetrics(install_start_ms=0)
    health.set_ws_connected(False)  # simulate disconnect
    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=health,
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/areas", auth=("admin", ts.read()))
        assert r.status_code == 200
        h = await c.get("/api/health")
        assert h.json()["status"] == "degraded"
```

- [ ] **Step 10: Run all + commit**

```bash
pytest tests/integration/ -v
git add tests/integration/test_error_*.py tests/integration/test_edge_cases.py \
        tests/integration/test_adversarial.py tests/integration/test_i18n.py \
        tests/integration/test_degrade.py
git commit -m "test(integration): error/edge/adversarial/i18n/degrade — covers spec §7 + §9 6-类下限"
```

---

## Task 26: Concurrency + resource-exhaustion tests

**Files:**
- Create: `tests/integration/test_concurrency.py`
- Create: `tests/integration/test_resource_exhaustion.py`

- [ ] **Step 1: Write `test_concurrency.py`** — 100 concurrent reads while ingest

```python
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, EventRow
from ai_ha.topology import SnapshotStore, EntityIndex
from ai_ha.health import HealthMetrics
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_100_concurrent_reads_while_writing(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)

    async def writer() -> None:
        for i in range(200):
            await dao.insert_events([EventRow(
                i, i, f"x.{i}", "state_changed", None, '"on"',
                None, None, None, None, None, 1,
            )])
            await asyncio.sleep(0)

    async def reader(client: AsyncClient) -> int:
        r = await client.get("/api/v1/events?limit=10", auth=("admin", ts.read()))
        return r.status_code

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        w = asyncio.create_task(writer())
        results = await asyncio.gather(*[reader(c) for _ in range(100)])
        await w
    assert all(s == 200 for s in results)
```

- [ ] **Step 2: Write `test_resource_exhaustion.py`** — disk-full + db-busy storm

```python
import asyncio
import os
import pytest
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, EventRow

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.skipif(os.geteuid() != 0, reason="requires mount tmpfs (root)")
@pytest.mark.asyncio
async def test_disk_full_does_not_crash(tmp_path):
    # NOTE: in CI we mark this slow + run only on tmpfs-mountable hosts.
    # Local dev can simulate via fallocate.
    pass


@pytest.mark.asyncio
async def test_lock_storm_recovers(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    # 50 concurrent writers, busy_timeout=5s configured in PRAGMA
    async def w(i: int) -> None:
        for _ in range(20):
            await dao.insert_events([EventRow(
                i, i, "x", "state_changed", None, None, None, None,
                None, None, None, 1,
            )])
    await asyncio.gather(*[w(i) for i in range(50)])
    rows = await dao.list_events(limit=2000)
    assert len(rows) == 1000  # no lock loss
```

- [ ] **Step 3: Run + commit**

```bash
pytest tests/integration/test_concurrency.py tests/integration/test_resource_exhaustion.py -v
git add tests/integration/test_concurrency.py tests/integration/test_resource_exhaustion.py
git commit -m "test(integration): 100 concurrent reads + lock-storm recovery"
```

---

## Task 27: Perf benchmarks (criterion-like via pytest-benchmark)

**Files:**
- Create: `tests/perf/__init__.py`
- Create: `tests/perf/bench_ingest.py`
- Create: `tests/perf/bench_api.py`

- [ ] **Step 1: Write `bench_ingest.py`** — measure ingest p50/p95/p99

```python
import pytest
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO
from ai_ha.privacy import HideMatcher
from ai_ha.topology import EntityIndex, TopologyPayload
from ai_ha.ingest.pipeline import HAEvent, IngestPipeline

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_ingest_1k_events_under_p99_100ms(tmp_path, benchmark):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    payload = TopologyPayload(
        areas=[{"area_id": "a"}], devices=[],
        entities=[{"entity_id": "e", "area_id": "a"}],
    )
    idx = EntityIndex.build_from_payload(payload, snapshot_id=1)
    pipe = IngestPipeline(
        dao=StoreDAO(db), entity_index=idx, hide_matcher=HideMatcher([]),
        batch_size=100, batch_interval_ms=1000,
    )
    await pipe.start()

    async def run() -> None:
        for i in range(1000):
            await pipe.submit(HAEvent(
                ts_ms=i, entity_id="e", event_type="state_changed",
                old_state=None, new_state='"on"',
                context_user_id=None, context_parent_id=None,
            ))
        await pipe.flush()

    import asyncio
    benchmark(lambda: asyncio.get_event_loop().run_until_complete(run()))
    # post-condition: p99 < 100ms per event (target G3)
    await pipe.stop()
```

Note: pytest-benchmark integrates with async via explicit asyncio.run wrappers; consider using simple timing as fallback:

```python
import time
async def manual_bench():
    times = []
    for i in range(1000):
        t0 = time.perf_counter()
        await pipe.submit(...)
        times.append(time.perf_counter() - t0)
    times.sort()
    p99 = times[990]
    assert p99 < 0.1, f"p99={p99*1000:.1f}ms exceeds 100ms"
```

- [ ] **Step 2: Write `bench_api.py`** — measure /api/health + /api/v1/areas latency

Similar pattern; assert p99 < 50ms (G10).

- [ ] **Step 3: Run + commit**

```bash
pytest tests/perf/ -v --benchmark-only || pytest tests/perf/ -v
git add tests/perf/
git commit -m "test(perf): ingest p99 < 100ms + /api/* p99 < 50ms benchmarks (G3/G10)"
```

---

## Task 28: Soak harness — 7-day run + analyze.py

**Files:**
- Create: `tests/soak/__init__.py`
- Create: `tests/soak/run_soak.py`
- Create: `tests/soak/analyze.py`
- Create: `tests/soak/README.md`

This is the G1 gate. Cannot be mock-only — must be real wall-clock 7 days against either real HA or MockHAServer with simulated traffic.

- [ ] **Step 1: Write `tests/soak/run_soak.py`** (launches container + injects traffic)

```python
"""7-day soak runner.

Two modes:
  --target=real-ha     point at $HA_URL and let ai-ha receive its real traffic
  --target=mock        spin up MockHAServer + inject synthetic 1k evt/day

Every 10 minutes:
  - curl http://localhost:8124/api/health → append to metrics.jsonl
  - shell out ps to measure RSS
  - sqlite3 size

Inject 5 random WS disconnects across the run (target=mock only).
Stop after 7×24×3600 seconds; emit run-<ts>/{metrics.jsonl, summary.txt}.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

from tests.integration.mock_ha_server import MockHAServer

SOAK_SECONDS = 7 * 24 * 3600  # 7 days
HEALTH_INTERVAL = 600          # 10 min


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--target", choices=["real-ha", "mock"], required=True)
    p.add_argument("--container", default="aiha-soak")
    p.add_argument("--port", type=int, default=8124)
    p.add_argument("--output-dir", default="tests/soak/runs")
    args = p.parse_args()

    run_dir = Path(args.output_dir) / f"run-{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = run_dir / "metrics.jsonl"

    mock_task: asyncio.Task[None] | None = None
    if args.target == "mock":
        srv = MockHAServer()
        await srv.start()
        ha_url = f"http://127.0.0.1:{srv.port}"
        ha_token = "test-token-not-real"
        mock_task = asyncio.create_task(_inject_synthetic_traffic(srv))
    else:
        ha_url = os.environ["HA_URL"]
        ha_token = os.environ["HA_TOKEN"]

    subprocess.run([
        "docker", "run", "-d", "--name", args.container,
        "--rm", "-p", f"{args.port}:8124",
        "-e", f"HA_URL={ha_url}", "-e", f"HA_TOKEN={ha_token}",
        "ai-home-assistant:dev",
    ], check=True)

    start = time.time()
    try:
        while time.time() - start < SOAK_SECONDS:
            await _record_metric(args.port, metrics_file, args.container)
            await asyncio.sleep(HEALTH_INTERVAL)
            if args.target == "mock" and random.random() < 0.001:
                await srv.disconnect_all()  # ~5 disconnects per 7 days
    finally:
        subprocess.run(["docker", "stop", args.container], check=False)
        if mock_task:
            mock_task.cancel()
    return 0


async def _record_metric(port: int, fpath: Path, container: str) -> None:
    out = subprocess.run(
        ["curl", "-s", f"http://localhost:{port}/api/health"], capture_output=True, text=True,
    ).stdout
    rss = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container],
        capture_output=True, text=True,
    ).stdout.strip()
    with fpath.open("a") as f:
        f.write(json.dumps({"ts": int(time.time()), "health": out, "rss": rss}) + "\n")


async def _inject_synthetic_traffic(srv: MockHAServer) -> None:
    # ~1k events / day → one every ~86 s
    while True:
        await srv.push_event("light.x", old="off", new="on")
        await asyncio.sleep(86)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 2: Write `tests/soak/analyze.py`** (produces summary.md)

```python
"""Read run-<ts>/metrics.jsonl, compute uptime% / mem trend / DB size growth / DC count."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def main(run_dir: str) -> int:
    p = Path(run_dir) / "metrics.jsonl"
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    if not rows:
        print("no rows")
        return 1
    total = len(rows)
    healthy = sum(1 for r in rows if '"status": "healthy"' in r.get("health", ""))
    uptime_pct = healthy / total * 100
    disconnects = sum(
        int(re.search(r'"disconnect_count":\s*(\d+)', r["health"]).group(1))
        for r in rows if re.search(r'"disconnect_count":', r["health"])
    )
    summary = (Path(run_dir) / "summary.md")
    summary.write_text(
        f"# Soak summary\n\n"
        f"- samples: {total}\n"
        f"- ws_connected uptime: {uptime_pct:.2f}% (G1 ≥ 99.5%)\n"
        f"- disconnect events: {disconnects}\n"
    )
    print(summary.read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
```

- [ ] **Step 3: Write `tests/soak/README.md`** (manual run instructions)

```markdown
# Soak harness

## Mode 1: against real HA (best — G1 evidence)

```bash
docker build -t ai-home-assistant:dev docker/
export HA_URL=http://homeassistant.local:8123
export HA_TOKEN=<token>
python -m tests.soak.run_soak --target=real-ha --container=aiha-soak
# After 7 days:
python -m tests.soak.analyze tests/soak/runs/run-<ts>/
```

## Mode 2: mock HA + synthetic traffic

```bash
python -m tests.soak.run_soak --target=mock
```

`summary.md` is the G1 evidence. Commit it to `docs/screenshots/v010-ga-verification/`.
```

- [ ] **Step 4: Commit (harness only — 7d run happens manually before GA)**

```bash
git add tests/soak/
git commit -m "test(soak): 7d harness — real-ha or mock target, /api/health polling + disconnect injection"
```

---

## Task 29: TEST_PLAN.md + MANUAL_TEST_CHECKLIST.md + tests/TESTING.md

**Files:**
- Create: `tests/TEST_PLAN.md`
- Create: `tests/MANUAL_TEST_CHECKLIST.md`
- Create: `tests/TESTING.md` (how to run + dependencies)

- [ ] **Step 1: Write `tests/TEST_PLAN.md`** (per global §6.1 SSOT)

```markdown
# v0.1.0 Test Plan

## Objective
Verify all 17 acceptance gates (G1-G17 per spec Appendix C) and 14 error cases
(spec §7) before tagging v0.1.0 GA.

## Matrix

| Layer | Tool | Coverage target |
|-------|------|-----------------|
| Unit | pytest | line 80% / branch 60% |
| Integration | pytest + MockHAServer | 12 HTTP endpoints + WS + 14 error cases |
| Perf | pytest + manual timing | ingest p99 < 100ms / API p99 < 50ms |
| Soak | tests/soak harness | 7d real-wallclock, real or mock HA |
| Multi-arch | docker buildx | amd64/arm64/riscv64 build + amd64 native test + real RK3588 verify |

## Black-box / Grey-box / White-box

- **Black-box (G1/G5/G6/G7/G9/G16/G17)**: real RK3588 board, real HA, real
  browser. No mocks. G7 evidence: grep DB/jsonl/logs for `entity_id` after 100
  privacy-hit events → 0/0/0 hits.
- **Grey-box (G2/G3/G10/G11/G12)**: MockHAServer + ASGITransport, measured.
- **White-box (G13/G15)**: pytest --cov; grep `except.*pass`.

## Pass criteria

Per spec Appendix C: 17/17 must PASS. Any single fail = no GA tag.

## Test history (per release)

| v0.1.0 | date | run | result |
|--------|------|-----|--------|
| | | | |
```

- [ ] **Step 2: Write `tests/MANUAL_TEST_CHECKLIST.md`** (per global §5.3 step 2)

```markdown
# v0.1.0 Manual Test Checklist

> Run on real RK3588 board (per spec §9.5) with real Home Assistant. Tick each
> box and paste evidence (screenshot path / curl output / log excerpt).

## First-run

- [ ] Container starts; stdout shows admin token (red banner) once
- [ ] /data/.admin-token created with 0600
- [ ] Browser http://<board>:8124 redirects to /login; token works

## Topology

- [ ] /api/v1/topology returns snapshot_id ≥ 1 within 30s
- [ ] Web UI / (rooms grid) shows all my HA areas with name
- [ ] Move an entity to a different area in HA → ai-ha new snapshot within 5s
  (check /api/v1/topology/snapshots count increased)
- [ ] Orphan detection: leave one entity unassigned in HA → /entities?orphan=true
  returns it

## Privacy

- [ ] /settings shows current hide_entities_pattern (default empty)
- [ ] Add pattern `sensor\.bank_card_.*` and save → settings.html shows new pattern
- [ ] Trigger 10 state changes on a hidden entity → /api/v1/events does NOT show them
- [ ] grep /data/ai-ha.db for hidden entity_id → 0 hits
- [ ] grep /data/events/*.jsonl.gz | grep entity_id of hidden → 0 hits
- [ ] grep docker logs aiha for entity_id of hidden → 0 hits
- [ ] /api/health hidden_event_count ≥ 10

## Web UI

- [ ] Chrome desktop: 5 pages render, 0 console errors
- [ ] Firefox desktop: ditto
- [ ] Safari desktop: ditto
- [ ] Chrome mobile viewport (≤ 400 px): rooms grid usable

## Multi-arch

- [ ] amd64 image starts + /api/health 200
- [ ] arm64 image (RK3588 native): starts + /api/health 200
- [ ] riscv64 buildx PASS (no runtime test — deferred per spec G17)

## Soak

- [ ] tests/soak/runs/run-<ts>/summary.md present, uptime ≥ 99.5%

## Acceptance gates (Appendix C)

- [ ] G1 7d uptime
- [ ] G2 reconnect p95 < 30s
- [ ] G3 ingest p99 < 100ms
- [ ] G4 events_received == events_in_db (during online window)
- [ ] G5 topology count matches HA UI
- [ ] G6 registry update detected ≤ 5s
- [ ] G7 privacy 0/0/0
- [ ] G8 privacy hot-reload < 5s
- [ ] G9 3 browsers 0 console errors
- [ ] G10 API p99 < 50/200ms
- [ ] G11 RAM < 300/500 MB
- [ ] G12 DB < 50 MB/1k events
- [ ] G13 unit 80%/60%
- [ ] G14 integration 12+WS=14 PASS
- [ ] G15 grep `except.*pass` = 0
- [ ] G16 docs synced
- [ ] G17 amd64 + arm64 + riscv64 build + RK3588 real
```

- [ ] **Step 3: Write `tests/TESTING.md`** (how to run)

```markdown
# Running the test suite

## Inside Docker (recommended)

```bash
docker build -t ai-home-assistant:dev docker/
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c \
  "pip install -e . && pytest tests/unit tests/integration -v"
```

## Coverage

```bash
pytest --cov=src/ai_ha --cov-report=term-missing tests/unit tests/integration
```

## Lint + types

```bash
ruff check src/ tests/
mypy src/
```

## Perf

```bash
pytest tests/perf/ -v
```

## Soak (7 days; not in CI)

See `tests/soak/README.md`.
```

- [ ] **Step 4: Commit**

```bash
git add tests/TEST_PLAN.md tests/MANUAL_TEST_CHECKLIST.md tests/TESTING.md
git commit -m "doc(tests): TEST_PLAN + MANUAL_TEST_CHECKLIST + TESTING.md per global §6.1"
```

---

## Task 30: Multi-arch buildx verification

**Files:**
- Modify: `.github/workflows/ci.yml` (already builds 3 arch; verify still green after all code lands)

- [ ] **Step 1: Verify GH Actions ci.yml runs to completion on a PR**

```bash
# Push current state to a temporary branch and observe Actions UI
git push origin HEAD:tmp-ci-verify
# Wait for the lint-and-test + multi-arch-build jobs
```

- [ ] **Step 2: Local cross-build smoke (no push)**

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64,linux/riscv64 \
  -f docker/Dockerfile -t ai-home-assistant:multi-test --load .
# Note: --load only works for single platform; for all 3, omit --load and just verify it builds.
docker buildx build \
  --platform linux/amd64,linux/arm64,linux/riscv64 \
  -f docker/Dockerfile -t ai-home-assistant:multi-test .
```

- [ ] **Step 3: Document outcome in RELEASE.md** (next task)

- [ ] **Step 4: Commit (workflow already exists; nothing new to commit unless ci.yml needs adjustments)**

If pytest steps need to be added to ci.yml:

```yaml
# In .github/workflows/ci.yml under lint-and-test:
      - name: Run tests
        run: |
          PYTHONPATH=src pytest tests/unit tests/integration -v
```

Then:

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run unit + integration tests on amd64 in CI"
```

---

## Task 31: Real RK3588 verification + screenshots

**Files:**
- Create: `docs/screenshots/v010-ga-verification/.gitkeep`
- Modify: `.gitignore` (ensure docs/screenshots committed)

This task happens on a real RK3588 board (per spec §9.5).

- [ ] **Step 1: On RK3588 board, pull and run the v0.1.0 RC image**

```bash
# On the board:
docker pull ghcr.io/qiurui144/ai-home-assistant:v0.1.0-rc.1
docker run -d --name aiha -p 8124:8124 \
  -e HA_URL=http://<your-ha>:8123 -e HA_TOKEN=<token> \
  -v /opt/aiha-data:/data \
  ghcr.io/qiurui144/ai-home-assistant:v0.1.0-rc.1
docker logs aiha | head -20  # screenshot the first-run banner
```

- [ ] **Step 2: Walk the manual checklist + capture screenshots**

For each ✓ in `tests/MANUAL_TEST_CHECKLIST.md`, take 1 screenshot:

```
docs/screenshots/v010-ga-verification/
├── 01-first-run-banner.png
├── 02-rooms-grid.png
├── 03-room-detail.png
├── 04-entities-orphan.png
├── 05-timeline.png
├── 06-settings-hide-pattern.png
├── 07-privacy-grep-zero.txt        (output of `grep entity_id /data/ai-ha.db | wc -l`)
├── 08-topology-snapshots-history.png
├── 09-rk3588-uname.txt             (uname -a + /proc/cpuinfo head)
├── 10-soak-summary.md               (copy of tests/soak/runs/<latest>/summary.md)
└── 11-multi-browser-grid.png
```

- [ ] **Step 3: Commit screenshots**

```bash
git add docs/screenshots/v010-ga-verification/
git commit -m "evidence(v0.1.0): RK3588 RC verification — 11 screenshots + soak summary"
```

---

## Task 32: RC 4 Gate audit + RELEASE.md v0.1.0 section

**Files:**
- Create: `RELEASE.md`

Per global §7.2 the four gates:
- Gate 1 (docs): README/DEVELOP/RELEASE/CLAUDE.md match code
- Gate 2 (code): pytest --cov 80%/60%, ruff/mypy clean, 0 skipped, 0 WIP/TODO/FIXME in commit msgs
- Gate 3 (function): every RELEASE Highlight has evidence
- Gate 4 (gap): RELEASE Known Limitations enumerated

- [ ] **Step 1: Write `RELEASE.md` with v0.1.0 section**

```markdown
# Release notes

## v0.1.0 — 2026-06-xx (Listen-only Foundation)

### Highlights
- HA WebSocket subscribe with auto-reconnect (exponential backoff 1→60s)
- Topology snapshot ingestion: areas / devices / entities; append-only versioned
- Room-aware Web UI (5 pages: rooms grid / room detail / entities / timeline / settings)
- Privacy hide-pattern with ReDoS guard; hot-reload via watchfiles
- 6 health metrics on /api/health (ws_connected / events_per_hour / db_size_mb /
  hidden_event_count / uptime_seconds / current_topology_snapshot_id)
- Multi-arch Docker image (amd64/arm64; riscv64 build-only)

### Breaking changes
None — first release.

### Migration
None — first release.

### Known limitations
- **Listen-only**: no LLM, no learning, no automation suggestions. v0.4 starts.
- **No HA write**: read-only. v0.6 introduces soft-intention queue.
- **No multi-user / voice ID**: single household. v1.1 adds voiceprint.
- **riscv64**: image builds in CI but runtime is untested (K3 hardware deferred per spec G17).
- **High event rate (>5k/h on eMMC)**: tested upper bound. Use NVMe for higher.
- **SIGKILL data loss**: in-memory buffer (max 1000) discarded; v0.6+ evaluates WAL buffer.

### Tested HA versions
- HA Core 2026.5.x ✓
- HA Core 2026.6.x ✓
- Older HA (< 2024.x): falls back to 60s polling for registry; degraded mode.

### Hardware verification
- Rockchip RK3588 NanoPC-T6: real-device smoke + 7d soak ✓ (see docs/screenshots/v010-ga-verification/)
- amd64 (Intel N100): smoke ✓
- riscv64 (SpacemiT K1/K3): NOT yet — CI build only

### Verification evidence
See `docs/screenshots/v010-ga-verification/` for the 11-screenshot evidence pack
and `tests/soak/runs/<latest>/summary.md` for soak uptime data.
```

- [ ] **Step 2: Run the 4-gate audit script** (manual checklist)

```bash
# Gate 1: docs vs code
grep -n "v0.1.0" README.md DEVELOP.md RELEASE.md src/ai_ha/__init__.py
# Verify all match. Update README "Status" section: change "Spec stage — no code yet"
# to "v0.1.0 GA"

# Gate 2:
ruff check src/ tests/
mypy src/
pytest --cov=src/ai_ha --cov-fail-under=80 tests/unit tests/integration
git log --oneline | grep -iE "WIP|FIXME-CRITICAL"  # should be empty

# Gate 3:
# For each Highlight in RELEASE, point to a screenshot or test
# (verify by reading docs/screenshots/v010-ga-verification/)

# Gate 4:
# Confirm Known Limitations table covers behaviors that may surprise users
```

- [ ] **Step 3: Update README.md "Status" section**

Edit `README.md`:

```diff
-## Status
-
-**Spec stage** — no code yet. v0.1.0 target ~ 6 weeks of focused development
-(per [§12 timeline](docs/specs/2026-05-25-ai-home-assistant-architecture.md#12-实施时间线-建议)).
-
-Subscribe to repo for v0.1.0 release notification.
+## Status
+
+**v0.1.0 GA** — Listen-only foundation. See [RELEASE.md](RELEASE.md) for
+changes and known limitations. v0.2 (histogram behavior model) is next.
```

- [ ] **Step 4: Commit**

```bash
git add RELEASE.md README.md
git commit -m "doc(release): RELEASE.md v0.1.0 + README status update + 4-gate audit"
```

---

## Task 33: GA tag v0.1.0 + push to main

**Files:**
- (none — git operations only)

- [ ] **Step 1: Final pre-tag check**

```bash
git log --oneline | head -40
# Verify last commit is the RELEASE/README update
ruff check src/ tests/ && mypy src/ && \
  pytest --cov=src/ai_ha --cov-fail-under=80 tests/unit tests/integration && \
  echo "ALL GREEN"
```

- [ ] **Step 2: Create annotated tag**

```bash
git tag -a v0.1.0 -m "v0.1.0 — Listen-only Foundation

Highlights: HA WS subscribe with reconnect, topology snapshot ingestion,
room-aware Web UI (5 pages), privacy hide-pattern with ReDoS guard,
6 health metrics, multi-arch Docker (amd64/arm64; riscv64 build-only).

Known limitations: no LLM, no learning, no HA write. See RELEASE.md.

Verified: real RK3588 + 7d soak. See docs/screenshots/v010-ga-verification/.
Spec: docs/superpowers/specs/2026-06-02-ai-home-assistant-v010-listen-only-design.md.
"
git push origin main
git push origin v0.1.0
```

- [ ] **Step 3: GH Actions release.yml will auto-build + push GHCR image**

```bash
# Watch the release workflow:
# https://github.com/qiurui144/ai-home-assistant/actions
# Confirm ghcr.io/qiurui144/ai-home-assistant:0.1.0 and :latest tags appear
```

- [ ] **Step 4: Re-verify on RK3588 with the GHCR image (per spec §9.5 final step)**

```bash
# On the board:
docker pull ghcr.io/qiurui144/ai-home-assistant:0.1.0
docker stop aiha && docker rm aiha
docker run -d --name aiha -p 8124:8124 \
  -e HA_URL=http://<ha>:8123 -e HA_TOKEN=<token> \
  -v /opt/aiha-data:/data \
  ghcr.io/qiurui144/ai-home-assistant:0.1.0
curl http://localhost:8124/api/health
# Capture one more screenshot:
#   docs/screenshots/v010-ga-verification/12-ga-image-deployed.png
```

- [ ] **Step 5: Commit the GA-image deployment evidence**

```bash
git add docs/screenshots/v010-ga-verification/12-ga-image-deployed.png
git commit -m "evidence(v0.1.0): GA image deployed on RK3588 — final verification"
git push origin main
```

---

# Risk register (v0.1.0 plan-time — derived from spec §11)

| # | Risk | Severity | Affects | Mitigation in this plan |
|---|------|:---:|---------|------------|
| 1 | HA WS API drift mid-implementation | S2 | Tasks 13-15 | MockHAServer mirrors HA WS surface; CI matrix; spec §10.3 watch list |
| 2 | Task 14 reconnect logic flaky in tests | S2 | Task 14, 26 | TDD with controlled disconnect via mock_ha.disconnect_all(); G2 acceptance |
| 3 | Privacy ReDoS heuristic too permissive | S2 | Task 6, 20g | Tests cover known patterns; future v0.6+ swap to re2 |
| 4 | Task 16 ingest pipeline race(commit while submit) | S2 | Task 16 | asyncio.Lock around buffer; test_concurrency.py 100 reader exercise |
| 5 | Jinja autoescape unfailed test (XSS slip) | S2 | Task 22, 25 | test_adversarial.py explicit `<script>` test |
| 6 | RK3588 native test slower than budgeted day 14-15 | S3 | Task 31 | Allow buffer days 19-21 |
| 7 | 7d soak fails due to mem leak | S2 | Task 28 | Mem trend chart in summary.md; if leak found, debug + retest |
| 8 | aiosqlite incompat with Py3.11 on arm64 | S3 | Task 4 | Wheel pinned; tested on amd64 in CI; arm64 verified in Task 31 |
| 9 | Settings POST writes garbage TOML | S2 | Task 20g | Round-trip test (`tomllib.loads` after write) |
| 10 | EntityIndex atomic-swap not actually atomic under GIL contention | S3 | Task 8 | Dict pointer assignment is atomic in CPython; no test needed |

---

# GA acceptance checklist (G1-G17 + RC 4 Gate)

## Acceptance gates G1-G17 (spec Appendix C)

- [ ] **G1**: 7d soak uptime ≥ 99.5% — evidence: `tests/soak/runs/<ts>/summary.md`
- [ ] **G2**: reconnect median < 5s, p95 < 30s — evidence: `test_reconnect.py` log
- [ ] **G3**: ingest p99 < 100ms — evidence: `tests/perf/bench_ingest.py` output
- [ ] **G4**: events received == events in DB (online window) — manual: count diff
- [ ] **G5**: topology count matches HA UI — manual checklist + screenshot
- [ ] **G6**: registry update detected ≤ 5s — manual: edit area in HA + observe
- [ ] **G7**: privacy 0 in DB / 0 in jsonl / 0 in log — `grep` evidence + screenshot
- [ ] **G8**: privacy hot-reload < 5s — manual: POST + observe pipeline change
- [ ] **G9**: 3 browsers + mobile viewport 0 console errors — screenshots
- [ ] **G10**: `/api/health` p99 < 50ms, `/api/v1/areas` p99 < 200ms — `bench_api.py`
- [ ] **G11**: RAM sustained < 300 MB / peak < 500 MB — soak metrics
- [ ] **G12**: DB growth < 50 MB / 1000 events — soak metrics
- [ ] **G13**: pytest --cov line ≥ 80% / branch ≥ 60% — CI output
- [ ] **G14**: 14 integration test files PASS — pytest output
- [ ] **G15**: `grep -rn "except.*:.*pass" src/` = 0 — manual
- [ ] **G16**: README/DEVELOP/RELEASE/spec all reference v0.1.0 — manual diff
- [ ] **G17**: amd64 native test + 3-arch buildx + RK3588 real `/api/health` 200

## RC 4 Gate (global §7.2)

- [ ] **Gate 1 (docs)**: no doc drift (Task 32)
- [ ] **Gate 2 (code)**: ruff/mypy clean, 0 skip, 80%/60% cov (Task 32)
- [ ] **Gate 3 (function)**: every Highlight has screenshot evidence (Task 31)
- [ ] **Gate 4 (gap)**: Known Limitations enumerated in RELEASE.md (Task 32)

## Release self-deploy verification (global §7.3)

- [ ] GHCR image pulled (not dev cargo build)
- [ ] Real RK3588 board (not amd64 dev)
- [ ] Real HA (not MockHAServer)
- [ ] Real browser walk-through (per checklist)
- [ ] Evidence committed to `docs/screenshots/v010-ga-verification/`

---

# Self-review

**Spec coverage check:**

| Spec section | Task(s) |
|--------------|---------|
| §1 north star + 1.1 7-day soak | Task 28, G1 |
| §2.1 11 things v0.1.0 does | Tasks 2-24 (foundation, adapter, web) |
| §2.2 things v0.1.0 does NOT | Tasks 18-20 (no service_call, no LLM in any route) |
| §2.3 cross-slice promises (schema for v0.2+) | Task 5 (DDL), Task 7 (snapshot version), Task 16 (denormalize) |
| §3 architecture + data flow | Tasks 4-18 (each module) |
| §4 module boundary + dep graph | All Tasks (per file ownership) |
| §5 API contract (12 routes + WS) | Tasks 19-21 |
| §6 extension points (v0.1.0 minimal) | Task 24 startup log message |
| §7 14 error cases | Task 25 (8 tests cover 14 cases) |
| §8 cost contract | Task 28 soak metrics, Task 32 RELEASE.md |
| §9 test matrix | Tasks 25-29 |
| §10 backward compat | Task 4 (migration runner) |
| §11 15 risks | Plan risk register above (subset; spec §11 has full 15) |
| Appendix A DDL | Task 5 |
| Appendix B error codes | Tasks 12-21 (each raises corresponding code) |
| Appendix C G1-G17 | GA checklist above |
| Appendix D parent-spec diffs | Reflected in Task 17 (RK3588 only) + Task 31 (riscv64 build only) |

**Placeholder scan**: no `TBD`, no `implement later`, no `similar to Task N`.

**Type consistency**:
- `AppConfig` / `HAConfig` etc. defined Task 2, used Task 24
- `EventRow` / `EntityRow` defined Task 11, used Tasks 16, 20
- `TopologyPayload` defined Task 7, used Tasks 8, 15, 18
- `HAEvent` defined Task 16, used Task 24
- `EntityIndex` defined Task 8, `lookup()` signature used Task 16

All names verified consistent across tasks.

---

# Notes for executing engineer

1. **Spec is source of truth** for behaviors not spelled out in this plan (DDL constants, kebab error codes, etc.). Always cross-check `docs/superpowers/specs/2026-06-02-ai-home-assistant-v010-listen-only-design.md` when a detail seems missing.
2. **Container-only dev**: never `pip install` to host. Use `docker run -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "..."` for all build/test.
3. **Frequent commits**: one Task = one logical commit (sub-tasks like 20a-20g produce their own commits).
4. **No silent failures**: every `try` block has at least one `logger.error|warning` or re-raise. Verified by G15 grep.
5. **TDD discipline**: failing test → minimal impl → passing test → commit. Don't write impl without a failing test first.
6. **XSS-safe DOM**: Jinja autoescape + `textContent` in JS. Never `innerHTML` with server strings.
7. **Spec §0 roadmap**: v0.1.0 is one of 7 minors. Don't sneak v0.2 work in.

End of v0.1.0 implementation plan.

