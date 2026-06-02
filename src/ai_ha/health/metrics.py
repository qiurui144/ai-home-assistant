"""In-memory health metric collector. /api/health reads snapshot() once per request."""
from __future__ import annotations

from collections import deque
from typing import Any


class HealthMetrics:
    def __init__(self, *, install_start_ms: int) -> None:
        self._start_ms = install_start_ms
        self._ws_connected = False
        self._event_log_recent: deque[int] = deque()  # ts_ms, kept rolling 1h
        self._hidden_total = 0
        self._db_size_bytes = 0
        self._topology_snapshot_id: int | None = None
        self._wal_recovery_count = 0
        self._privacy_compile_fail = 0
        self._config_reload_fail = 0
        self._ha_version: str | None = None

    def set_ws_connected(self, ok: bool) -> None:
        self._ws_connected = ok

    def set_db_size(self, bytes_: int) -> None:
        self._db_size_bytes = bytes_

    def set_topology_snapshot_id(self, sid: int) -> None:
        self._topology_snapshot_id = sid

    def set_ha_version(self, v: str) -> None:
        self._ha_version = v

    def inc_wal_recovery(self) -> None:
        self._wal_recovery_count += 1

    def inc_privacy_compile_fail(self) -> None:
        self._privacy_compile_fail += 1

    def inc_config_reload_fail(self) -> None:
        self._config_reload_fail += 1

    def record_event(self, *, ts_ms: int) -> None:
        self._event_log_recent.append(ts_ms)
        cutoff = ts_ms - 3_600_000
        while self._event_log_recent and self._event_log_recent[0] < cutoff:
            self._event_log_recent.popleft()

    def record_privacy_drop(self) -> None:
        self._hidden_total += 1

    def snapshot(self, *, now_ms: int) -> dict[str, Any]:
        cutoff = now_ms - 3_600_000
        while self._event_log_recent and self._event_log_recent[0] < cutoff:
            self._event_log_recent.popleft()
        uptime = max(0, (now_ms - self._start_ms) // 1000)
        return {
            "status": "healthy" if self._ws_connected else "degraded",
            "ws_connected": self._ws_connected,
            "events_per_hour": len(self._event_log_recent),
            "db_size_mb": round(self._db_size_bytes / 1_000_000, 2),
            "uptime_seconds": uptime,
            "hidden_event_count": self._hidden_total,
            "current_topology_snapshot_id": self._topology_snapshot_id,
            "ha_version_seen": self._ha_version,
            "wal_recovery_count": self._wal_recovery_count,
            "privacy_regex_compile_fail_total": self._privacy_compile_fail,
            "config_reload_fail_total": self._config_reload_fail,
        }
