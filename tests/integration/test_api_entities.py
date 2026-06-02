from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from ai_ha.health import HealthMetrics
from ai_ha.store.dao import EntityRow, StoreDAO
from ai_ha.store.db import Database
from ai_ha.topology import EntityIndex, SnapshotStore
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_orphan_filter_returns_only_no_area(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    await dao.upsert_entities([
        EntityRow("orphan.x", None, "sensor", None, None, None, 0, 1, 1, 1, 0, 0),
        EntityRow("attached.x", None, "sensor", None, None, "a1", 0, 1, 1, 1, 0, 0),
    ])
    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "cfg.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/entities?orphan=true", auth=("admin", ts.read()))
        body = r.json()
        assert [e["entity_id"] for e in body] == ["orphan.x"]
