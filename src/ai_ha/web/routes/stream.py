"""In-process event broadcaster + WS endpoint.

Each WS client has its own bounded asyncio.Queue. publish() fans out; if a client
queue is full, oldest is dropped. No replay, no ack — Web UI reconnects on close.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


class EventBroadcaster:
    def __init__(self, *, queue_size: int = 500) -> None:
        self._queues: set[asyncio.Queue[dict[str, Any]]] = set()
        self._queue_size = queue_size

    async def publish(self, event: dict[str, Any]) -> None:
        for q in list(self._queues):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await q.put(event)

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._queue_size)
        self._queues.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._queues.discard(q)


def build_ws_router(broadcaster: EventBroadcaster) -> APIRouter:
    router = APIRouter()

    @router.websocket("/api/v1/stream/events")
    async def stream(ws: WebSocket) -> None:
        await ws.accept()
        try:
            async for ev in broadcaster.subscribe():
                await ws.send_text(json.dumps(ev, ensure_ascii=False))
        except WebSocketDisconnect:
            return

    return router
