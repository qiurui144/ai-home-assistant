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
        dao=StoreDAO(db),
        snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(),
        health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "cfg.toml",
        hide_pattern=[],
        on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    yield create_app(token_store=ts, state=state, require_auth=False), ts


@pytest.mark.asyncio
async def test_rooms_page_default_english(app_pair):
    app, _ts = app_pair
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/")
        assert r.status_code in (200, 302, 307)
        if r.status_code == 200:
            assert "Rooms" in r.text  # default en


@pytest.mark.asyncio
async def test_lang_switcher_in_base_template(app_pair):
    app, _ts = app_pair
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/")
        # base.html should include lang options
        assert "ai-ha-lang" in r.text or "lang-switcher" in r.text or "?lang=" in r.text
