"""Dashboard p99 < 300ms benchmark (vG3)."""
import time
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


@pytest.mark.slow
@pytest.mark.asyncio
async def test_dashboard_p99_under_300ms(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    # seed: 15 rooms, 100 entities, 500 events
    for i in range(15):
        await dao.upsert_areas([
            AreaRow(f"a{i}", f"Area {i}", None, None, "[]", 1, 1000, 1000),
        ])
    for i in range(100):
        await dao.upsert_entities([EntityRow(
            f"e{i}", None, "sensor", "temperature",
            None, f"a{i % 15}", 0, 1, 1000, 1000, 0, 0,
        )])
    await dao.insert_events([EventRow(
        i, i, f"e{i % 100}", "state_changed", None, '"on"',
        None, None, f"a{i % 15}", None, None, 1,
    ) for i in range(500)])

    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    times: list[float] = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        for _ in range(100):
            t0 = time.perf_counter()
            r = await c.get("/api/v1/dashboard", auth=("admin", ts.read()))
            times.append(time.perf_counter() - t0)
            assert r.status_code == 200
    times.sort()
    p99 = times[98]
    print(f"\n/api/v1/dashboard p99={p99*1000:.2f}ms")
    assert p99 < 0.3, f"p99={p99*1000:.1f}ms exceeds 300ms (vG3)"
