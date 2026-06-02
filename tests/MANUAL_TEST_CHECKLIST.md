# v0.1.0 Manual Test Checklist

> Run on real RK3588 board (per spec §9.5) with real Home Assistant. Tick each
> box and paste evidence (screenshot path / curl output / log excerpt).

## First-run

- [ ] Container starts; stdout shows admin token (red banner) once
- [ ] /data/.admin-token created with 0600
- [ ] Browser http://<board>:8124 redirects to /login; token works

## Topology

- [ ] /api/v1/topology returns snapshot_id ≥ 1 within 30s
- [ ] Web UI / (rooms grid) shows all my HA areas with name
- [ ] Move an entity to a different area in HA → ai-ha new snapshot within 5s
  (check /api/v1/topology/snapshots count increased)
- [ ] Orphan detection: leave one entity unassigned in HA → /entities?orphan=true
  returns it

## Privacy

- [ ] /settings shows current hide_entities_pattern (default empty)
- [ ] Add pattern `sensor\.bank_card_.*` and save → settings.html shows new pattern
- [ ] Trigger 10 state changes on a hidden entity → /api/v1/events does NOT show them
- [ ] grep /data/ai-ha.db for hidden entity_id → 0 hits
- [ ] grep /data/events/*.jsonl.gz | grep entity_id of hidden → 0 hits
- [ ] grep docker logs aiha for entity_id of hidden → 0 hits
- [ ] /api/health hidden_event_count ≥ 10

## Web UI

- [ ] Chrome desktop: 5 pages render, 0 console errors
- [ ] Firefox desktop: ditto
- [ ] Safari desktop: ditto
- [ ] Chrome mobile viewport (≤ 400 px): rooms grid usable

## Multi-arch

- [ ] amd64 image starts + /api/health 200
- [ ] arm64 image (RK3588 native): starts + /api/health 200
- [ ] riscv64 buildx PASS (no runtime test — deferred per spec G17)

## Soak

- [ ] tests/soak/runs/run-<ts>/summary.md present, uptime ≥ 99.5%

## Acceptance gates (Appendix C)

- [ ] G1 7d uptime
- [ ] G2 reconnect p95 < 30s
- [ ] G3 ingest p99 < 100ms
- [ ] G4 events_received == events_in_db (during online window)
- [ ] G5 topology count matches HA UI
- [ ] G6 registry update detected ≤ 5s
- [ ] G7 privacy 0/0/0
- [ ] G8 privacy hot-reload < 5s
- [ ] G9 3 browsers 0 console errors
- [ ] G10 API p99 < 50/200ms
- [ ] G11 RAM < 300/500 MB
- [ ] G12 DB < 50 MB/1k events
- [ ] G13 unit 80%/60%
- [ ] G14 integration 12+WS=14 PASS
- [ ] G15 grep `except.*pass` = 0
- [ ] G16 docs synced
- [ ] G17 amd64 + arm64 + riscv64 build + RK3588 real
