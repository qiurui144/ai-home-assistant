import httpx
import pytest
import respx
from httpx import Response

from ai_ha.ha_adapter.client import HAAuthInvalid, HAClient, HAUnreachable


@pytest.mark.asyncio
@respx.mock
async def test_fetch_states_returns_list():
    respx.get("http://ha/api/states").mock(
        return_value=Response(200, json=[
            {"entity_id": "light.x", "state": "on", "last_updated": "2026-06-02T10:00:00+00:00"},
        ])
    )
    c = HAClient("http://ha", "tok")
    states = await c.fetch_states()
    assert states[0]["entity_id"] == "light.x"
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_auth_invalid_raises():
    respx.get("http://ha/api/states").mock(return_value=Response(401))
    c = HAClient("http://ha", "tok")
    with pytest.raises(HAAuthInvalid):
        await c.fetch_states()
    await c.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_unreachable_raises():
    respx.get("http://ha/api/states").mock(side_effect=httpx.ConnectError("nope"))
    c = HAClient("http://ha", "tok", connect_retries=2)
    with pytest.raises(HAUnreachable):
        await c.fetch_states()
    await c.aclose()
