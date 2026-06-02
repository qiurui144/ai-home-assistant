"""API p99 latency benchmark — target G10: /api/health < 50ms, /api/v1/areas < 200ms."""
import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from ai_ha.health import HealthMetrics
from ai_ha.store.dao import AreaRow, EntityRow, StoreDAO
from ai_ha.store.db import Database
from ai_ha.topology import EntityIndex, SnapshotStore
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_health_p99_under_50ms(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t"))
    ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    times: list[float] = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        for _ in range(500):
            t0 = time.perf_counter()
            r = await c.get("/api/health")
            times.append(time.perf_counter() - t0)
            assert r.status_code == 200
    times.sort()
    p99 = times[494]
    print(f"\n/api/health p99={p99*1000:.2f}ms")
    assert p99 < 0.05, f"p99={p99*1000:.1f}ms exceeds 50ms (G10)"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_areas_p99_under_200ms(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    # seed 10 areas + 50 entities so /areas does meaningful work
    for i in range(10):
        await dao.upsert_areas([
            AreaRow(f"a{i}", f"Area {i}", None, None, "[]", 1, 1000, 1000),
        ])
    for i in range(50):
        await dao.upsert_entities([EntityRow(
            f"e{i}", None, "sensor", "temperature",
            None, f"a{i % 10}", 0, 1, 1000, 1000, 0, 0,
        )])

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
        for _ in range(200):
            t0 = time.perf_counter()
            r = await c.get("/api/v1/areas", auth=("admin", ts.read()))
            times.append(time.perf_counter() - t0)
            assert r.status_code == 200
    times.sort()
    p99 = times[197]
    print(f"\n/api/v1/areas p99={p99*1000:.2f}ms")
    assert p99 < 0.2, f"p99={p99*1000:.1f}ms exceeds 200ms (G10)"
