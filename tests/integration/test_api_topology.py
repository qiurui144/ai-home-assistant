import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from ai_ha.health import HealthMetrics
from ai_ha.store.dao import StoreDAO
from ai_ha.store.db import Database
from ai_ha.topology import EntityIndex, SnapshotStore, TopologyPayload
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_topology_not_ready_returns_503(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "x.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/topology", auth=("admin", ts.read()))
        assert r.status_code == 503


@pytest.mark.asyncio
async def test_current_topology_after_snapshot(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    snap = SnapshotStore(db)
    payload = TopologyPayload(
        areas=[{"area_id": "a1"}], devices=[],
        entities=[{"entity_id": "x"}],
    )
    await snap.insert_if_changed(payload, ts_ms=int(time.time() * 1000))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=snap, entity_index=EntityIndex(),
        health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "x.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/topology", auth=("admin", ts.read()))
        assert r.status_code == 200
        body = r.json()
        assert body["areas_count"] == 1 and body["entities_count"] == 1
