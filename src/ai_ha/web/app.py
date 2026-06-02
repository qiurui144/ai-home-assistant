"""FastAPI app factory. Routes are mounted from web/routes/* in later tasks (Task 20)."""
from __future__ import annotations

from fastapi import Depends, FastAPI

from ai_ha.web.auth import AdminTokenStore, make_require_admin


def create_app(
    *, token_store: AdminTokenStore, require_auth: bool = True,
) -> FastAPI:
    app = FastAPI(title="ai-home-assistant", version="0.1.0")
    require_admin = make_require_admin(token_store, require_auth=require_auth)
    app.state.require_admin = require_admin

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        return {"status": "healthy"}

    @app.get("/api/v1/areas", dependencies=[Depends(require_admin)])
    async def areas_stub() -> list[object]:
        return []

    return app
