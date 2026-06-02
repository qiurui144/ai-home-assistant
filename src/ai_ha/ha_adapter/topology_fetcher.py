"""One-shot WS connection that pulls area/device/entity registry lists.

Returns a TopologyPayload.
"""
from __future__ import annotations

import json
from typing import Any, cast

import websockets

from ai_ha.topology.snapshot_store import TopologyPayload


class TopologyFetcher:
    def __init__(self, url: str, token: str, *, timeout_s: float = 10.0) -> None:
        self._url = url
        self._token = token
        self._timeout = timeout_s

    async def fetch_once(self) -> TopologyPayload:
        async with websockets.connect(self._url, open_timeout=self._timeout) as ws:
            await ws.recv()  # auth_required
            await ws.send(json.dumps({"type": "auth", "access_token": self._token}))
            ack = json.loads(await ws.recv())
            if ack.get("type") != "auth_ok":
                raise RuntimeError(f"auth failed: {ack}")
            areas = await self._request(ws, 1, "config/area_registry/list")
            devices = await self._request(ws, 2, "config/device_registry/list")
            entities = await self._request(ws, 3, "config/entity_registry/list")
        return TopologyPayload(areas=areas, devices=devices, entities=entities)

    @staticmethod
    async def _request(ws: Any, rid: int, cmd: str) -> list[dict[str, Any]]:
        await ws.send(json.dumps({"id": rid, "type": cmd}))
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            if msg.get("id") == rid and msg.get("type") == "result":
                if not msg.get("success"):
                    raise RuntimeError(f"{cmd} failed: {msg.get('error')}")
                return cast(list[dict[str, Any]], msg.get("result", []))
