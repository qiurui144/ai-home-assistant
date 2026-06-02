"""Coverage for stream.py: router registration + broadcaster subscribe cleanup."""
from __future__ import annotations

import asyncio

import pytest

from ai_ha.web.routes.stream import EventBroadcaster, build_ws_router


def test_build_ws_router_registers_ws_endpoint():
    """build_ws_router must expose /api/v1/stream/events as a WebSocket route."""
    bc = EventBroadcaster()
    router = build_ws_router(bc)
    paths = [r.path for r in router.routes]
    assert "/api/v1/stream/events" in paths


@pytest.mark.asyncio
async def test_broadcaster_subscribe_cleanup_after_aclose():
    """subscribe() context manager removes its queue on generator close."""
    bc = EventBroadcaster()

    async def open_and_close() -> None:
        gen = bc.subscribe()
        # Immediately close without consuming any events
        await gen.aclose()

    await open_and_close()
    assert len(bc._queues) == 0


@pytest.mark.asyncio
async def test_broadcaster_multiple_subscribers_cleanup():
    """All subscriber queues are removed after generators are closed."""
    bc = EventBroadcaster()

    async def sub_and_close() -> None:
        gen = bc.subscribe()
        await gen.aclose()

    await asyncio.gather(sub_and_close(), sub_and_close(), sub_and_close())
    assert len(bc._queues) == 0


@pytest.mark.asyncio
async def test_broadcaster_publish_to_zero_subscribers_is_noop():
    """publish() with no subscribers must not raise."""
    bc = EventBroadcaster()
    await bc.publish({"entity_id": "light.test", "ts": 1})  # should not raise
