"""Daily-rotating JSONL writer with optional gzip.

Filename: YYYY-MM-DD.jsonl[.gz] in UTC. Append-only; on day rollover, the current
file handle is closed and a new file is opened. Flush is explicit (called by ingest
batch commit). No buffer cap — if disk fills, OSError surfaces to caller.
"""
from __future__ import annotations

import asyncio
import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any


class JsonlWriter:
    def __init__(self, directory: str | Path, *, compress: bool = True) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._compress = compress
        self._current_day: str | None = None
        self._handle: IO[str] | None = None
        self._lock = asyncio.Lock()

    def _path_for_day(self, day: str) -> Path:
        suffix = ".jsonl.gz" if self._compress else ".jsonl"
        return self._dir / f"{day}{suffix}"

    def _ensure_day(self, day: str) -> None:
        if self._current_day == day and self._handle is not None:
            return
        if self._handle is not None:
            self._handle.close()
        path = self._path_for_day(day)
        if self._compress:
            self._handle = gzip.open(path, "at")  # text-append
        else:
            self._handle = open(path, "a", encoding="utf-8")
        self._current_day = day

    async def append(self, record: dict[str, Any], *, ts_ms: int) -> None:
        day = datetime.fromtimestamp(ts_ms / 1000.0, UTC).strftime("%Y-%m-%d")
        async with self._lock:
            self._ensure_day(day)
            assert self._handle is not None  # noqa: S101
            self._handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def flush(self) -> None:
        async with self._lock:
            if self._handle is not None:
                self._handle.flush()

    async def close(self) -> None:
        async with self._lock:
            if self._handle is not None:
                self._handle.close()
                self._handle = None
                self._current_day = None
