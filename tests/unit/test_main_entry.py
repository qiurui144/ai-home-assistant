"""Smoke-import tests for main entry points."""
from __future__ import annotations

import ai_ha
import ai_ha.__main__
from ai_ha.main import (
    EXIT_CONFIG,
    EXIT_DB_UNRECOVERABLE,
    EXIT_OK,
    _print_first_run_banner,
    _ws_url,
    main,
)


def test_main_module_importable():
    """Ensures __main__.py and ai_ha package wire correctly without running."""
    assert ai_ha is not None
    assert ai_ha.__main__ is not None


def test_main_exit_codes():
    assert callable(main)
    assert EXIT_OK == 0
    assert EXIT_CONFIG == 78
    assert EXIT_DB_UNRECOVERABLE == 70


def test_ws_url_and_banner_importable():
    assert callable(_ws_url)
    assert callable(_print_first_run_banner)
