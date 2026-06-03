import asyncio
from pathlib import Path

import pytest

from ai_ha.ingest.pipeline import HAEvent, IngestPipeline
from ai_ha.privacy.hide_matcher import HideMatcher
from ai_ha.store.dao import AreaRow, EntityRow, StoreDAO
from ai_ha.store.db import Database
from ai_ha.topology.entity_index import EntityIndex
from ai_ha.topology.snapshot_store import TopologyPayload
from ai_ha.web.routes.stream import EventBroadcaster

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.fixture
async def setup(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    payload = TopologyPayload(
        areas=[{"area_id": "living"}],
        devices=[{"device_id": "d1", "area_id": "living"}],
        entities=[{"entity_id": "light.a", "device_id": "d1"}],
    )
    idx = EntityIndex.build_from_payload(payload, snapshot_id=1)
    await dao.upsert_areas([AreaRow("living", "Living", None, None, "[]", 1, 1, 1)])
    await dao.upsert_entities([EntityRow(
        "light.a", "A", "light", "light", "d1", "living", 0, 1, 1, 1, 0, 0,
    )])
    bc = EventBroadcaster()
    yield dao, idx, bc


@pytest.mark.asyncio
async def test_pipeline_publishes_room_state_on_commit(setup):
    dao, idx, bc = setup
    received: list[dict] = []

    async def listener() -> None:
        async for ev in bc.subscribe():
            received.append(ev)
            if len(received) >= 1:
                return

    listener_task = asyncio.create_task(listener())
    await asyncio.sleep(0.05)

    pipe = IngestPipeline(
        dao=dao, entity_index=idx, hide_matcher=HideMatcher([]),
        batch_size=1, batch_interval_ms=10_000, broadcaster=bc,
    )
    await pipe.start()
    await pipe.submit(HAEvent(
        ts_ms=1_700_000_000_000, entity_id="light.a",
        event_type="state_changed", old_state=None, new_state='"on"',
        context_user_id=None, context_parent_id=None,
    ))
    await pipe.flush()
    await asyncio.wait_for(listener_task, timeout=1.0)
    room_states = [e for e in received if e.get("type") == "room_state"]
    assert len(room_states) == 1
    assert room_states[0]["area_id"] == "living"
    assert room_states[0]["active"] is True
    await pipe.stop()


@pytest.mark.asyncio
async def test_pipeline_throttles_room_state_per_second(setup):
    dao, idx, bc = setup
    received: list[dict] = []

    async def listener() -> None:
        async for ev in bc.subscribe():
            received.append(ev)

    listener_bg = asyncio.create_task(listener())
    await asyncio.sleep(0.05)

    pipe = IngestPipeline(
        dao=dao, entity_index=idx, hide_matcher=HideMatcher([]),
        batch_size=1, batch_interval_ms=10_000, broadcaster=bc,
    )
    await pipe.start()
    # 5 events fast → only 1 room_state for the area within the 1-sec window
    for i in range(5):
        await pipe.submit(HAEvent(
            ts_ms=1_700_000_000_000 + i, entity_id="light.a",
            event_type="state_changed", old_state=None, new_state='"on"',
            context_user_id=None, context_parent_id=None,
        ))
    await pipe.flush()
    await asyncio.sleep(0.1)
    listener_bg.cancel()
    room_states = [
        e for e in received
        if e.get("type") == "room_state" and e.get("area_id") == "living"
    ]
    assert len(room_states) == 1, f"expected 1 throttled room_state, got {len(room_states)}"
    await pipe.stop()
