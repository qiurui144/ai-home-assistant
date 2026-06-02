from __future__ import annotations

import time

from fastapi import APIRouter

from ai_ha.web.routes import AppState


def build_router(state: AppState | None) -> APIRouter:
    router = APIRouter()

    @router.get("/api/health")
    async def health() -> dict[str, object]:
        if state is None:
            return {"status": "healthy", "uptime_seconds": 0}
        return state.health.snapshot(now_ms=int(time.time() * 1000))

    return router
