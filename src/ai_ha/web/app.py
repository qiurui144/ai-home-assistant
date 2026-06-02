from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ai_ha.web.auth import AdminTokenStore, make_require_admin
from ai_ha.web.routes import AppState


def create_app(
    *, token_store: AdminTokenStore, require_auth: bool = True,
    state: AppState | None = None,
) -> FastAPI:
    app = FastAPI(title="ai-home-assistant", version="0.1.0")
    require_admin = make_require_admin(token_store, require_auth=require_auth)
    app.state.require_admin = require_admin
    app.state.app_state = state

    from ai_ha.web.routes.areas import build_router as _a
    from ai_ha.web.routes.entities import build_router as _e
    from ai_ha.web.routes.events import build_router as _ev
    from ai_ha.web.routes.health import build_router as _h
    from ai_ha.web.routes.settings import build_router as _s
    from ai_ha.web.routes.topology import build_router as _t

    app.include_router(_h(state))
    app.include_router(_t(state, require_admin))
    app.include_router(_a(state, require_admin))
    app.include_router(_e(state, require_admin))
    app.include_router(_ev(state, require_admin))
    app.include_router(_s(state, require_admin))

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app
