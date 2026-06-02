import asyncio
from pathlib import Path

import pytest

from ai_ha.store.dao import EventRow, StoreDAO
from ai_ha.store.db import Database

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
