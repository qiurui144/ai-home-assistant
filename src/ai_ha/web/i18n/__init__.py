"""i18n module for ai-home-assistant Web UI.

Real implementation arrives in Task 9. This stub allows the package to be
importable so Task 10's Jinja env wiring doesn't fail at install time.
"""
from __future__ import annotations

__all__ = ["locale_from_request", "install_translations"]


def locale_from_request(*_args: object, **_kwargs: object) -> str:
    return "en"


def install_translations(*_args: object, **_kwargs: object) -> None:
    pass
