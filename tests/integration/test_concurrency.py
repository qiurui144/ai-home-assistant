import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from ai_ha.health import HealthMetrics
from ai_ha.store.dao import EventRow, StoreDAO
from ai_ha.store.db import Database
from ai_ha.topology import EntityIndex, SnapshotStore
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
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
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
