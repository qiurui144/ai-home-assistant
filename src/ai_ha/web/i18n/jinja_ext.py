"""Jinja2 i18n integration."""
from __future__ import annotations

from jinja2 import Environment

from ai_ha.web.i18n.loader import get_translation


def install_translations(env: Environment, locale: str) -> None:
    """Wire the translation for `locale` into Jinja env for {% trans %} support."""
    t = get_translation(locale)
    env.install_gettext_translations(t, newstyle=True)  # type: ignore[attr-defined]
