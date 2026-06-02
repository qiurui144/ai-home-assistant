"""Hour-bucket arithmetic for counters_per_area."""
from __future__ import annotations

import time

_HOUR_MS = 3_600_000


class HourBucketRing:
    def bucket_for(self, ts_ms: int) -> int:
        return ts_ms // _HOUR_MS

    def now_bucket(self, *, now_ms: int | None = None) -> int:
        if now_ms is None:
            now_ms = int(time.time() * 1000)
        return now_ms // _HOUR_MS
