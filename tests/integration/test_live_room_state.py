import asyncio

import pytest

from ai_ha.web.routes.stream import EventBroadcaster, publish_room_state


@pytest.mark.asyncio
async def test_room_state_broadcast_delivered():
    bc = EventBroadcaster()
    received: list[dict] = []

    async def listener() -> None:
        async for ev in bc.subscribe():
            received.append(ev)
            return

    t = asyncio.create_task(listener())
    await asyncio.sleep(0.05)
    await publish_room_state(bc, area_id="living", last_seen_at=1000, active=True, entity_count=8)
    await asyncio.wait_for(t, timeout=1.0)
    assert received[0]["type"] == "room_state"
    assert received[0]["entity_count"] == 8


@pytest.mark.asyncio
async def test_room_state_fanout_to_multiple_subscribers():
    bc = EventBroadcaster()
    received_a: list[dict] = []
    received_b: list[dict] = []

    async def listener(out: list[dict]) -> None:
        async for ev in bc.subscribe():
            out.append(ev)
            return

    ta = asyncio.create_task(listener(received_a))
    tb = asyncio.create_task(listener(received_b))
    await asyncio.sleep(0.05)
    await publish_room_state(bc, area_id="x", last_seen_at=1, active=True)
    await asyncio.gather(ta, tb)
    assert received_a == received_b
