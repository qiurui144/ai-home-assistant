from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from ai_ha.health import HealthMetrics
from ai_ha.store.dao import AreaRow, StoreDAO
from ai_ha.store.db import Database
from ai_ha.topology import EntityIndex, SnapshotStore
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_chinese_area_name_renders(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    await dao.upsert_areas([AreaRow("kt", "厨房", None, None, "[]", 1, 1, 1)])
    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/rooms", auth=("admin", ts.read()))
        assert "厨房" in r.text
