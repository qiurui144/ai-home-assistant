"""Ingest pipeline p99 latency benchmark — target G3: < 100ms per event."""
import time
from pathlib import Path

import pytest

from ai_ha.ingest.pipeline import HAEvent, IngestPipeline
from ai_ha.privacy import HideMatcher
from ai_ha.store.dao import StoreDAO
from ai_ha.store.db import Database
from ai_ha.topology import EntityIndex, TopologyPayload

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_ingest_1k_events_p99_under_100ms(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    payload = TopologyPayload(
        areas=[{"area_id": "a"}], devices=[],
        entities=[{"entity_id": "e", "area_id": "a"}],
    )
    idx = EntityIndex.build_from_payload(payload, snapshot_id=1)
    pipe = IngestPipeline(
        dao=StoreDAO(db), entity_index=idx, hide_matcher=HideMatcher([]),
        batch_size=100, batch_interval_ms=1000,
    )
    await pipe.start()

    times: list[float] = []
    for i in range(1000):
        t0 = time.perf_counter()
        await pipe.submit(HAEvent(
            ts_ms=i, entity_id="e", event_type="state_changed",
            old_state=None, new_state='"on"',
            context_user_id=None, context_parent_id=None,
        ))
        times.append(time.perf_counter() - t0)
    await pipe.flush()

    times.sort()
    p50 = times[500]
    p95 = times[950]
    p99 = times[990]
    print(f"\ningest: p50={p50*1000:.2f}ms p95={p95*1000:.2f}ms p99={p99*1000:.2f}ms")
    assert p99 < 0.1, f"p99={p99*1000:.1f}ms exceeds 100ms (G3)"
    await pipe.stop()
