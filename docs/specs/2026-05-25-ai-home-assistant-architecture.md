# AI Home Assistant — Architecture Spec

**Date**: 2026-05-25
**Status**: Initial spec (per global CLAUDE.md §架构级别设计铁律 11-section requirement)
**Repo**: `qiurui144/ai-home-assistant` (TBD created post-spec)

---

## 0. Why this exists (one-paragraph pitch)

> User asked (2026-05-25): "规划一个独立项目，home assistant 建立 AI 体系
> （不只是接入 LLM，而是更懂用户的 AI home assistant），这个 home assistant
> 支持 x86、arm64、riscv64（docker 部署）"

**The bet**: Current Home Assistant (HA Core, Nabu Casa) is a great
device-aggregation hub, but its "AI" surface is limited to (1) Voice
Pipeline w/ LLM and (2) Assist actions. It does **not** model the user
— it doesn't know that "you usually turn off the bedroom light when
the front door locks at night" or "you prefer 22°C in winter weekday
mornings but 24°C on weekends." Each request starts cold from the LLM.

**Our take**: an **AI Home Assistant** that maintains a per-user
**preference + behavior model** locally, feeds *compressed context* to
the LLM, and lets the LLM operate on **delta intentions** instead of
re-explaining every state. The intelligence advantage compounds with
use, not with model size.

**Tech bet**: ship as a Docker container that can sit *alongside* an
existing Home Assistant Core instance (does not replace HA), talks to
HA via its REST + WebSocket API, and runs LLM either on-device
(RKLLM 3B / Ollama on x86) or via a privacy-aware cloud route. Multi-arch
images (linux/amd64 / linux/arm64 / linux/riscv64) from day one.

---

## 0.5 目标硬件 + 迁移路径（用户 2026-05-25 补充）

> "整体体系需要 RK3588，未来可能是进迭时空 K3，所以规划时要考虑清楚"

**Primary deployment target**: **Rockchip RK3588** (NanoPC-T6) — same SoC
as KVM project, allowing AI Home Assistant to live on the same hardware
in `kvm-nas-dual` image variant (per KVM derivative-repo standard §0).

**Future migration target**: **SpacemiT K1/K3** (RISC-V, IME2 INT8 NPU,
SpacemiT Spine framework) — when the platform matures (≥ 2027 estimate).
Spec considerations to keep ports easy:

| Concern | RK3588 today | K3 RISC-V future |
|---------|--------------|------------------|
| Python wheels | aarch64 — mature | riscv64 — thin; build-from-source CI 必须 |
| Fast-tier LLM | RKLLM (rknn-runtime) | SpacemiT Spine + IME2 INT8 (LLM acceleration TBD) |
| NPU API | `rknn-toolkit2-lite` | SpacemiT NPU SDK (different headers) |
| Container ABI | linux/arm64 | linux/riscv64 |
| Distro support | Debian Bookworm (friendly-elec) | Debian Trixie (RISC-V upstream) |

**Implication for AI HomeAssistant design**:

1. **LLM provider abstraction must be NPU-agnostic** — fast tier handlers
   plug in via the OpenAI-compat shim (RKLLM 8891 today, SpacemiT NPU
   endpoint tomorrow). The orchestrator code stays unchanged.
2. **Behavior engine math runs on CPU only** — histograms / time curves /
   sequence mining never depend on NPU. Stays portable across SoCs.
3. **CI matrix from day one** includes `linux/riscv64` (even if slow) so
   the K1/K3 migration is one tag bump, not a fork.
4. **NPU-bound paths are opt-in** — if `llm.fast_tier.provider = local-rkllm`
   fails to resolve on a non-RK3588 host, fall back to `ollama` or
   `cloud-capable` without breaking the app.
5. **Vendor-specific code (if any)** lives behind a `platform` adapter:
   `src/ai_ha/platform/rk3588.py` / `src/ai_ha/platform/k3.py` /
   `src/ai_ha/platform/generic.py`. Default is `generic.py` (pure CPU + cloud LLM).

### Concrete K3 readiness checklist (track in `docs/specs/` over time)

- [ ] CI `linux/riscv64` job green (v0.1.0 ship gate)
- [ ] At least one **end-to-end test** runs in qemu-riscv64 (mock HA, mock LLM)
- [ ] SpacemiT NPU SDK header survey — what's the OpenAI-compat path?
- [ ] First-attempt deploy on a real K1 board (LicheePi 4A or VisionFive 2 as
  a stand-in until K3 hardware ships)
- [ ] Performance gap: % slower vs RK3588 on `digest-builder p95` benchmark

---

## 1. 目标定位

