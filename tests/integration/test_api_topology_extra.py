"""Additional topology API coverage: snapshots list + detail 404 + payload body."""
from __future__ import annotations

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


async def _make_app(tmp_path, snap: SnapshotStore | None = None):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    snap = snap or SnapshotStore(db)
    state = AppState(
        dao=StoreDAO(db),
        snapshot_store=snap,
        entity_index=EntityIndex(),
        health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "x.toml",
        hide_pattern=[],
        on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    return create_app(token_store=ts, state=state), ts, db


@pytest.mark.asyncio
async def test_snapshots_list_returns_inserted_rows(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    snap = SnapshotStore(db)
    await snap.insert_if_changed(
        TopologyPayload(areas=[{"area_id": "a"}], devices=[], entities=[]),
        ts_ms=int(time.time() * 1000),
    )
    await snap.insert_if_changed(
        TopologyPayload(areas=[{"area_id": "b"}], devices=[], entities=[]),
        ts_ms=int(time.time() * 1000) + 1,
    )
    state = AppState(
        dao=StoreDAO(db),
        snapshot_store=snap,
        entity_index=EntityIndex(),
        health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "x.toml",
        hide_pattern=[],
        on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    app = create_app(token_store=ts, state=state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/topology/snapshots", auth=("admin", ts.read()))
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        assert len(body) >= 2
        # Most recent first
        assert body[0]["snapshot_id"] > body[1]["snapshot_id"]


@pytest.mark.asyncio
async def test_snapshots_list_empty_when_no_snapshots(tmp_path):
    app, ts, _ = await _make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/topology/snapshots", auth=("admin", ts.read()))
        assert r.status_code == 200
        assert r.json() == []


@pytest.mark.asyncio
async def test_snapshot_detail_404_for_unknown_id(tmp_path):
    app, ts, _ = await _make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/topology/snapshots/9999", auth=("admin", ts.read()))
        assert r.status_code == 404
        assert r.json()["detail"]["error"] == "not-found"


@pytest.mark.asyncio
async def test_snapshot_detail_returns_full_payload(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    snap = SnapshotStore(db)
    sid, _ = await snap.insert_if_changed(
        TopologyPayload(areas=[{"area_id": "kitchen"}], devices=[], entities=[]),
        ts_ms=int(time.time() * 1000),
    )
    state = AppState(
        dao=StoreDAO(db),
        snapshot_store=snap,
        entity_index=EntityIndex(),
        health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "x.toml",
        hide_pattern=[],
        on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    app = create_app(token_store=ts, state=state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get(f"/api/v1/topology/snapshots/{sid}", auth=("admin", ts.read()))
        assert r.status_code == 200
        body = r.json()
        assert body["snapshot_id"] == sid
        assert "payload" in body
        assert body["payload"]["areas"][0]["area_id"] == "kitchen"
