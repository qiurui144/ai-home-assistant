import textwrap
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
async def app_with_cfg(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text(textwrap.dedent("""
        [ha]
        url = "http://x"
        token = "t"
        [privacy]
        hide_entities_pattern = []
    """))
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=cfg, hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    yield create_app(token_store=ts, state=state), ts, cfg


@pytest.mark.asyncio
async def test_post_privacy_writes_config(app_with_cfg):
    app, ts, cfg_path = app_with_cfg
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.post(
            "/api/v1/settings/privacy",
            auth=("admin", ts.read()),
            json={"hide_entities_pattern": [r"sensor\.bank_.*"]},
        )
        assert r.status_code == 200
    assert "sensor" in cfg_path.read_text()


@pytest.mark.asyncio
async def test_post_invalid_regex_returns_422(app_with_cfg):
    app, ts, _ = app_with_cfg
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.post(
            "/api/v1/settings/privacy",
            auth=("admin", ts.read()),
            json={"hide_entities_pattern": ["(a+)+b"]},
        )
        assert r.status_code == 422
        assert r.json()["detail"]["error"] == "hide-pattern-invalid"