### 1.1 解决的核心痛点

| Pain | Current solution | Our improvement |
|------|------------------|-----------------|
| LLM 每次冷启动，要重复 explain 状态 | dump full state to system prompt | rolling **state digest** (preference deltas + recent events) |
| 用户偏好沉默 | manual scripts / blueprints | **preference learning loop** — auto-extract from action histograms |
| 自动化触发硬规则 | YAML automation | **soft intentions** — LLM proposes, user approves once, becomes habit |
| 跨房间 / 跨情境记忆缺失 | none | **episodic memory** — "last time you said this, you wanted X" |
| 多用户混淆 | HA person entity | **person-identified preference vector** per voice / phone presence |
| Voice latency | round-trip to cloud LLM | **on-device fast tier** + cloud capable tier escalation |

### 1.2 与产品 positioning 对齐

- **本地优先** (per KVM project core thesis) — preference data NEVER leaves device unless user opt-in
- **多硬件 portability** — same Docker image runs on a Raspberry Pi (arm64),
  N100 mini-PC (amd64), or VisionFive 2 / Lichee Pi 4A (riscv64)
- **可审计** — every LLM call + every auto-action logged with reasoning

### 1.3 不解决的范畴

- ❌ Not replacing Home Assistant Core (we *complement* it; HA does devices, we do AI)
- ❌ Not a voice transcription engine (use HA's Whisper / cloud STT)
- ❌ Not a smart-speaker hardware product (software-only)
- ❌ Not a multi-tenant SaaS (single household per instance; deploy your own)

---

## 2. 范围边界

### 2.1 做（v1.0 必须）

- Docker container `ghcr.io/qiurui144/ai-home-assistant:vX.Y.Z` for amd64/arm64/riscv64
- HA REST + WebSocket adapter (read entity states, subscribe events, call services)
- Per-user preference model (preference vector + decay) — stored in SQLite locally
- Behavior model — action histogram, time-of-day curves, sequence-pattern mining
- LLM provider abstraction (compatible with the same OpenAI-compat registry as KVM uses — DeepSeek / OpenAI / Anthropic / Ollama / RKLLM 等)
- State digest builder — compress current relevant entities into < 500 tokens for LLM context
- "soft intention" workflow — LLM proposes automation; user one-tap approves → becomes a real HA automation
- Web UI for: viewing learned preferences, editing/forgetting items, approving suggestions
- Audit log (append-only hash-chain — same primitive as KVM)
- Offline mode — if cloud LLM unavailable, fall back to local RKLLM / Ollama

### 2.2 不做（明确划清）

- ❌ Direct device control bypassing HA — always go through HA service calls
- ❌ Replace HA's UI (we ship our own minimal UI; the HA Lovelace dashboards
  remain untouched)
- ❌ Stream microphone audio to cloud — voice handled by HA's pipeline
- ❌ Multi-tenant — single household, single device, single deployment
- ❌ Free hosting — users self-host (Docker on their own hardware)

### 2.3 后续 v.x 才做

| Version | Feature |
|---------|---------|
| v1.1 | Multi-user voice ID (per-person preferences via voiceprint) |
| v1.2 | Cross-device sync via P2P (two AI HAs on same LAN sharing preferences) |
| v1.3 | Federation — opt-in anonymized preference sharing for community learning |
| v2.0 | Vision agent (consume camera streams via HA → identify scenes) |

---

## 3. 架构数据流

### 3.1 High-level diagram

