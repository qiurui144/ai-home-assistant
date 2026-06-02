import json

import pytest
import websockets


@pytest.mark.asyncio
async def test_auth_ok_flow(mock_ha):
    uri = f"ws://127.0.0.1:{mock_ha.port}"
    async with websockets.connect(uri) as ws:
        hello = json.loads(await ws.recv())
        assert hello["type"] == "auth_required"
        await ws.send(json.dumps({"type": "auth", "access_token": "test-token-not-real"}))
        ack = json.loads(await ws.recv())
        assert ack["type"] == "auth_ok"


@pytest.mark.asyncio
async def test_auth_invalid_flow(mock_ha):
    uri = f"ws://127.0.0.1:{mock_ha.port}"
    async with websockets.connect(uri) as ws:
        await ws.recv()  # auth_required
        await ws.send(json.dumps({"type": "auth", "access_token": "wrong"}))
        nak = json.loads(await ws.recv())
        assert nak["type"] == "auth_invalid"
