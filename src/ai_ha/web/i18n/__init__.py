"""i18n module for ai-home-assistant Web UI."""
from __future__ import annotations

from ai_ha.web.i18n.jinja_ext import install_translations
from ai_ha.web.i18n.loader import (
    SUPPORTED_LOCALES,
    get_translation,
    locale_from_request,
)

__all__ = [
    "SUPPORTED_LOCALES",
    "get_translation",
    "install_translations",
    "locale_from_request",
]