```
┌──────────────────────────────────────────────────────────┐
│  Existing Home Assistant Core (untouched, runs on 8123)  │
│   ├─ device integrations (zigbee/zwave/wifi/ble)         │
│   ├─ Lovelace UI                                          │
│   └─ Voice Pipeline (Whisper STT / Piper TTS)            │
└─────────────┬─────────────────────────────┬──────────────┘
              │ REST + WebSocket            │
              │                              │ service_call /
              │ event_stream                 │ states API
              ▼                              ▲
┌──────────────────────────────────────────────────────────┐
│       AI Home Assistant (this project, runs on 8124)     │
│  ┌──────────────────────────────────────────────────┐    │
│  │ ha-adapter (REST + WS bridge)                    │    │
│  └─────┬──────────────────────────────────────┬─────┘    │
│        ▼                                      ▼          │
│  ┌──────────────┐                  ┌──────────────────┐  │
│  │ event-stream │                  │ state-cache       │  │
│  │ (subscribe)  │                  │ (read latest)     │  │
│  └──────┬───────┘                  └────────┬──────────┘  │
│         ▼                                   ▼             │
│  ┌────────────────────────────────────────────────────┐   │
│  │ behavior-engine                                    │   │
│  │  ├─ action-histogram     (what user does when)     │   │
│  │  ├─ time-curve-model     (preference over hour-of-day)│
│  │  ├─ sequence-miner       (A→B→C pattern detection) │   │
│  │  └─ preference-vector    (per person × dimension)  │   │
│  └────────────────┬───────────────────────────────────┘   │
│                   ▼                                       │
│  ┌────────────────────────────────────────────────────┐   │
│  │ digest-builder — compress to <500 tokens           │   │
│  └────────────────┬───────────────────────────────────┘   │
│                   ▼                                       │
│  ┌────────────────────────────────────────────────────┐   │
│  │ llm-orchestrator                                   │   │
│  │  ├─ fast tier   (local RKLLM / Ollama / Phi3-mini) │   │
│  │  ├─ capable tier (DeepSeek / GPT-4o-mini / Claude) │   │
│  │  └─ escalation policy (low_confidence → capable)   │   │
│  └────────────────┬───────────────────────────────────┘   │
│                   ▼                                       │
│  ┌────────────────────────────────────────────────────┐   │
│  │ intent-router → HA service_call  OR                │   │
│  │              → soft-intention queue                │   │
│  │              → user-notification                   │   │
│  └────────────────────────────────────────────────────┘   │
│                                                           │
│  ┌────────────────────────────────────────────────────┐   │
│  │ SQLite — preferences / history / audit chain       │   │
│  │ MQTT (optional) — emit AI suggestions to HA topics │   │
│  │ Web UI — http://<host>:8124  (review + control)    │   │
│  └────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### 3.2 Key data flows

1. **Event ingestion**: HA WS event → behavior-engine → update histograms / patterns
2. **Question answered**: User asks → ha-adapter receives via API/MQTT → digest-builder snapshots relevant state + recent preferences → llm-orchestrator picks tier → response → if it's an action, optionally execute via HA service_call (after policy check)
3. **Proactive suggestion**: behavior-engine detects pattern (e.g. "user always turns off bedroom light 5 min after locking door at >22:00") → digest + LLM verify → propose to user via UI/notification → on approve, write a real HA automation YAML and ask HA to load it

### 3.3 数据存储

| Store | Path | Retention |
|-------|------|-----------|
| Preferences SQLite | `/data/preferences.db` | indefinite (until user purges) |
| Audit log | `/data/audit-log.jsonl` (hash-chain) | rolling 90 days, then archive |
| Event archive | `/data/events.parquet` | rolling 30 days |
| LLM cache | `/data/llm-cache.db` | 24 h TTL |

All inside the Docker volume — survives image upgrade.

---

## 4. 模块边界

```
ai-home-assistant/
├── README.md
├── LICENSE                       # Apache-2.0
├── DEVELOP.md
├── CLAUDE.md                     # AI working instructions
├── docker/
│   ├── Dockerfile                # multi-arch (amd64/arm64/riscv64)
│   ├── docker-compose.yml        # standalone deploy template
│   └── docker-compose.with-ha.yml # bundles HA Core + ai-ha
├── src/                          # Python 3.11+ (per HA ecosystem alignment)
│   ├── ai_ha/
│   │   ├── __init__.py
│   │   ├── ha_adapter.py         # REST + WS client wrapping homeassistant_api
│   │   ├── behavior_engine.py    # histograms / curves / patterns
│   │   ├── digest_builder.py     # compress state to <500 tok
│   │   ├── llm_orchestrator.py   # fast + capable tier + escalation
│   │   ├── intent_router.py      # service_call vs soft-intention
│   │   ├── audit.py              # hash-chain log
│   │   └── web/                  # FastAPI app — minimal UI
├── config/
│   ├── default.toml              # all knobs documented + defaults
│   └── providers.example.toml    # LLM provider examples (DeepSeek/OpenAI/Ollama)
├── tests/
│   ├── unit/
│   └── integration/              # spins up mock HA + asserts behavior
├── docs/
│   ├── specs/
│   │   └── 2026-05-25-architecture.md     # THIS file
│   └── adr/                                # later decisions
└── .github/workflows/
    ├── ci.yml                    # unit + integration test
    └── release.yml               # multi-arch image push to GHCR
```

---

## 5. API 契约

### 5.1 HTTP API (FastAPI on :8124)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /api/health` | GET | liveness |
| `GET /api/v1/preferences` | GET | list learned preferences |
| `DELETE /api/v1/preferences/{id}` | DELETE | forget a preference |
| `GET /api/v1/suggestions` | GET | pending soft-intentions for user review |
| `POST /api/v1/suggestions/{id}/approve` | POST | accept → become HA automation |
| `POST /api/v1/suggestions/{id}/reject` | POST | reject + train against |
| `POST /api/v1/ask` | POST | one-shot question (returns LLM answer + optional executed action) |
| `GET /api/v1/audit?from=&to=` | GET | audit log (JSONL stream) |
| `WS /api/v1/events` | WS | real-time AI events (suggestion / action / audit) |

