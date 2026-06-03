"""Language switcher endpoints — no auth required.

GET  /api/v1/locales  → list supported
POST /api/v1/lang     → set ai-ha-lang cookie
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from ai_ha.web.i18n import SUPPORTED_LOCALES
from ai_ha.web.i18n.loader import _normalize


class LangPayload(BaseModel):
    lang: str


def build_lang_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/locales")
    async def locales() -> list[dict[str, str]]:
        return [{"code": k, "name": v} for k, v in SUPPORTED_LOCALES.items()]

    @router.post("/lang")
    async def set_lang(payload: LangPayload, response: Response) -> dict[str, str]:
        norm = _normalize(payload.lang)
        if norm is None:
            raise HTTPException(
                422,
                detail={"error": "invalid-locale",
                        "detail": f"unknown lang {payload.lang!r}"},
            )
        response.set_cookie(
            "ai-ha-lang", norm, max_age=31_536_000, samesite="lax", path="/",
        )
        return {"lang": norm}

    return router
