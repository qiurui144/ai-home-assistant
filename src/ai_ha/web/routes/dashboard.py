"""GET /api/v1/dashboard — single-endpoint aggregator for the home dashboard."""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends

from ai_ha.web.routes import AppState


def build_router(
    state: AppState | None,
    require_admin: Callable[..., Awaitable[None]],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin)])

    @router.get("/dashboard")
    async def dashboard() -> dict[str, object]:
        if state is None:
            return {"health": {}, "rooms": [], "recent_events": []}
        now_ms = int(time.time() * 1000)
        now_hour = now_ms // 3_600_000
        health = state.health.snapshot(now_ms=now_ms)
        areas = await state.dao.list_areas()
        counters = await state.dao.get_counters_24h(now_hour=now_hour)
        per_area: dict[str, int] = {}
        for (aid, _), n in counters.items():
            per_area[aid] = per_area.get(aid, 0) + n
        active_cutoff = now_ms - 600_000  # 10 min
        rooms = []
        for r in areas:
            entities = await state.dao.list_entities(area_id=r.area_id)
            class_dist: dict[str, int] = {}
            last_seen_max = 0
            for e in entities:
                if e.device_class:
                    class_dist[e.device_class] = class_dist.get(e.device_class, 0) + 1
                last_seen_max = max(last_seen_max, e.last_seen_at)
            rooms.append({
                "area_id": r.area_id, "name": r.name, "floor_id": r.floor_id,
                "entity_count": len(entities),
                "device_class_distribution": class_dist,
                "events_per_hour_24h": per_area.get(r.area_id, 0),
                "last_seen": last_seen_max,
                "active": last_seen_max > active_cutoff,
            })
        recent = await state.dao.list_events(limit=50)
        return {
            "health": health,
            "rooms": rooms,
            "recent_events": [{
                "ts": e.ts, "entity_id": e.entity_id,
                "event_type": e.event_type, "area_id": e.area_id,
                "old_state": e.old_state, "new_state": e.new_state,
            } for e in recent],
        }

    return router