### 5.2 MQTT topics (optional, for HA dashboard integration)

| Topic | Direction | Payload |
|-------|-----------|---------|
| `ai-ha/suggestion` | publish | `{id, summary, confidence, proposed_automation}` |
| `ai-ha/action` | publish | `{action, target, reason, audit_id}` |
| `ai-ha/notify` | publish | `{level: info|warn, message}` |

### 5.3 LLM provider abstraction

Reuse the **same OpenAI-compatible registry pattern as KVM** (per
`KVM/config/llm-providers.yaml`). Providers config file:

```yaml
providers:
  - key: ollama-local
    label: "Ollama (host)"
    base_url: "http://host.docker.internal:11434"
    default_model: "llama3.1"
    role: "fast"  # NEW: fast | capable
  - key: rkllm-device
    label: "RKLLM (RK3588 NPU)"
    base_url: "http://kvm.local:8891"
    default_model: "qwen3-0.6b"
    role: "fast"
  - key: deepseek
    label: "DeepSeek (cloud)"
    base_url: "https://api.deepseek.com"
    default_model: "deepseek-chat"
    role: "capable"
```

---

## 6. 扩展点 / 插件接口

### 6.1 v1.0 ships with

- `behavior_engine.plugins.histogram` — built-in
- `behavior_engine.plugins.time_curve` — built-in
- `behavior_engine.plugins.sequence_miner` — built-in

### 6.2 v1.1+ plugin contract

```python
class BehaviorPlugin:
    name: str
    def observe(self, event: HAEvent) -> None: ...
    def query(self, prompt_context: dict) -> Optional[PreferenceContribution]: ...
```

Drop a `*.py` file into `/data/plugins/` → loaded on next startup.

---

## 7. 错误处理 + 边界 case

### 7.1 HA unreachable

- Adapter retries with exponential backoff (initial 1s, max 60s)
- During disconnect: queue events to local buffer (max 1000)
- On reconnect: replay events; if buffer overflowed, log warning and skip

### 7.2 LLM provider down

- Tier escalation: fast → capable
- Both down: queue user query, retry every 60s, after 3 retries → reply "I'm offline,
  here's what I last saw: <state digest>"
- Critical actions (e.g. "lock the door") are NEVER executed by LLM alone —
  must come through soft-intention flow (queue → user approve once → automation)

### 7.3 Multi-arch image issues

- riscv64 build may take 3× as long (limited GCC optimization for some Python deps)
- If `cryptography` or `pydantic` lacks riscv64 wheel: build from source in CI
- Test matrix runs at minimum: `pytest tests/unit/` on all 3 arches

---

## 8. 成本契约

| Resource | Amount |
|----------|-------:|
| Docker image size | ~250 MB (uncompressed) — multi-arch |
| RAM at runtime | ~150-300 MB idle / 500 MB peak (during pattern mining) |
| Disk | ~50 MB code + 100-500 MB user data (1 yr) |
| Network | Negligible for HA WS; LLM cost = whatever the chosen provider charges |
| CPU | 1 core sustained for behavior engine; bursts on LLM call |

**Cost target**: zero cloud cost in default config (local Ollama / RKLLM tier 0).
Optional cloud LLM at ~$0.0001-$0.001 per user-question (per token model).

---

## 9. 测试矩阵 (per CLAUDE.md §代码变更后强制流程)

| Test Layer | Tool | Min Coverage |
|------------|------|--------------|
| Unit | pytest | 80% lines / 60% branches |
| Integration | pytest + mock HA | All 8 HTTP endpoints + WS events |
| Multi-arch CI | GitHub Actions matrix | amd64 + arm64 + riscv64 |
| E2E (manual) | Real HA + real LLM provider | per-release checklist |
| Performance | pytest-benchmark | digest-builder p95 < 50ms / 1k events |

---

## 10. 向后兼容

