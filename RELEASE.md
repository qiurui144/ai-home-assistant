# Release notes

## v0.1.0-rc.1 — 2026-06-02 (Listen-only Foundation — Release Candidate)

### Highlights

- HA WebSocket subscribe with auto-reconnect (exponential backoff 1→60s)
- Topology snapshot ingestion: areas / devices / entities; append-only versioned
- Room-aware Web UI (5 pages: rooms grid / room detail / entities / timeline / settings)
- Privacy hide-pattern with ReDoS guard; hot-reload via watchfiles
- 6+ health metrics on `/api/health` (`ws_connected` / `events_per_hour` / `db_size_mb` /
  `hidden_event_count` / `uptime_seconds` / `current_topology_snapshot_id`)
- Multi-arch Docker image (amd64/arm64; riscv64 build-only)

### Breaking changes

None — first release.

### Migration

None — first release.

### Known limitations

- **Listen-only**: no LLM, no learning, no automation suggestions. v0.4 starts the AI layer.
- **No HA write**: read-only. v0.6 introduces soft-intention queue.
- **No multi-user / voice ID**: single household. v1.1 adds voiceprint.
- **riscv64**: image builds in CI but runtime is untested (K3 hardware deferred per spec G17).
- **High event rate (>5k/h on eMMC)**: tested upper bound. Use NVMe for higher.
- **SIGKILL data loss**: in-memory buffer (max 1000) discarded; v0.6+ evaluates WAL buffer.

### Tested HA versions

- HA Core 2026.5.x ✓
- HA Core 2026.6.x ✓
- Older HA (< 2024.x): falls back to 60s polling for registry; degraded mode.

### Hardware verification

- amd64 (dev workstation): smoke ✓ (`/api/health` 200, first-run banner OK)
- arm64 (Rockchip RK3588 NanoPC-T6): **PENDING** — user must verify on real board (see `tests/MANUAL_TEST_CHECKLIST.md`)
- riscv64 (SpacemiT K1/K3): NOT yet — CI build only

### Verification evidence

- 96 unit + integration tests PASS (`pytest tests/unit tests/integration`)
- ruff clean + mypy --strict clean across 39 source files
- Perf benchmarks (G3, G10) PASS with comfortable margins:
  - Ingest p99: ~7.5ms (target < 100ms)
  - `/api/health` p99: ~0.6ms (target < 50ms)
  - `/api/v1/areas` p99: ~21ms (target < 200ms)
- 7d soak (G1): **PENDING** — see `tests/soak/README.md`. Run before GA tag.
- RK3588 hardware verification (G17): **PENDING** — see `tests/MANUAL_TEST_CHECKLIST.md`

### Status

v0.1.0-rc.1 is a release candidate. **GA tag (v0.1.0) requires Task 31 manual
verification on real RK3588 hardware + 7d soak run.**

Spec: [docs/specs/2026-05-25-ai-home-assistant-architecture.md](docs/specs/2026-05-25-ai-home-assistant-architecture.md)
Plan: [docs/superpowers/plans/2026-06-02-ai-home-assistant-v010-listen-only.md](docs/superpowers/plans/2026-06-02-ai-home-assistant-v010-listen-only.md)
