"""Minimal HA-compatible WebSocket server for integration tests.

Implements: auth handshake, subscribe_events (state_changed firehose),
config/{area,device,entity}_registry/list, *_registry_updated events.
Not a full HA simulator — only the surface ai-ha needs.
"""
from __future__ import annotations

import json
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection, serve


class MockHAServer:
    def __init__(self) -> None:
        self.port: int = 0
        self._token = "test-token-not-real"
        self._areas: list[dict[str, Any]] = []
        self._devices: list[dict[str, Any]] = []
        self._entities: list[dict[str, Any]] = []
        self._states: list[dict[str, Any]] = []
        self._connections: set[ServerConnection] = set()
        self._server: Any = None
        self._next_id = 1

    async def start(self) -> None:
        self._server = await serve(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        for c in list(self._connections):
            await c.close()
        self._server.close()
        await self._server.wait_closed()

    def set_topology(
        self, areas: list[dict[str, Any]], devices: list[dict[str, Any]],
        entities: list[dict[str, Any]],
    ) -> None:
        self._areas, self._devices, self._entities = areas, devices, entities

    def set_states(self, states: list[dict[str, Any]]) -> None:
        self._states = states

    async def push_event(self, entity_id: str, *, old: str | None, new: str) -> None:
        for c in list(self._connections):
            await c.send(json.dumps({
                "id": 1, "type": "event",
                "event": {
                    "event_type": "state_changed",
                    "data": {
                        "entity_id": entity_id,
                        "old_state": {"state": old} if old is not None else None,
                        "new_state": {"state": new},
                    },
                    "time_fired": "2026-06-02T10:00:00+00:00",
                },
            }))

    async def push_registry_updated(self, kind: str) -> None:
        assert kind in ("area", "device", "entity")
        for c in list(self._connections):
            await c.send(json.dumps({
                "id": 1, "type": "event",
                "event": {"event_type": f"{kind}_registry_updated", "data": {}},
            }))

    async def disconnect_all(self) -> None:
        for c in list(self._connections):
            await c.close()

    async def _handle(self, ws: ServerConnection) -> None:
        self._connections.add(ws)
        try:
            await ws.send(json.dumps({"type": "auth_required"}))
            msg = json.loads(await ws.recv())
            if msg.get("access_token") != self._token:
                await ws.send(json.dumps({"type": "auth_invalid"}))
                return
            await ws.send(json.dumps({"type": "auth_ok"}))
            async for raw in ws:
                req = json.loads(raw)
                await self._dispatch(ws, req)
        except websockets.ConnectionClosed:
            pass
        finally:
            self._connections.discard(ws)

    async def _dispatch(self, ws: ServerConnection, req: dict[str, Any]) -> None:
        rid = req.get("id", 0)
        t = req.get("type", "")
        if t == "subscribe_events":
            await ws.send(json.dumps({"id": rid, "type": "result", "success": True}))
        elif t == "config/area_registry/list":
            await ws.send(json.dumps({
                "id": rid, "type": "result", "success": True, "result": self._areas,
            }))
        elif t == "config/device_registry/list":
            await ws.send(json.dumps({
                "id": rid, "type": "result", "success": True, "result": self._devices,
            }))
        elif t == "config/entity_registry/list":
            await ws.send(json.dumps({
                "id": rid, "type": "result", "success": True, "result": self._entities,
            }))
        else:
            await ws.send(json.dumps({
                "id": rid, "type": "result", "success": False,
                "error": {"code": "unknown_command", "message": t},
            }))
