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

from ai_ha.web.i18n import install_translations, locale_from_request
from ai_ha.web.routes import AppState

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
templates.env.filters["tstoiso"] = lambda ms: datetime.fromtimestamp(
    ms / 1000.0, tz=UTC,
).isoformat()
templates.env.add_extension("jinja2.ext.i18n")


def _render(request: Request, name: str, ctx: dict[str, object]) -> HTMLResponse:
    install_translations(templates.env, locale_from_request(request))  # type: ignore[arg-type]
    return templates.TemplateResponse(request, name, ctx)


def build_pages_router(
    state: AppState | None,
    require_admin: Callable[..., Awaitable[None]],
) -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_admin)])

    @router.get("/", response_class=HTMLResponse)
    async def root_redirect() -> RedirectResponse:
        return RedirectResponse("/dashboard", status_code=307)

    @router.get("/dashboard", response_class=HTMLResponse)
    async def dashboard_page(request: Request) -> HTMLResponse:
        import json as _json
        # Best-effort initial data; client will refetch via /api/v1/dashboard
        initial: dict[str, object] = {"health": {}, "rooms": [], "recent_events": []}
        if state is not None:
            initial = {
                "health": state.health.snapshot(now_ms=int(__import__("time").time() * 1000)),
                "rooms": [], "recent_events": [],
            }
        return _render(request, "dashboard.html", {
            "initial": initial,
            "initial_json": _json.dumps(initial, ensure_ascii=False),
        })

    @router.get("/rooms", response_class=HTMLResponse)
    async def rooms_page(request: Request) -> HTMLResponse:
        if state is None:
            return _render(request, "rooms.html", {"areas": []})
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
                "active": last_seen_max > active_cutoff,
                "entity_count": len(ents),
            })
        return _render(request, "rooms.html", {"areas": areas_out})

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
        return _render(request, "room.html", {
            "area": match, "entities": entities, "recent_events": recent,
        })

    @router.get("/entities", response_class=HTMLResponse)
    async def entities_page(request: Request) -> HTMLResponse:
        ents = await state.dao.list_entities(limit=500) if state else []
        return _render(request, "entities.html", {"entities": ents})

    @router.get("/timeline", response_class=HTMLResponse)
    async def timeline_page(request: Request) -> HTMLResponse:
        evs = await state.dao.list_events(limit=200) if state else []
        return _render(request, "timeline.html", {"events": evs})

    @router.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request) -> HTMLResponse:
        ctx: dict[str, object] = {"hide_pattern": state.hide_pattern if state else []}
        return _render(request, "settings.html", ctx)

    return router
