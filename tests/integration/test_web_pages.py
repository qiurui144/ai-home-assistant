from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from ai_ha.health import HealthMetrics
from ai_ha.store.dao import StoreDAO
from ai_ha.store.db import Database
from ai_ha.topology import EntityIndex, SnapshotStore
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest_asyncio.fixture
async def app_pair(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "cfg.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    yield create_app(token_store=ts, state=state), ts


@pytest.mark.asyncio
async def test_rooms_renders(app_pair):
    app, ts = app_pair
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/", auth=("admin", ts.read()))
        assert r.status_code == 200
        assert "<h1>Rooms</h1>" in r.text


@pytest.mark.asyncio
async def test_entities_renders(app_pair):
    app, ts = app_pair
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/entities", auth=("admin", ts.read()))
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_settings_renders(app_pair):
    app, ts = app_pair
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/settings", auth=("admin", ts.read()))
        assert r.status_code == 200
