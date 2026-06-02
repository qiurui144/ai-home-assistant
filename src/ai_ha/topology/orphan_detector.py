"""Detect entities with no area attribution (neither direct nor via device)."""
from __future__ import annotations

from ai_ha.topology.snapshot_store import TopologyPayload


def find_orphans(payload: TopologyPayload) -> list[str]:
    device_to_area = {
        d["device_id"]: d.get("area_id") for d in payload.devices if "device_id" in d
    }
    orphans: list[str] = []
    for e in payload.entities:
        if e.get("disabled_by"):
            continue
        if e.get("area_id"):
            continue
        if e.get("device_id") and device_to_area.get(e["device_id"]):
            continue
        if eid := e.get("entity_id"):
            orphans.append(eid)
    return orphans
