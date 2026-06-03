from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from ai_ha.health import HealthMetrics
from ai_ha.store.dao import AreaRow, EntityRow, EventRow, StoreDAO
from ai_ha.store.db import Database
from ai_ha.topology import EntityIndex, SnapshotStore
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_dashboard_returns_health_rooms_events(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    await dao.upsert_areas([AreaRow("living", "Living", None, None, "[]", 1, 1000, 1000)])
    await dao.upsert_entities([EntityRow(
        "light.x", "L", "light", "light", None, "living", 0, 1, 1000, 1000, 3, 3,
    )])
    await dao.insert_events([EventRow(
        1000, 1001, "light.x", "state_changed", None, '"on"',
        None, None, "living", None, "light", 1,
    )])
    health = HealthMetrics(install_start_ms=0)
    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=health,
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/dashboard", auth=("admin", ts.read()))
        assert r.status_code == 200
        body = r.json()
        assert "health" in body and "rooms" in body and "recent_events" in body
        assert len(body["rooms"]) == 1
        assert body["rooms"][0]["area_id"] == "living"
        assert body["rooms"][0]["entity_count"] == 1
        assert len(body["recent_events"]) == 1


@pytest.mark.asyncio
async def test_dashboard_empty_when_no_data(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/dashboard", auth=("admin", ts.read()))
        assert r.status_code == 200
        body = r.json()
        assert body["rooms"] == []
        assert body["recent_events"] == []


@pytest.mark.asyncio
async def test_dashboard_requires_auth(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    app = create_app(token_store=ts, state=state, require_auth=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/dashboard")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_recent_events_capped_at_50(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    await dao.insert_events([EventRow(
        i, i, "x", "state_changed", None, '"on"',
        None, None, None, None, None, 1,
    ) for i in range(100)])
    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    app = create_app(token_store=ts, state=state, require_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/dashboard")
        body = r.json()
        assert len(body["recent_events"]) == 50
