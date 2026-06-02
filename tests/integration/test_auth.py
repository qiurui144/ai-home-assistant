import pytest
from httpx import ASGITransport, AsyncClient

from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore


@pytest.fixture
def token_store(tmp_path):
    tok_file = tmp_path / "token"
    store = AdminTokenStore(str(tok_file))
    store.ensure_token()
    return store


@pytest.mark.asyncio
async def test_health_requires_no_auth(token_store):
    app = create_app(token_store=token_store, require_auth=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/health")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_areas_requires_auth(token_store):
    app = create_app(token_store=token_store, require_auth=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/areas")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_areas_with_basic_auth_ok(token_store):
    app = create_app(token_store=token_store, require_auth=True)
    tok = token_store.read()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/areas", auth=("admin", tok))
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_require_auth_false_skips(token_store):
    app = create_app(token_store=token_store, require_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/areas")
        assert r.status_code == 200
