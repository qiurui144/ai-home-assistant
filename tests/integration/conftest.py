import pytest_asyncio

from tests.integration.mock_ha_server import MockHAServer


@pytest_asyncio.fixture
async def mock_ha():
    srv = MockHAServer()
    await srv.start()
    yield srv
    await srv.stop()
