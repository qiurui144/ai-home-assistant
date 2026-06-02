from ai_ha.health.metrics import HealthMetrics


def test_initial_snapshot():
    m = HealthMetrics(install_start_ms=0)
    s = m.snapshot(now_ms=1_000)
    assert s["uptime_seconds"] == 1
    assert s["ws_connected"] is False
    assert s["events_per_hour"] == 0


def test_record_event_increments_rate():
    m = HealthMetrics(install_start_ms=0)
    base = 3_600_000  # bucket = 1
    m.record_event(ts_ms=base + 1000)
    m.record_event(ts_ms=base + 2000)
    s = m.snapshot(now_ms=base + 3000)
    assert s["events_per_hour"] == 2


def test_record_event_drops_old_buckets():
    m = HealthMetrics(install_start_ms=0)
    m.record_event(ts_ms=0)
    m.record_event(ts_ms=3_600_000 * 2)  # 2 hours later
    s = m.snapshot(now_ms=3_600_000 * 2)
    # within last hour: just the second event
    assert s["events_per_hour"] == 1


def test_set_ws_connected():
    m = HealthMetrics(install_start_ms=0)
    m.set_ws_connected(True)
    assert m.snapshot(now_ms=1000)["ws_connected"] is True


def test_record_privacy_drop():
    m = HealthMetrics(install_start_ms=0)
    m.record_privacy_drop()
    m.record_privacy_drop()
    assert m.snapshot(now_ms=1000)["hidden_event_count"] == 2
