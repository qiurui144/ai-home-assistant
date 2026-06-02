"""Server-side rendered HTML pages."""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ai_ha.web.routes import AppState

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
templates.env.filters["tstoiso"] = lambda ms: datetime.fromtimestamp(
    ms / 1000.0, tz=UTC,
).isoformat()


def build_pages_router(
    state: AppState | None,
    require_admin: Callable[..., Awaitable[None]],
) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_admin)])

    @router.get("/", response_class=HTMLResponse)
    async def rooms(request: Request) -> HTMLResponse:
        if state is None:
            return templates.TemplateResponse(request, "rooms.html", {"areas": []})
        rows = await state.dao.list_areas()
        now_hour = int(time.time() * 1000) // 3_600_000
        counters = await state.dao.get_counters_24h(now_hour=now_hour)
        per_area: dict[str, int] = {}
        for (aid, _), n in counters.items():
            per_area[aid] = per_area.get(aid, 0) + n
        active_cutoff = int(time.time() * 1000) - 600_000
        areas_out = []
        for r in rows:
            ents = await state.dao.list_entities(area_id=r.area_id)
            class_dist: dict[str, int] = {}
            last_seen_max = 0
            for e in ents:
                if e.device_class:
                    class_dist[e.device_class] = class_dist.get(e.device_class, 0) + 1
                last_seen_max = max(last_seen_max, e.last_seen_at)
            areas_out.append({
                "area_id": r.area_id, "name": r.name,
                "events_per_hour_24h": per_area.get(r.area_id, 0),
                "device_class_distribution": class_dist,
                "is_active": last_seen_max > active_cutoff,
                "entity_count": len(ents),
            })
        return templates.TemplateResponse(request, "rooms.html", {"areas": areas_out})

    @router.get("/room/{area_id}", response_class=HTMLResponse, response_model=None)
    async def room(request: Request, area_id: str) -> Any:
        if state is None:
            return RedirectResponse("/")
        areas = await state.dao.list_areas()
        match = next((a for a in areas if a.area_id == area_id), None)
        if not match:
            return RedirectResponse("/")
        entities = await state.dao.list_entities(area_id=area_id)
        recent = await state.dao.list_events(area_id=area_id, limit=50)
        return templates.TemplateResponse(request, "room.html", {
            "area": match, "entities": entities, "recent_events": recent,
        })

    @router.get("/entities", response_class=HTMLResponse)
    async def entities_page(request: Request) -> HTMLResponse:
        ents = await state.dao.list_entities(limit=500) if state else []
        return templates.TemplateResponse(request, "entities.html",
                                          {"entities": ents})

    @router.get("/timeline", response_class=HTMLResponse)
    async def timeline_page(request: Request) -> HTMLResponse:
        evs = await state.dao.list_events(limit=200) if state else []
        return templates.TemplateResponse(request, "timeline.html",
                                          {"events": evs})

    @router.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request) -> HTMLResponse:
        ctx = {"hide_pattern": state.hide_pattern if state else []}
        return templates.TemplateResponse(request, "settings.html", ctx)

    return router
