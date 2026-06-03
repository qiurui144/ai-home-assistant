"""Test responsive design: CSS breakpoints + template classes present."""
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
    """Setup app with in-memory database for testing."""
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db),
        snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(),
        health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml",
        hide_pattern=[],
        on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    yield create_app(token_store=ts, state=state), ts


@pytest.mark.asyncio
async def test_dashboard_responsive_classes_present(app_pair):
    """Verify the breakpoint-driving CSS classes are emitted by the template.

    Tests that /dashboard contains all necessary responsive layout classes:
    - health-strip: metric chips responsive grid
    - dashboard-grid: main layout (single col mobile, 2-col tablet+)
    - rooms-panel: room list container
    - events-panel: event stream sidebar
    - room-grid: room cards responsive grid
    """
    app, ts = app_pair
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://x"
    ) as c:
        r = await c.get("/dashboard", auth=("admin", ts.read()))
        assert r.status_code == 200

        # Verify all responsive layout classes are in the rendered HTML
        required_classes = [
            "health-strip",
            "dashboard-grid",
            "rooms-panel",
            "events-panel",
            "room-grid",
        ]
        for cls in required_classes:
            assert cls in r.text, f"class '{cls}' missing from /dashboard HTML"


@pytest.mark.asyncio
async def test_css_has_breakpoints(tmp_path):
    """Verify app.css contains the 3 breakpoint media queries.

    Tests mobile-first approach:
    - @media (min-width: 480px): tablet layout
    - @media (min-width: 768px): larger tablet/small laptop
    - @media (min-width: 1100px): desktop
    """
    css_path = (
        Path(__file__).parent.parent.parent
        / "src/ai_ha/web/static/app.css"
    )
    body = css_path.read_text()

    breakpoints = [
        "@media (min-width: 480px)",
        "@media (min-width: 768px)",
        "@media (min-width: 1100px)",
    ]
    for bp in breakpoints:
        assert bp in body, f"breakpoint '{bp}' missing from app.css"
