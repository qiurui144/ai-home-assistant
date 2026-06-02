from __future__ import annotations

import json as _json
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, Query

from ai_ha.web.routes import AppState


def build_router(
    state: AppState | None,
    require_admin: Callable[..., Awaitable[None]],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin)])

    @router.get("/topology")
    async def current_topology() -> dict[str, object]:
        if state is None:
            raise HTTPException(503, detail={"error": "topology-not-ready"})
        cur = await state.snapshot_store.get_current()
        if cur is None:
            raise HTTPException(503, detail={"error": "topology-not-ready"})
        return {
            "snapshot_id": cur.snapshot_id,
            "ts": cur.ts_ms,
            "hash": cur.payload_hash,
            "areas_count": len(cur.payload.areas),
            "devices_count": len(cur.payload.devices),
            "entities_count": len(cur.payload.entities),
            "diff_summary": cur.diff_summary,
        }

    @router.get("/topology/snapshots")
    async def list_snapshots(
        limit: int = Query(50, ge=1, le=200),
    ) -> list[dict[str, object]]:
        if state is None:
            return []
        async with state.snapshot_store._db.connect() as c:
            rows = await (await c.execute(
                "SELECT snapshot_id, ts, payload_hash, diff_summary "
                "FROM topology_snapshots ORDER BY snapshot_id DESC LIMIT ?",
                (limit,),
            )).fetchall()
        return [{"snapshot_id": r[0], "ts": r[1], "hash": r[2],
                 "diff_summary": r[3]} for r in rows]

    @router.get("/topology/snapshots/{sid}")
    async def snapshot_detail(sid: int) -> dict[str, object]:
        if state is None:
            raise HTTPException(503, detail={"error": "topology-not-ready"})
        async with state.snapshot_store._db.connect() as c:
            row = await (await c.execute(
                "SELECT snapshot_id, ts, payload_hash, payload, diff_summary "
                "FROM topology_snapshots WHERE snapshot_id=?", (sid,),
            )).fetchone()
        if not row:
            raise HTTPException(404, detail={"error": "not-found"})
        payload = _json.loads(row[3])
        return {
            "snapshot_id": row[0], "ts": row[1], "hash": row[2],
            "payload": payload, "diff_summary": row[4],
        }

    return router
