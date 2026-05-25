# DEVELOP

> Developer onboarding for ai-home-assistant. Per the spec
> (`docs/specs/2026-05-25-ai-home-assistant-architecture.md`) and global
> CLAUDE.md, all builds and tests run inside Docker — no host pollution.

## Multi-arch dev cycle

```bash
# Build for your host arch (fast iteration)
cd docker
docker build -t ai-home-assistant:dev .

# Build multi-arch (CI / release)
docker buildx build \
  --platform linux/amd64,linux/arm64,linux/riscv64 \
  -t ghcr.io/qiurui144/ai-home-assistant:dev \
  --load .
```

riscv64 builds may take 3-5× longer than amd64 due to GCC limitations on
some native deps. CI runs riscv64 in parallel so it doesn't block.

## Run locally against an existing HA Core

```bash
docker run -d --name ai-ha-dev \
  -p 8124:8124 \
  -v $PWD/.dev-data:/data \
  -e HA_URL=http://<ha-host>:8123 \
  -e HA_TOKEN=<your-long-lived-token> \
  ai-home-assistant:dev
```

## Test layers (per spec §9)

| Layer | Command | Coverage target |
|-------|---------|-----------------|
| Unit  | `pytest tests/unit/` | 80% lines / 60% branches |
| Integration | `pytest tests/integration/` | All HTTP endpoints + WS events |
| Multi-arch CI | GitHub Actions matrix | amd64 / arm64 / riscv64 all green |
| Perf  | `pytest --benchmark` | digest p95 < 50ms / 1k events |

## Branch + push

Per parent KVM CLAUDE.md §git push 策略:

- Default `main`
- Direct push allowed after tests pass (private/personal project posture)
- Tags drive Docker image release (`v*.*.*` → CI builds + pushes to GHCR)

## Hardware testing

- **Primary**: RK3588 (NanoPC-T6) — same hardware as KVM main, can deploy
  as `kvm-nas-dual` image variant
- **Future migration**: SpacemiT K1/K3 (RISC-V) — CI catches breakage
  early via qemu-riscv64

## Spec-stage stubs

All Python modules under `src/ai_ha/` are currently empty placeholders.
The Docker container builds and runs, but `python -m ai_ha` just prints
a status banner and sleeps. v0.1.0 will replace this with the real
FastAPI app. See spec §12 timeline (6-week roadmap).
