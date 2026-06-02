import textwrap

import pytest

from ai_ha.config.loader import ConfigError, load_config


def test_load_minimal_config(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(textwrap.dedent("""
        [ha]
        url = "http://localhost:8123"
        token = "fake-token"
    """))
    cfg = load_config(str(cfg_path))
    assert cfg.ha.url == "http://localhost:8123"
    assert cfg.behavior.history_retention_days == 30  # default


def test_env_override(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text('[ha]\nurl = "http://x"\ntoken = "t"\n')
    monkeypatch.setenv("HA_URL", "http://from-env:8123")
    cfg = load_config(str(cfg_path))
    assert cfg.ha.url == "http://from-env:8123"


def test_invalid_toml_raises(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("[ha\n  url = broken")
    with pytest.raises(ConfigError) as exc:
        load_config(str(cfg_path))
    assert "TOML" in str(exc.value)


def test_missing_required_field_raises(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("[ha]\nurl = ''\n")
    with pytest.raises(ConfigError):
        load_config(str(cfg_path))


def test_invalid_port_env_raises_config_error(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text('[ha]\nurl = "http://x"\ntoken = "t"\n')
    monkeypatch.setenv("AI_HA_WEB_PORT", "not-an-int")
    with pytest.raises(ConfigError) as exc:
        load_config(str(cfg_path))
    assert "AI_HA_WEB_PORT" in str(exc.value)
