import asyncio

import pytest

from ai_ha.ha_adapter.ws_client import HAWSClient


@pytest.mark.asyncio
async def test_connect_and_subscribe(mock_ha):
    events: list[dict] = []

    async def on_event(e: dict) -> None:
        events.append(e)

    client = HAWSClient(
        url=f"ws://127.0.0.1:{mock_ha.port}",
        token="test-token-not-real",
        on_event=on_event,
    )
    task = asyncio.create_task(client.run())
    await asyncio.sleep(0.2)
    await mock_ha.push_event("light.x", old="off", new="on")
    await asyncio.sleep(0.2)
    client.stop()
    await task
    assert any(e.get("event", {}).get("data", {}).get("entity_id") == "light.x" for e in events)


@pytest.mark.asyncio
async def test_auth_invalid_does_not_retry_forever(mock_ha):
    async def noop(_e: dict) -> None:
        pass

    client = HAWSClient(
        url=f"ws://127.0.0.1:{mock_ha.port}", token="wrong",
        on_event=noop,
        max_reconnect_seconds=2,
    )
    task = asyncio.create_task(client.run())
    await asyncio.sleep(1.0)
    client.stop()
    await task
    assert client.last_error_kind == "auth-invalid"


@pytest.mark.asyncio
async def test_reconnects_on_drop(mock_ha):
    events: list[dict] = []

    async def on_event(e: dict) -> None:
        events.append(e)

    client = HAWSClient(
        url=f"ws://127.0.0.1:{mock_ha.port}",
        token="test-token-not-real",
        on_event=on_event,
        initial_backoff=0.1, max_backoff=0.5,
    )
    task = asyncio.create_task(client.run())
    await asyncio.sleep(0.3)
    await mock_ha.disconnect_all()
    await asyncio.sleep(0.6)
    await mock_ha.push_event("light.y", old=None, new="on")
    await asyncio.sleep(0.3)
    client.stop()
    await task
    assert any(
        e.get("event", {}).get("data", {}).get("entity_id") == "light.y" for e in events
    )
    assert client.disconnect_count >= 1
