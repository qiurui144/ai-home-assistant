from pathlib import Path

import pytest

from ai_ha.store.dao import EntityRow, EventRow, StoreDAO
from ai_ha.store.db import Database

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
        1000, 1001, "light.\U0001f6cb️_main", "state_changed", None, '"on"',
        None, None, "客厅", None, "light", 1,
    )])
    rows = await dao.list_events(limit=10)
    assert rows[0].entity_id == "light.\U0001f6cb️_main"
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
