"""TOML + env-var configuration loading.

v0.1.0 only consumes [ha], [behavior], [digest] (max_tokens used by Web UI for
display only since LLM is v0.3+), [audit], [privacy], [web], [soft_intention]
(stored but never read in v0.1.0). [llm.*] is parsed for forward-compat but
not consumed.
"""
from __future__ import annotations

import os
import tomllib  # py311 stdlib (alias of tomli)
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class ConfigError(Exception):
    """Raised on TOML parse failure or schema validation failure."""


class HAConfig(BaseModel):
    url: str = Field(min_length=1)
    token: str = Field(min_length=1)


class BehaviorConfig(BaseModel):
    history_retention_days: int = 30
    preference_half_life_days: int = 14
    min_observations_for_pattern: int = 5


class DigestConfig(BaseModel):
    max_tokens: int = 500
    recent_event_window_minutes: int = 30
    include_entities_pattern: list[str] = []


class LLMProvider(BaseModel):
    key: str
    label: str = ""
    base_url: str = ""
    default_model: str = ""
    role: str = "capable"


class LLMConfig(BaseModel):
    fast_tier: str = ""
    capable_tier: str = ""
    escalation_threshold: float = 0.7
    budget_usd_monthly: float = 5.0
    providers: list[LLMProvider] = []


class AuditConfig(BaseModel):
    retention_days: int = 90
    hash_chain: bool = True


class PrivacyConfig(BaseModel):
    allow_cloud_llm_with_digest: bool = False
    hide_entities_pattern: list[str] = []


class WebConfig(BaseModel):
    host: str = "0.0.0.0"  # noqa: S104
    port: int = 8124
    require_auth: bool = True


class SoftIntentionConfig(BaseModel):
    auto_dismiss_after_hours: int = 72
    max_queue_size: int = 50
    require_dual_confirm_for_critical: bool = True


class ArchiveConfig(BaseModel):
    retention_days: int = 365
    compress: bool = True


class AppConfig(BaseModel):
    ha: HAConfig
    behavior: BehaviorConfig = BehaviorConfig()
    digest: DigestConfig = DigestConfig()
    llm: LLMConfig = LLMConfig()
    audit: AuditConfig = AuditConfig()
    privacy: PrivacyConfig = PrivacyConfig()
    web: WebConfig = WebConfig()
    soft_intention: SoftIntentionConfig = SoftIntentionConfig()
    archive: ArchiveConfig = ArchiveConfig()


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    if env_url := os.environ.get("HA_URL"):
        raw.setdefault("ha", {})["url"] = env_url
    if env_token := os.environ.get("HA_TOKEN"):
        raw.setdefault("ha", {})["token"] = env_token
    if env_port := os.environ.get("AI_HA_WEB_PORT"):
        raw.setdefault("web", {})["port"] = int(env_port)
    return raw


def load_config(path: str | Path) -> AppConfig:
    """Load and validate config.toml. env vars (HA_URL/HA_TOKEN/AI_HA_WEB_PORT) override file."""
    p = Path(path)
    try:
        raw = tomllib.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {p}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"TOML parse error in {p}: {exc}") from exc
    raw = _apply_env_overrides(raw)
    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"config validation failed:\n{exc}") from exc
