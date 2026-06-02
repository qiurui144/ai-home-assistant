import time
from pathlib import Path

import pytest

from ai_ha.store.dao import StoreDAO
from ai_ha.store.db import Database
from ai_ha.topology.entity_index import EntityIndex
from ai_ha.topology.orchestrator import TopologyOrchestrator
from ai_ha.topology.snapshot_store import SnapshotStore, TopologyPayload

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
