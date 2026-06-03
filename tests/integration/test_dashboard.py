from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from ai_ha.health import HealthMetrics
from ai_ha.store.dao import StoreDAO
from ai_ha.store.db import Database
from ai_ha.topology import EntityIndex, SnapshotStore
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.fixture
async def app_pair(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    yield create_app(token_store=ts, state=state), ts


@pytest.mark.asyncio
async def test_root_redirects_to_dashboard(app_pair):
    app, ts = app_pair
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://x", follow_redirects=False,
    ) as c:
        r = await c.get("/", auth=("admin", ts.read()))
        assert r.status_code in (302, 307)
        assert "/dashboard" in r.headers.get("location", "")


@pytest.mark.asyncio
async def test_dashboard_page_renders(app_pair):
    app, ts = app_pair
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/dashboard", auth=("admin", ts.read()))
        assert r.status_code == 200
        assert "Dashboard" in r.text or "dashboard" in r.text.lower()
