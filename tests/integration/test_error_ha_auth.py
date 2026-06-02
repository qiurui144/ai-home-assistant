import pytest

from ai_ha.ha_adapter.ws_client import HAWSClient


@pytest.mark.asyncio
async def test_ws_auth_invalid_stops_retry(mock_ha):
    async def noop(_e: dict) -> None:
        pass

    client = HAWSClient(
        url=f"ws://127.0.0.1:{mock_ha.port}", token="bad",
        on_event=noop,
        max_reconnect_seconds=2,
    )
    await client.run()
    assert client.last_error_kind == "auth-invalid"
