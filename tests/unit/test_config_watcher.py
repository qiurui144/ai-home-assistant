import asyncio
import os
import time

import pytest

from ai_ha.config.watcher import ConfigWatcher


def _touch_future(path, seconds: float = 2.0) -> None:
    """Advance mtime by `seconds` so watchfiles polling (1s mtime resolution) detects the change.

    watchfiles force_polling mode compares integer-second mtime from stat(). On overlay/Docker
    filesystems both writes may land in the same second, giving the same truncated mtime, so
    the watcher never fires.  Bumping mtime to now+2s guarantees a detectable delta regardless
    of when within the second the write happens.
    """
    t = time.time() + seconds
    os.utime(path, (t, t))


@pytest.mark.asyncio
async def test_watcher_fires_on_change(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text('[ha]\nurl = "http://x"\ntoken = "t"\n')
    fired: list[str] = []

    async def on_change(cfg) -> None:
        fired.append(cfg.ha.url)

    watcher = ConfigWatcher(str(cfg_path), on_change, debounce_ms=50)
    task = asyncio.create_task(watcher.run())
    await asyncio.sleep(0.1)
    cfg_path.write_text('[ha]\nurl = "http://y"\ntoken = "t"\n')
    _touch_future(cfg_path)
    await asyncio.sleep(0.5)
    watcher.stop()
    await task
    assert "http://y" in fired


@pytest.mark.asyncio
async def test_watcher_ignores_invalid_change(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text('[ha]\nurl = "http://x"\ntoken = "t"\n')
    errors: list[Exception] = []

    async def on_change(cfg) -> None:
        pass

    async def on_error(exc: Exception) -> None:
        errors.append(exc)

    watcher = ConfigWatcher(str(cfg_path), on_change, on_error=on_error, debounce_ms=50)
    task = asyncio.create_task(watcher.run())
    await asyncio.sleep(0.1)
    cfg_path.write_text("[broken\n")
    _touch_future(cfg_path)
    await asyncio.sleep(0.5)
    watcher.stop()
    await task
    assert len(errors) >= 1
