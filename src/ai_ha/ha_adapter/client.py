"""HA REST client (auth header + state snapshot)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)


class HAUnreachable(RuntimeError):
    """REST endpoint unreachable after retries."""


class HAAuthInvalid(RuntimeError):
    """HA returned 401/403 — token is bad."""


class HAClient:
    def __init__(
        self, base_url: str, token: str, *,
        timeout_s: float = 10.0, connect_retries: int = 5,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._client = httpx.AsyncClient(
            base_url=self._base, timeout=timeout_s, headers=self._headers,
        )
        self._retries = connect_retries

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_states(self) -> list[dict[str, Any]]:
        delay = 1.0
        for attempt in range(self._retries):
            try:
                r = await self._client.get("/api/states")
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                logger.warning("ha REST attempt %d failed: %s", attempt + 1, exc)
                if attempt + 1 == self._retries:
                    raise HAUnreachable(f"after {self._retries} attempts") from exc
                await asyncio.sleep(delay)
                delay = min(60.0, delay * 2)
                continue
            if r.status_code in (401, 403):
                raise HAAuthInvalid(f"status={r.status_code}")
            r.raise_for_status()
            return cast(list[dict[str, Any]], r.json())
        raise HAUnreachable("retries exhausted")
