from pathlib import Path

import pytest

from ai_ha.store.dao import AreaRow, EntityRow, EventRow, StoreDAO
from ai_ha.store.db import Database

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
