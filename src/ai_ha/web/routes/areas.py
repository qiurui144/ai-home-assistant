from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException

from ai_ha.web.routes import AppState


def build_router(
    state: AppState | None,
    require_admin: Callable[..., Awaitable[None]],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin)])

    @router.get("/areas")
    async def list_areas() -> list[dict[str, object]]:
        if state is None:
            return []
        rows = await state.dao.list_areas()
        now_hour = int(time.time() * 1000) // 3_600_000
        counters = await state.dao.get_counters_24h(now_hour=now_hour)
        per_area: dict[str, int] = {}
        for (aid, _), n in counters.items():
            per_area[aid] = per_area.get(aid, 0) + n
        active_cutoff = int(time.time() * 1000) - 600_000
        result: list[dict[str, object]] = []
        for r in rows:
            entities = await state.dao.list_entities(area_id=r.area_id)
            class_dist: dict[str, int] = {}
            last_seen_max = 0
            for e in entities:
                if e.device_class:
                    class_dist[e.device_class] = class_dist.get(e.device_class, 0) + 1
                last_seen_max = max(last_seen_max, e.last_seen_at)
            result.append({
                "area_id": r.area_id, "name": r.name, "floor_id": r.floor_id,
                "events_per_hour_24h": per_area.get(r.area_id, 0),
                "device_class_distribution": class_dist,
                "is_active": last_seen_max > active_cutoff,
                "active_since": last_seen_max if last_seen_max > active_cutoff else None,
                "entity_count": len(entities),
            })
        return result

    @router.get("/areas/{area_id}")
    async def area_detail(area_id: str) -> dict[str, object]:
        if state is None:
            raise HTTPException(404, detail={"error": "not-found"})
        areas = await state.dao.list_areas()
        match = next((a for a in areas if a.area_id == area_id), None)
        if not match:
            raise HTTPException(404, detail={"error": "not-found"})
        entities = await state.dao.list_entities(area_id=area_id)
        recent = await state.dao.list_events(area_id=area_id, limit=50)
        return {
            "area": {"area_id": match.area_id, "name": match.name, "floor_id": match.floor_id},
            "entities": [{"entity_id": e.entity_id, "friendly_name": e.friendly_name,
                          "device_class": e.device_class, "last_seen": e.last_seen_at}
                         for e in entities],
            "recent_events": [
                {"ts": ev.ts, "entity_id": ev.entity_id, "event_type": ev.event_type,
                 "old_state": ev.old_state, "new_state": ev.new_state}
                for ev in recent
            ],
        }

    @router.get("/areas/{area_id}/entities")
    async def area_entities(area_id: str) -> list[dict[str, object]]:
        if state is None:
            return []
        ents = await state.dao.list_entities(area_id=area_id)
        return [{"entity_id": e.entity_id, "friendly_name": e.friendly_name,
                 "device_class": e.device_class, "last_seen": e.last_seen_at,
                 "event_count_24h": e.event_count_24h} for e in ents]

    return router
