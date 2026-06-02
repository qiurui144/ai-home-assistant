import pytest

from ai_ha.config.loader import ConfigError, load_config


def test_invalid_toml_raises(tmp_path):
    (tmp_path / "c.toml").write_text("[broken\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path / "c.toml")


def test_missing_ha_section_raises(tmp_path):
    (tmp_path / "c.toml").write_text("[other]\nx=1\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path / "c.toml")
