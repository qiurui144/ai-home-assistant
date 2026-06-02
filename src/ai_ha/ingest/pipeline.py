"""5-step ingest: enrich → privacy → entity upsert → event insert → counter bump.

Batch policy: commit when either batch_size events accumulated or batch_interval_ms
elapsed since first uncommitted event. Background flush task wakes every 100 ms to
check interval. submit() blocks only on the in-mem queue (unbounded for v0.1.0;
spec §11 risk 11 accepts SIGKILL data loss for now).
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from ai_ha.ingest.counters import HourBucketRing
from ai_ha.privacy.hide_matcher import HideMatcher
from ai_ha.store.dao import EventRow, StoreDAO
from ai_ha.topology.entity_index import EntityIndex

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HAEvent:
    ts_ms: int
    entity_id: str
    event_type: str
    old_state: str | None
    new_state: str | None
    context_user_id: str | None
    context_parent_id: str | None


class IngestPipeline:
    def __init__(
        self, *, dao: StoreDAO, entity_index: EntityIndex,
        hide_matcher: HideMatcher,
        batch_size: int = 100, batch_interval_ms: int = 1000,
    ) -> None:
        self._dao = dao
        self._idx = entity_index
        self._hide = hide_matcher
        self._batch_size = batch_size
        self._batch_interval = batch_interval_ms / 1000.0
        self._buffer: list[tuple[HAEvent, int]] = []  # (event, snapshot_id)
        self._first_added: float | None = None
        self._ring = HourBucketRing()
        self._lock = asyncio.Lock()
        self._stop = asyncio.Event()
        self._flush_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def stop(self) -> None:
        self._stop.set()
        if self._flush_task:
            await self._flush_task
        await self.flush()

    async def submit(self, event: HAEvent) -> None:
        ref = self._idx.lookup(event.entity_id)
        if ref and self._hide.matches(event.entity_id):
            bucket = self._ring.now_bucket()
            await self._dao.increment_privacy_drop(hour_bucket_utc=bucket, by=1)
            return
        if not ref and self._hide.matches(event.entity_id):
            # also drop for unknown entities (defense in depth)
            bucket = self._ring.now_bucket()
            await self._dao.increment_privacy_drop(hour_bucket_utc=bucket, by=1)
            return
        snapshot_id = ref.snapshot_id if ref else 0
        async with self._lock:
            self._buffer.append((event, snapshot_id))
            if self._first_added is None:
                self._first_added = time.monotonic()
            if len(self._buffer) >= self._batch_size:
                await self._commit_locked()

    async def flush(self) -> None:
        async with self._lock:
            await self._commit_locked()

    async def _commit_locked(self) -> None:
        if not self._buffer:
            return
        received_at = int(time.time() * 1000)
        rows: list[EventRow] = []
        per_area: dict[tuple[str, int], int] = {}
        per_entity_last: dict[str, int] = {}
        for ev, sid in self._buffer:
            ref = self._idx.lookup(ev.entity_id)
            area_id = ref.area_id if ref else None
            device_id = ref.device_id if ref else None
            device_class = ref.device_class if ref else None
            rows.append(EventRow(
                ts=ev.ts_ms, received_at=received_at, entity_id=ev.entity_id,
                event_type=ev.event_type, old_state=ev.old_state,
                new_state=ev.new_state, context_user_id=ev.context_user_id,
                context_parent_id=ev.context_parent_id,
                area_id=area_id, device_id=device_id, device_class=device_class,
                snapshot_id=sid,
            ))
            if area_id:
                key = (area_id, self._ring.bucket_for(ev.ts_ms))
                per_area[key] = per_area.get(key, 0) + 1
            per_entity_last[ev.entity_id] = ev.ts_ms
        await self._dao.insert_events(rows)
        for (aid, bucket), n in per_area.items():
            await self._dao.increment_counter(aid, hour_bucket_utc=bucket, by=n)
        for eid, last_ts in per_entity_last.items():
            await self._dao.bump_entity_event_counts(entity_id=eid, last_seen_at=last_ts)
        self._buffer.clear()
        self._first_added = None

    async def _periodic_flush(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=0.1)
                return
            except TimeoutError:
                pass
            async with self._lock:
                if self._first_added is None:
                    continue
                if time.monotonic() - self._first_added >= self._batch_interval:
                    await self._commit_locked()
