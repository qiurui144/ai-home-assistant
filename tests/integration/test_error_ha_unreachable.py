import pytest

from ai_ha.ha_adapter.client import HAClient, HAUnreachable


@pytest.mark.asyncio
async def test_rest_unreachable_raises_after_retries():
    c = HAClient("http://127.0.0.1:1", "tok", connect_retries=2)
    with pytest.raises(HAUnreachable):
        await c.fetch_states()
    await c.aclose()
