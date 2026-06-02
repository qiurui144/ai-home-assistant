from __future__ import annotations

import tomllib
from collections.abc import Awaitable, Callable
from typing import Any

import tomli_w
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ai_ha.privacy.hide_matcher import HideMatcher, PatternComplexityError
from ai_ha.web.routes import AppState


class PrivacyPayload(BaseModel):
    hide_entities_pattern: list[str] = Field(default_factory=list)
    allow_cloud_llm_with_digest: bool | None = None


def build_router(
    state: AppState | None,
    require_admin: Callable[..., Awaitable[None]],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin)])

    @router.get("/settings/privacy")
    async def get_privacy() -> dict[str, object]:
        if state is None:
            return {"hide_entities_pattern": [], "allow_cloud_llm_with_digest": False}
        return {
            "hide_entities_pattern": state.hide_pattern,
            "allow_cloud_llm_with_digest": False,  # v0.1.0 always false (no LLM)
        }

    @router.post("/settings/privacy")
    async def update_privacy(payload: PrivacyPayload) -> dict[str, object]:
        if state is None:
            raise HTTPException(503)
        try:
            HideMatcher(payload.hide_entities_pattern)
        except PatternComplexityError as exc:
            raise HTTPException(422, detail={"error": "hide-pattern-invalid",
                                              "detail": str(exc)}) from exc
        except Exception as exc:
            raise HTTPException(422, detail={"error": "hide-pattern-invalid",
                                              "detail": str(exc)}) from exc
        raw: dict[str, Any] = tomllib.loads(state.config_path.read_text())
        raw.setdefault("privacy", {})["hide_entities_pattern"] = payload.hide_entities_pattern
        state.config_path.write_bytes(tomli_w.dumps(raw).encode())
        return {
            "hide_entities_pattern": payload.hide_entities_pattern,
            "allow_cloud_llm_with_digest": False,
        }

    return router
