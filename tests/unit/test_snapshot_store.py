from pathlib import Path

import pytest

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
