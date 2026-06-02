from pathlib import Path

import pytest

from ai_ha.ingest.pipeline import HAEvent, IngestPipeline
from ai_ha.privacy.hide_matcher import HideMatcher
from ai_ha.store.dao import AreaRow, EntityRow, StoreDAO
from ai_ha.store.db import Database
from ai_ha.topology.entity_index import EntityIndex
from ai_ha.topology.snapshot_store import TopologyPayload

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
