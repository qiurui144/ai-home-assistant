from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Query

from ai_ha.web.routes import AppState


def build_router(
    state: AppState | None,
    require_admin: Callable[..., Awaitable[None]],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin)])

    @router.get("/entities")
    async def list_entities(
        area_id: str | None = None,
        orphan: bool = False,
        device_class: str | None = None,
        limit: int = Query(100, ge=1, le=1000),
    ) -> list[dict[str, object]]:
        if state is None:
            return []
        rows = await state.dao.list_entities(
            area_id=area_id, orphan=orphan, device_class=device_class, limit=limit,
        )
        return [{
            "entity_id": r.entity_id, "friendly_name": r.friendly_name,
            "domain": r.domain, "device_class": r.device_class,
            "device_id": r.device_id, "area_id": r.area_id,
            "disabled": bool(r.disabled), "snapshot_id": r.snapshot_id,
            "last_seen": r.last_seen_at, "event_count_24h": r.event_count_24h,
            "total_event_count": r.total_event_count,
        } for r in rows]

    @router.get("/entities/{entity_id}/events")
    async def entity_events(
        entity_id: str, limit: int = Query(100, ge=1, le=1000),
        cursor: int | None = None,
    ) -> list[dict[str, object]]:
        if state is None:
            return []
        rows = await state.dao.list_events(
            entity_id=entity_id, cursor=cursor, limit=limit,
        )
        return [{
            "ts": r.ts, "received_at": r.received_at,
            "event_type": r.event_type, "old_state": r.old_state,
            "new_state": r.new_state, "context_user_id": r.context_user_id,
        } for r in rows]

    return router
