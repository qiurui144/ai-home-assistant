# Running the test suite

## Inside Docker (recommended)

```bash
docker build -t ai-home-assistant:dev -f docker/Dockerfile .
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c \
  "pip install -e . && pytest tests/unit tests/integration -v"
```

## Coverage

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c \
  "pip install -e . && pytest --cov=src/ai_ha --cov-report=term-missing tests/unit tests/integration"
```

## Lint + types

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c \
  "pip install -e . && ruff check src/ tests/ && mypy src/"
```

## Perf benchmarks (marked slow)

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c \
  "pip install -e . && pytest tests/perf/bench_ingest.py tests/perf/bench_api.py -m slow -s"
```

## Soak (7 days; not in CI)

See `tests/soak/README.md`.

## Test layout

```
tests/
├── TEST_PLAN.md                       # SSOT for what we verify
├── MANUAL_TEST_CHECKLIST.md           # human verification on RK3588
├── TESTING.md                         # how to run (this file)
├── conftest.py
├── unit/                              # ~33 unit tests, no IO
├── integration/                       # ~30+ integration tests with MockHAServer
├── perf/                              # 3 timing benchmarks (G3/G10 gates)
└── soak/                              # 7-day uptime harness (G1 gate)
```
