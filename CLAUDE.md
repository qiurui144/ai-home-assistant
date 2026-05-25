# ai-home-assistant — AI Working Instructions

Per parent global `~/.claude/CLAUDE.md` + KVM main project CLAUDE.md.

## Project north star

> An AI layer for your house that **learns you** — preferences, habits,
> edge cases — and only goes to an LLM for the parts it can't decide on
> its own. Not just LLM plumbing.

If a change makes the system **smarter over use**, it's on-mission.
If it just adds more LLM round-trips, push back.

## Hardware targets

- **Primary**: Rockchip RK3588 (NanoPC-T6), shares hardware with KVM main
- **Future**: SpacemiT K1/K3 (RISC-V), 2027+ — keep ports easy
- **Dev**: any x86_64 / amd64 Docker host
- Spec §0.5 has the migration checklist

Per KVM main CLAUDE.md §模型测试目标硬件: **all model accuracy / latency
testing must run on target hardware**. 4090 / cloud-only inference does
not count as a release-gate.

## Branch + push

- Default `main`
- Direct push after tests pass (per KVM 个人/私有 project posture)
- 分支极简: no feature branches; tags drive release

## Docker-only build

All work happens inside the Docker image. Don't `pip install` to host;
don't `apt install` system Python deps for development. Use the
container.

## License

Apache-2.0 on this whole repo. Each LLM provider plugin / behavior plugin
under `/data/plugins/` may declare its own.

## Privacy is the headline feature

- Default: **NO** cloud LLM. Local fast tier (Ollama / RKLLM) only.
- Cloud LLM is opt-in, AND when on, only **digest** leaves the device
  (never raw event log).
- User can purge any learned preference in one click.
- All decisions auditable via hash-chain log.

If a PR weakens any of the above, reject it. This is the core
differentiator vs "just send everything to GPT-4."

## Sibling projects (avoid duplication)

| Repo | What's there | Use |
|------|--------------|-----|
| `qiurui144/KVM` | LLM provider registry + audit hash-chain primitives | **copy patterns, don't duplicate code** |
| `qiurui144/kvm-rknn-models` | RKNN INT8 model zoo | reference for fast-tier on RK3588 |
| `qiurui144/kvm-build-env` | aarch64/riscv64 cross-build base image | use as `FROM` for multi-arch |
| `qiurui144/kvm-privacy` | Privacy redaction SDK | hide PII fields from digest |
| `qiurui144/kvm-rtp` / `kvm-webcodecs-client` | unrelated (video) | ignore |
