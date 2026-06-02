"""Hot-reload watcher for /data/config.toml.

Reads the file 50 ms after a Change event (half-write protection per spec §11 risk #8).
Calls on_change with new AppConfig; on validation failure, calls on_error and keeps old config.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from watchfiles import awatch

from ai_ha.config.loader import AppConfig, ConfigError, load_config

logger = logging.getLogger(__name__)


class ConfigWatcher:
    def __init__(
        self,
        path: str | Path,
        on_change: Callable[[AppConfig], Awaitable[None]],
        *,
        on_error: Callable[[Exception], Awaitable[None]] | None = None,
        debounce_ms: int = 200,
    ) -> None:
        self._path = Path(path)
        self._on_change = on_change
        self._on_error = on_error
        self._debounce = debounce_ms / 1000.0
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        # force_polling=True + poll_delay_ms=50 ensure reliable change detection on
        # Docker bind-mounts where inotify events don't propagate from the host.
        # debounce=100 ms (watchfiles default is 1600 ms) keeps the loop responsive
        # during tests; production code may increase debounce_ms via the constructor.
        async for _changes in awatch(
            self._path,
            stop_event=self._stop,
            force_polling=True,
            poll_delay_ms=50,
            debounce=100,
        ):
            await asyncio.sleep(self._debounce)
            try:
                cfg = load_config(self._path)
            except ConfigError as exc:
                logger.warning("config reload failed, keeping old: %s", exc)
                if self._on_error:
                    await self._on_error(exc)
                continue
            await self._on_change(cfg)
