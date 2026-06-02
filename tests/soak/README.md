# Soak harness — 7-day uptime validation (G1 acceptance gate)

## Mode 1: against real HA (best — G1 evidence)

```bash
docker build -t ai-home-assistant:dev -f docker/Dockerfile .
export HA_URL=http://homeassistant.local:8123
export HA_TOKEN=<your long-lived token>
python -m tests.soak.run_soak --target=real-ha --container=aiha-soak
# After 7 days:
python -m tests.soak.analyze tests/soak/runs/run-<ts>/
```

## Mode 2: mock HA + synthetic traffic (CI-friendly)

```bash
docker build -t ai-home-assistant:dev -f docker/Dockerfile .
python -m tests.soak.run_soak --target=mock
```

The mock mode injects ~1k events/day and ~5 random disconnects across the 7 days.

## G1 acceptance criteria

`summary.md` must show:
- `ws_connected uptime ≥ 99.5%`
- `disconnect events`: only the ones we injected (no unexpected drops)

Commit `summary.md` to `docs/screenshots/v010-ga-verification/` as RC evidence.
