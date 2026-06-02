import asyncio
from pathlib import Path

import pytest

from ai_ha.store.dao import EventRow, StoreDAO
from ai_ha.store.db import Database

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_lock_storm_recovers(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)

    async def w(i: int) -> None:
        for _ in range(20):
            await dao.insert_events([EventRow(
                i, i, "x", "state_changed", None, None, None, None,
                None, None, None, 1,
            )])

    await asyncio.gather(*[w(i) for i in range(50)])
    rows = await dao.list_events(limit=2000)
    assert len(rows) == 1000  # no lock loss
