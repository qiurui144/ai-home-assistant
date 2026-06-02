# v0.1.0 Test Plan

## Objective

Verify all 17 acceptance gates (G1-G17 per spec Appendix C) and 14 error cases
(spec §7) before tagging v0.1.0 GA.

## Matrix

| Layer | Tool | Coverage target |
|-------|------|-----------------|
| Unit | pytest | line 80% / branch 60% |
| Integration | pytest + MockHAServer | 12 HTTP endpoints + WS + 14 error cases |
| Perf | pytest + manual timing | ingest p99 < 100ms / API p99 < 50ms |
| Soak | tests/soak harness | 7d real-wallclock, real or mock HA |
| Multi-arch | docker buildx | amd64/arm64/riscv64 build + amd64 native test + real RK3588 verify |

## Black-box / Grey-box / White-box

- **Black-box (G1/G5/G6/G7/G9/G16/G17)**: real RK3588 board, real HA, real
  browser. No mocks. G7 evidence: grep DB/jsonl/logs for `entity_id` after 100
  privacy-hit events → 0/0/0 hits.
- **Grey-box (G2/G3/G10/G11/G12)**: MockHAServer + ASGITransport, measured.
- **White-box (G13/G15)**: pytest --cov; grep `except.*pass`.

## Pass criteria

Per spec Appendix C: 17/17 must PASS. Any single fail = no GA tag.

## Test history (per release)

| v0.1.0 | date | run | result |
|--------|------|-----|--------|
| | | | |
