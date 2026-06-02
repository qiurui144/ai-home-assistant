# ai-home-assistant

> An AI layer that sits **alongside** your existing Home Assistant Core
> and learns *you* — preferences, routines, habits, edge-cases. Not
> just "LLM plumbing." More like a household co-pilot that gets sharper
> with use.

> **Spec**: [`docs/specs/2026-05-25-ai-home-assistant-architecture.md`](docs/specs/2026-05-25-ai-home-assistant-architecture.md) — 13 sections, please read before opening a PR.

## What this is, in one paragraph

Home Assistant Core does a great job aggregating devices. Its AI surface
(Voice Pipeline, LLM bridges) is thin — each user request starts fresh,
the LLM has to be re-told the whole house state, and the system doesn't
learn that you usually turn off the bedroom light 5 minutes after
locking the front door past 22:00. **ai-home-assistant** runs in a Docker
container next to HA, subscribes to its event stream, builds a
**per-user preference + behavior model**, and feeds the LLM a
**compressed state digest** (< 500 tokens) so cloud cost stays low and
the assistant actually gets smarter over time.

## Architecture summary

```
[Home Assistant Core 8123]  ←—REST + WS—→  [ai-home-assistant 8124]
   ↑ devices                                  ├ behavior-engine
   ↑ Lovelace UI                              ├ digest-builder
   ↑ Voice Pipeline                           ├ llm-orchestrator
                                              └ Web UI + audit log
```

Detailed flow: [§3 of the spec](docs/specs/2026-05-25-ai-home-assistant-architecture.md#3-架构数据流).

## Multi-arch support

Single image, three architectures:

| Arch | Hardware examples | Status |
|------|-------------------|--------|
| `linux/amd64` | N100 mini-PC, Intel NUC, x86 NAS, Proxmox VM | v0.1.0 target |
| `linux/arm64` | Raspberry Pi 4/5, RK3588 (NanoPC-T6 etc.), Apple Silicon dev | v0.1.0 target |
| `linux/riscv64` | VisionFive 2, Lichee Pi 4A, SpacemiT K1/K3 | v0.1.0 target (expect slower build) |

Image: `ghcr.io/qiurui144/ai-home-assistant:v<version>`.

## Quickstart (standalone next to existing HA)

```bash
# Assumes Home Assistant Core already running at http://homeassistant.local:8123
mkdir -p ai-ha-data
docker run -d --name ai-home-assistant \
  -p 8124:8124 \
  -v $PWD/ai-ha-data:/data \
  -e HA_URL=http://homeassistant.local:8123 \
  -e HA_TOKEN=<long-lived-access-token> \
  ghcr.io/qiurui144/ai-home-assistant:latest
```

Then visit http://localhost:8124 for the AI dashboard.

## Quickstart (compose, bundles HA Core)

For a fresh device with no existing HA:

```bash
git clone https://github.com/qiurui144/ai-home-assistant.git
cd ai-home-assistant/docker
docker compose -f docker-compose.with-ha.yml up -d
```

Brings up: Home Assistant Core (port 8123) + ai-home-assistant (8124) +
Mosquitto MQTT broker + watchtower (auto-update opt-in).

## Configuration knobs

All knobs live in `/data/config.toml` (copied from `config/default.toml`
on first run). Important ones:

- `llm.providers.*` — define your LLM providers (DeepSeek / OpenAI / Ollama / RKLLM…)
- `llm.fast_tier` / `llm.capable_tier` — which provider keys to use
- `behavior.history_retention_days` — default 30
- `behavior.preference_half_life_days` — default 14
- `audit.retention_days` — default 90
- `privacy.allow_cloud_llm_with_digest` — default `false` (set `true` to opt in)

## Status

**v0.1.0-rc.1** — Listen-only foundation, release candidate. See [RELEASE.md](RELEASE.md) for highlights and known limitations. GA (v0.1.0) requires real RK3588 hardware verification + 7d soak (see `tests/MANUAL_TEST_CHECKLIST.md`). v0.2 (histogram behavior model) starts after GA.

## License

Apache-2.0 — see [LICENSE](LICENSE).

## Related projects

| Project | Relation |
|---------|----------|
| [Home Assistant Core](https://github.com/home-assistant/core) | Required peer (we read its API; we do not fork it) |
| [KVM main](https://github.com/qiurui144/KVM) | Sibling project; shares LLM provider registry pattern + audit chain primitives |
| [kvm-build-env](https://github.com/qiurui144/kvm-build-env) | Reuse for arm64/riscv64 Docker cross-build |
| [kvm-rknn-models](https://github.com/qiurui144/kvm-rknn-models) | If running on RK3588, use these RKNN models for fast-tier inference |
