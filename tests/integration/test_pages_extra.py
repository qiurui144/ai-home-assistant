"""Additional pages route coverage: room redirect, room render, timeline, settings pattern."""
from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from ai_ha.health import HealthMetrics
from ai_ha.store.dao import AreaRow, EventRow, StoreDAO
from ai_ha.store.db import Database
from ai_ha.topology import EntityIndex, SnapshotStore
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


async def _make_app(tmp_path, *, hide_pattern: list[str] | None = None):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    state = AppState(
        dao=dao,
        snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(),
        health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "cfg.toml",
        hide_pattern=hide_pattern or [],
        on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    return create_app(token_store=ts, state=state), ts, dao


@pytest.mark.asyncio
async def test_room_redirects_for_unknown_area(tmp_path):
    app, ts, _ = await _make_app(tmp_path)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://x",
        follow_redirects=False,
    ) as c:
        r = await c.get("/room/does-not-exist", auth=("admin", ts.read()))
        # Redirect to /
        assert r.status_code in (301, 302, 307, 308)
        assert r.headers["location"] in ("/", "http://x/")


@pytest.mark.asyncio
async def test_room_renders_for_known_area(tmp_path):
    app, ts, dao = await _make_app(tmp_path)
    await dao.upsert_areas([
        AreaRow(
            area_id="living",
            name="Living Room",
            floor_id=None,
            icon=None,
            aliases="[]",
            snapshot_id=1,
            first_seen_at=1000,
            last_seen_at=1000,
        )
    ])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/room/living", auth=("admin", ts.read()))
        assert r.status_code == 200
        assert "Living Room" in r.text


@pytest.mark.asyncio
async def test_timeline_renders_with_events(tmp_path):
    app, ts, dao = await _make_app(tmp_path)
    await dao.insert_events([
        EventRow(
            ts=1_000_000,
            received_at=1_000_001,
            entity_id="light.hall",
            event_type="state_changed",
            old_state=None,
            new_state='"on"',
            context_user_id=None,
            context_parent_id=None,
            area_id=None,
            device_id=None,
            device_class=None,
            snapshot_id=1,
        )
    ])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/timeline", auth=("admin", ts.read()))
        assert r.status_code == 200
        assert "Timeline" in r.text


@pytest.mark.asyncio
async def test_timeline_renders_empty(tmp_path):
    app, ts, _ = await _make_app(tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/timeline", auth=("admin", ts.read()))
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_settings_shows_hide_pattern(tmp_path):
    app, ts, _ = await _make_app(tmp_path, hide_pattern=[r"sensor\.bank_.*"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/settings", auth=("admin", ts.read()))
        assert r.status_code == 200
        # The pattern text must appear somewhere in the rendered page
        assert "sensor" in r.text


@pytest.mark.asyncio
async def test_settings_renders_empty_pattern(tmp_path):
    app, ts, _ = await _make_app(tmp_path, hide_pattern=[])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/settings", auth=("admin", ts.read()))
        assert r.status_code == 200
