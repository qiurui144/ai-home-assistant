import pytest
from httpx import ASGITransport, AsyncClient

from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore


@pytest.fixture
def token_store(tmp_path):
    s = AdminTokenStore(str(tmp_path / "t"))
    s.ensure_token()
    return s


@pytest.mark.asyncio
async def test_get_locales_returns_en_and_zh(token_store):
    app = create_app(token_store=token_store, require_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/locales")
        assert r.status_code == 200
        body = r.json()
        codes = {item["code"] for item in body}
        assert codes == {"en", "zh_CN"}


@pytest.mark.asyncio
async def test_post_lang_sets_cookie(token_store):
    app = create_app(token_store=token_store, require_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.post("/api/v1/lang", json={"lang": "zh"})
        assert r.status_code == 200
        cookie = r.headers.get("set-cookie", "")
        assert "ai-ha-lang=zh_CN" in cookie


@pytest.mark.asyncio
async def test_post_lang_invalid_returns_422(token_store):
    app = create_app(token_store=token_store, require_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.post("/api/v1/lang", json={"lang": "klingon"})
        assert r.status_code == 422
        assert r.json()["detail"]["error"] == "invalid-locale"
