"""ai-home-assistant — AI layer that augments existing Home Assistant Core.

See docs/specs/2026-05-25-ai-home-assistant-architecture.md for the
complete design. This package is **spec-stage scaffolding** — the
v0.1.0 implementation work has not started yet (per spec §12 timeline).

Module map (planned):
    ha_adapter         — REST + WS client for Home Assistant Core
    behavior_engine    — histograms / time-curves / sequence mining
    digest_builder     — compress state to < 500 tokens for LLM context
    llm_orchestrator   — fast + capable tier + escalation
    intent_router      — service_call vs soft-intention queue
    audit              — hash-chain log
    web                — FastAPI UI + REST API on :8124

Architecture rationale: see spec §3.
Hardware targets:        see spec §0.5 (RK3588 primary, K3 RISC-V future).
"""

__version__ = "0.0.0-spec-stage"
__all__: list[str] = []
