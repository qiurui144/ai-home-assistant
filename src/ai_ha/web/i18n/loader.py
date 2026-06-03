"""Locale negotiation + gettext translation loader.

Order: ?lang= query → ai-ha-lang cookie → Accept-Language → "en" default.
Short codes ('zh', 'en') normalise to full ('zh_CN', 'en').
"""
from __future__ import annotations

import gettext
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

LOCALE_DIR = Path(__file__).parent / "locales"
SUPPORTED_LOCALES: dict[str, str] = {
    "en": "English",
    "zh_CN": "中文 (简体)",
}

_SHORT_ALIASES = {"zh": "zh_CN", "en": "en"}


class _HasRequestLikeAttrs(Protocol):
    query_params: Any
    cookies: Any
    headers: Any


def _normalize(code: str) -> str | None:
    code = code.strip().replace("-", "_")
    if code in SUPPORTED_LOCALES:
        return code
    short = code.split("_")[0].lower()
    return _SHORT_ALIASES.get(short)


def _accept_language_locales(header: str) -> Iterable[str]:
    """Yield candidate codes from an Accept-Language header in priority order."""
    parts = [p.split(";")[0].strip() for p in header.split(",") if p.strip()]
    for p in parts:
        if norm := _normalize(p):
            yield norm


def locale_from_request(request: _HasRequestLikeAttrs) -> str:
    q = getattr(request, "query_params", {}) or {}
    lang_q = q.get("lang") if hasattr(q, "get") else None
    if lang_q and (norm := _normalize(lang_q)):
        return norm

    cookies = getattr(request, "cookies", {}) or {}
    lang_c = cookies.get("ai-ha-lang") if hasattr(cookies, "get") else None
    if lang_c and (norm := _normalize(lang_c)):
        return norm

    headers = getattr(request, "headers", {}) or {}
    accept = (headers.get("accept-language") or "") if hasattr(headers, "get") else ""
    for cand in _accept_language_locales(accept):
        return cand

    return "en"


@lru_cache(maxsize=8)
def get_translation(locale: str) -> gettext.NullTranslations:
    """Return a Translation for `locale`. NullTranslations for 'en' or missing .mo."""
    if locale == "en":
        return gettext.NullTranslations()
    try:
        return gettext.translation(
            "ai_ha", localedir=str(LOCALE_DIR), languages=[locale], fallback=True,
        )
    except FileNotFoundError:
        return gettext.NullTranslations()
