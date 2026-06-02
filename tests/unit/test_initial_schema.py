from pathlib import Path

import pytest

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
