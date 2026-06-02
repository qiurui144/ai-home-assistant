import pytest
from httpx import ASGITransport, AsyncClient

from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore


@pytest.mark.asyncio
async def test_health_returns_json(tmp_path):
    store = AdminTokenStore(str(tmp_path / "t"))
    store.ensure_token()
    app = create_app(token_store=store)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("healthy", "degraded")
