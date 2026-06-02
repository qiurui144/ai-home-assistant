from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, Query

from ai_ha.web.routes import AppState


def build_router(
    state: AppState | None,
    require_admin: Callable[..., Awaitable[None]],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin)])

    @router.get("/events")
    async def list_events(
        since: int | None = None, until: int | None = None,
        area_id: str | None = None, entity_id: str | None = None,
        limit: int = Query(100, ge=1, le=1000),
        cursor: str | None = None,
    ) -> dict[str, object]:
        if state is None:
            return {"events": [], "next_cursor": None}
        cursor_int: int | None = None
        if cursor is not None:
            try:
                cursor_int = int(cursor)
            except ValueError as exc:
                raise HTTPException(400, detail={"error": "bad-cursor"}) from exc
        rows = await state.dao.list_events(
            entity_id=entity_id, area_id=area_id,
            since_ts=since, until_ts=until,
            cursor=cursor_int, limit=limit,
        )
        return {
            "events": [{
                "ts": r.ts, "received_at": r.received_at,
                "entity_id": r.entity_id, "event_type": r.event_type,
                "old_state": r.old_state, "new_state": r.new_state,
                "area_id": r.area_id, "device_class": r.device_class,
            } for r in rows],
            "next_cursor": str(rows[-1].ts) if rows and len(rows) == limit else None,
        }

    return router
