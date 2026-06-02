"""Tests for pure helper functions in main.py (no I/O, no lifespan)."""
from __future__ import annotations

from ai_ha.main import _print_first_run_banner, _ws_url


def test_ws_url_http_to_ws():
    assert _ws_url("http://homeassistant.local:8123") == "ws://homeassistant.local:8123/api/websocket"


def test_ws_url_https_to_wss():
    assert _ws_url("https://ha.example.com") == "wss://ha.example.com/api/websocket"


def test_ws_url_passthrough_appends_path():
    # Already ws:// — just append path
    assert _ws_url("ws://x:8123") == "ws://x:8123/api/websocket"


def test_ws_url_passthrough_wss():
    assert _ws_url("wss://ha.example.com") == "wss://ha.example.com/api/websocket"


def test_first_run_banner_contains_token(capsys):
    _print_first_run_banner("test-token-not-real")
    out = capsys.readouterr().out
    assert "test-token-not-real" in out


def test_first_run_banner_contains_first_run_text(capsys):
    _print_first_run_banner("test-token-not-real")
    out = capsys.readouterr().out
    assert "FIRST RUN" in out


def test_first_run_banner_contains_bar(capsys):
    _print_first_run_banner("test-token-not-real")
    out = capsys.readouterr().out
    # The banner uses "═" (U+2550) box-drawing characters
    assert "═" in out