- v1.x SQLite schema migrations auto-applied; user data preserved
- v1.x → v2.x: behavior model may change interpretation but **data
  retention is mandatory** (don't lose user history on upgrade)
- HA API version: pin against `2025.x`; auto-detect on connect and warn if mismatch
- Docker image: latest = bleeding edge; tag specific version for prod

---

## 11. 风险登记

| # | Risk | Mitigation |
|---|------|------------|
| 1 | Users find AI's automatic actions creepy/intrusive | Soft-intention flow — never auto-execute without user one-tap approval first time |
| 2 | LLM hallucinates an action that opens the door at 3am | Critical actions whitelisted manually; require dual confirmation (LLM + user) |
| 3 | Preference learning over-fits to one bad day | Decay function: half-life 14 days |
| 4 | riscv64 Python wheel ecosystem still thin | Build from source in CI; expect longer build time, document |
| 5 | HA breaking API change | Pin to HA 2025.x, monitor HA release notes monthly |
| 6 | LLM provider rate-limit | Built-in retry + escalation tier; gracefully degrade to "I'm thinking, ask again in 30s" |
| 7 | User data privacy concern | All by default local; cloud LLM gets *digest only* (no raw event log); opt-in toggle for cloud feature |
| 8 | RKLLM 0.6B too dumb for digest-driven Q&A | K-matrix in KVM project showed 17% accuracy on tasks; AI HA fast tier sets bar at 65% — use ≥ 3B model where memory permits |
| 9 | Multi-user voice ID infrastructure complex | Skip v1.0; rely on HA's person entity + presence; v1.1 adds voiceprint |
| 10 | Auto-update breaks user setup | watchtower opt-in (default off); user explicitly upgrades |
| 11 | Behavior engine SQLite size unbounded | Auto-prune events older than 30d (configurable) |
| 12 | LLM cost spirals | Built-in budget enforcement: cap monthly LLM API spend via per-key counter |

---

## 12. 实施时间线 (建议)

| Phase | Week | Deliverable |
|-------|-----:|-------------|
| 0 | -1 | This spec **(NOW)** |
| 1 | 1 | repo + Dockerfile multi-arch + CI green + dummy ha-adapter |
| 2 | 2-3 | behavior-engine core (histogram + time-curve) + SQLite schema + tests |
| 3 | 4 | digest-builder + llm-orchestrator + provider registry |
| 4 | 5 | intent-router + soft-intention queue + minimal Web UI |
| 5 | 6 | audit chain + multi-arch CI runs + integration tests |
| 6 | 7 | v0.1.0 release + docs / wiki |
| 7 | 8-9 | community pilot — 5-10 households |
| 8 | 10-12 | v1.0.0 GA based on pilot feedback |

---

## 13. Open questions for user (please confirm before implementation)

- [ ] **Language**: Python or Rust? Spec assumes Python (HA ecosystem alignment).
  Rust would be 3-5× faster on the behavior engine but adds 6-month dev cost.
- [ ] **Web UI tech**: FastAPI + minimal vanilla JS, or React/Vue? Spec assumes
  minimal vanilla to keep image small.
- [ ] **Docker base**: `python:3.11-slim` or `alpine`? Slim chosen for wheel
  compatibility; alpine is smaller but musl breaks several deps.
- [ ] **Voice integration**: just listen to HA's transcripts, or run our own
  STT (Whisper-tiny)? Spec assumes HA-provided.
- [ ] **Hardware test matrix**: which devices for CI? Suggested: GitHub Actions
  ubuntu-latest (amd64) + self-hosted RK3588 (arm64) + qemu-riscv64 (riscv64).

---

## Addendum 2026-05-25 (afternoon) — Kernel version pin per platform

Per user: "K3 和 3588 做好分支管理，因为一个是 6.1 内核，一个是 6.18 的 OEM 内核"
(see KVM main `docs/specs/2026-05-25-derivative-repo-standard.md` §0-bis)

This is **mostly transparent** to ai-home-assistant because:
- We run in Docker — the host kernel version is irrelevant to our container
- Our only kernel dependency is **cgroup v2** (Linux ≥ 5.x), trivially met
  by both 6.1.y and 6.18

But two indirect implications:

1. **Host platform detection** — for the optional `platform/rk3588.py` and
   `platform/k3.py` adapters (when present), the code may want to know the
   host kernel:
   ```python
   import platform
   kernel = platform.release()  # "6.1.141-rockchip" vs "6.18.0-spacemit"
   ```
   Use this to gate NPU endpoint discovery (RKLLM on 8891 vs SpacemiT NPU on TBD).

2. **kvm-build-env base image** — when our Dockerfile pulls
   `FROM ghcr.io/qiurui144/kvm-build-env:latest`, it gets a userspace
   compatible with both kernel versions (Bookworm glibc supports kernel ≥ 5.10).
   No build-time branching needed.

**Bottom line**: ai-home-assistant Docker image stays single-source; only
the optional platform adapter modules diverge. CI matrix already covers
both arches (arm64 for RK3588, riscv64 for K3 future).
