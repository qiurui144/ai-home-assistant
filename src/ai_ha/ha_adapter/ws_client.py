"""HA WebSocket client with auth handshake + reconnect + event push.

State machine: CONNECTING → AUTH → SUBSCRIBED → (event loop) → DISCONNECTED → CONNECTING.
On auth-invalid the loop stops (re-auth would not help). on_event runs in the same
task as the loop, so it must not block; ingest pipeline buffers in memory.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import websockets

logger = logging.getLogger(__name__)


class HAWSClient:
    def __init__(
        self, url: str, token: str,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
        *,
        initial_backoff: float = 1.0, max_backoff: float = 60.0,
        max_reconnect_seconds: float | None = None,
        ping_interval: float = 30.0,
    ) -> None:
        self._url = url
        self._token = token
        self._on_event = on_event
        self._initial_backoff = initial_backoff
        self._max_backoff = max_backoff
        self._stop = asyncio.Event()
        self._next_id = 1
        self._max_seconds = max_reconnect_seconds
        self._ping = ping_interval
        self.disconnect_count = 0
        self.last_error_kind: str | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        backoff = self._initial_backoff
        start = asyncio.get_event_loop().time()
        while not self._stop.is_set():
            if self._max_seconds is not None and \
                    asyncio.get_event_loop().time() - start > self._max_seconds:
                return
            try:
                await self._connect_and_loop()
                backoff = self._initial_backoff  # successful run resets backoff
            except _AuthInvalidError:
                self.last_error_kind = "auth-invalid"
                return  # do not retry
            except Exception as exc:
                self.last_error_kind = "ws-disconnected"
                logger.warning("ws loop ended: %s; sleep %.1fs", exc, backoff)
                self._connected = False
                self.disconnect_count += 1
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                return
            except TimeoutError:
                pass
            backoff = min(self._max_backoff, backoff * 2)

    async def _connect_and_loop(self) -> None:
        async with websockets.connect(
            self._url, ping_interval=self._ping, ping_timeout=self._ping,
        ) as ws:
            hello = json.loads(await ws.recv())
            if hello.get("type") != "auth_required":
                raise RuntimeError(f"unexpected hello: {hello}")
            await ws.send(json.dumps({"type": "auth", "access_token": self._token}))
            ack = json.loads(await ws.recv())
            if ack.get("type") == "auth_invalid":
                raise _AuthInvalidError
            if ack.get("type") != "auth_ok":
                raise RuntimeError(f"unexpected auth ack: {ack}")
            sub_id = self._next_id
            self._next_id += 1
            await ws.send(json.dumps({
                "id": sub_id, "type": "subscribe_events", "event_type": "state_changed",
            }))
            # also subscribe to registry updates
            for kind in ("area", "device", "entity"):
                self._next_id += 1
                await ws.send(json.dumps({
                    "id": self._next_id, "type": "subscribe_events",
                    "event_type": f"{kind}_registry_updated",
                }))
            self._connected = True
            while not self._stop.is_set():
                recv_task = asyncio.ensure_future(ws.recv())
                stop_task = asyncio.ensure_future(self._stop.wait())
                done, pending = await asyncio.wait(
                    {recv_task, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await t
                if stop_task in done:
                    recv_task.cancel()
                    return
                raw = recv_task.result()
                msg = json.loads(raw)
                if msg.get("type") == "event":
                    try:
                        await self._on_event(msg)
                    except Exception:
                        logger.exception("on_event raised")


class _AuthInvalidError(RuntimeError):
    pass
