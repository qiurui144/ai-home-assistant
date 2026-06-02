"""In-memory entity → (device, area, device_class) cache.

Read path is lock-free (atomic dict-pointer swap on rebuild). Write path holds a
single asyncio lock during rebuild. Each lookup returns the snapshot_id active at
build time so the ingest pipeline can stamp events.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ai_ha.topology.snapshot_store import TopologyPayload


@dataclass(frozen=True)
class EntityRef:
    device_id: str | None
    area_id: str | None
    device_class: str | None
    snapshot_id: int


class EntityIndex:
    def __init__(self) -> None:
        self._map: dict[str, EntityRef] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def build_from_payload(cls, payload: TopologyPayload, *, snapshot_id: int) -> EntityIndex:
        idx = cls()
        idx._map = _build(payload, snapshot_id)
        return idx

    def lookup(self, entity_id: str) -> EntityRef | None:
        return self._map.get(entity_id)

    def rebuild_from_payload(self, payload: TopologyPayload, *, snapshot_id: int) -> None:
        new_map = _build(payload, snapshot_id)
        self._map = new_map  # atomic pointer swap

    async def rebuild_async(self, payload: TopologyPayload, *, snapshot_id: int) -> None:
        async with self._lock:
            self.rebuild_from_payload(payload, snapshot_id=snapshot_id)


def _build(payload: TopologyPayload, snapshot_id: int) -> dict[str, EntityRef]:
    device_to_area = {
        d["device_id"]: d.get("area_id") for d in payload.devices if "device_id" in d
    }
    out: dict[str, EntityRef] = {}
    for e in payload.entities:
        eid = e.get("entity_id")
        if not eid:
            continue
        dev_id = e.get("device_id")
        area_id = e.get("area_id") or device_to_area.get(dev_id)
        out[eid] = EntityRef(
            device_id=dev_id,
            area_id=area_id,
            device_class=e.get("device_class"),
            snapshot_id=snapshot_id,
        )
    return out
