"""Orchestrate one topology refresh: snapshot dedup + DAO upsert + entity index rebuild."""
from __future__ import annotations

from ai_ha.store.dao import AreaRow, DeviceRow, EntityRow, StoreDAO
from ai_ha.topology.entity_index import EntityIndex
from ai_ha.topology.snapshot_store import SnapshotStore, TopologyPayload


class TopologyOrchestrator:
    def __init__(
        self, *, snapshot_store: SnapshotStore, entity_index: EntityIndex, dao: StoreDAO,
    ) -> None:
        self._snap = snapshot_store
        self._idx = entity_index
        self._dao = dao

    async def apply(self, payload: TopologyPayload, *, ts_ms: int) -> tuple[int, bool]:
        snapshot_id, is_new = await self._snap.insert_if_changed(payload, ts_ms=ts_ms)
        if is_new:
            await self._upsert_all(payload, snapshot_id=snapshot_id, ts_ms=ts_ms)
        await self._idx.rebuild_async(payload, snapshot_id=snapshot_id)
        return snapshot_id, is_new

    async def _upsert_all(
        self, payload: TopologyPayload, *, snapshot_id: int, ts_ms: int,
    ) -> None:
        await self._dao.upsert_areas([
            AreaRow(
                area_id=a["area_id"], name=a.get("name", a["area_id"]),
                floor_id=a.get("floor_id"), icon=a.get("icon"),
                aliases=str(a.get("aliases", "[]")),
                snapshot_id=snapshot_id, first_seen_at=ts_ms, last_seen_at=ts_ms,
            )
            for a in payload.areas if a.get("area_id")
        ])
        await self._dao.upsert_devices([
            DeviceRow(
                device_id=d["device_id"], name=d.get("name"),
                manufacturer=d.get("manufacturer"), model=d.get("model"),
                area_id=d.get("area_id"), sw_version=d.get("sw_version"),
                snapshot_id=snapshot_id, first_seen_at=ts_ms, last_seen_at=ts_ms,
            )
            for d in payload.devices if d.get("device_id")
        ])
        device_to_area = {d["device_id"]: d.get("area_id") for d in payload.devices}
        await self._dao.upsert_entities([
            EntityRow(
                entity_id=e["entity_id"], friendly_name=e.get("name"),
                domain=e["entity_id"].split(".", 1)[0],
                device_class=e.get("device_class"),
                device_id=e.get("device_id"),
                area_id=e.get("area_id") or device_to_area.get(e.get("device_id")),
                disabled=1 if e.get("disabled_by") else 0,
                snapshot_id=snapshot_id, first_seen_at=ts_ms, last_seen_at=ts_ms,
                event_count_24h=0, total_event_count=0,
            )
            for e in payload.entities if e.get("entity_id")
        ])
