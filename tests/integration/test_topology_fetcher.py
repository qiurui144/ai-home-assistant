import pytest

from ai_ha.ha_adapter.topology_fetcher import TopologyFetcher


@pytest.mark.asyncio
async def test_fetch_returns_three_lists(mock_ha):
    mock_ha.set_topology(
        areas=[{"area_id": "a1", "name": "Living"}],
        devices=[{"device_id": "d1", "area_id": "a1"}],
        entities=[{"entity_id": "light.x", "device_id": "d1"}],
    )
    f = TopologyFetcher(url=f"ws://127.0.0.1:{mock_ha.port}", token="test-token-not-real")
    payload = await f.fetch_once()
    assert len(payload.areas) == 1
    assert len(payload.devices) == 1
    assert len(payload.entities) == 1


@pytest.mark.asyncio
async def test_fetch_auth_invalid_raises(mock_ha):
    f = TopologyFetcher(url=f"ws://127.0.0.1:{mock_ha.port}", token="wrong")
    with pytest.raises(RuntimeError):
        await f.fetch_once()
