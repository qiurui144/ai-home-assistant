import asyncio

import pytest

from ai_ha.web.routes.stream import EventBroadcaster


@pytest.mark.asyncio
async def test_broadcast_delivers_to_listener():
    bc = EventBroadcaster()
    received: list[dict] = []

    async def listener() -> None:
        async for ev in bc.subscribe():
            received.append(ev)
            return

    t = asyncio.create_task(listener())
    await asyncio.sleep(0.05)
    await bc.publish({"entity_id": "light.x", "ts": 1})
    await asyncio.wait_for(t, timeout=1.0)
    assert received[0]["entity_id"] == "light.x"


@pytest.mark.asyncio
async def test_full_queue_drops_oldest():
    bc = EventBroadcaster(queue_size=2)
    gen = bc.subscribe()
    sub_task = asyncio.create_task(gen.__anext__())
    await asyncio.sleep(0.05)
    await bc.publish({"n": 1})
    await bc.publish({"n": 2})
    await bc.publish({"n": 3})  # 1 dropped
    first = await asyncio.wait_for(sub_task, timeout=0.5)
    second = await asyncio.wait_for(gen.__anext__(), timeout=0.5)
    assert first["n"] in (1, 2) and second["n"] in (2, 3)
    assert first["n"] != second["n"]


@pytest.mark.asyncio
async def test_broadcaster_publish_room_state_payload():
    """room_state messages have a 'type' field for client routing."""
    from ai_ha.web.routes.stream import EventBroadcaster

    bc = EventBroadcaster()
    received: list[dict] = []

    async def listener() -> None:
        async for ev in bc.subscribe():
            received.append(ev)
            return

    import asyncio
    t = asyncio.create_task(listener())
    await asyncio.sleep(0.05)
    await bc.publish(
        {"type": "room_state", "area_id": "living", "last_seen_at": 1000, "active": True}
    )
    await asyncio.wait_for(t, timeout=1.0)
    assert received[0]["type"] == "room_state"
    assert received[0]["area_id"] == "living"
