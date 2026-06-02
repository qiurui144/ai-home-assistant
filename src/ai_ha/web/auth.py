"""Admin token persistence + Basic-Auth dependency.

Token: 32-byte random, written 0600 to /data/.admin-token, printed once on first run.
v0.1.0 has a single 'admin' user. No multi-user, no OAuth.
"""
from __future__ import annotations

import os
import secrets
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials


class AdminTokenStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def ensure_token(self) -> str:
        if self._path.exists():
            return self.read()
        tok = secrets.token_urlsafe(32)
        self._path.write_text(tok)
        os.chmod(self._path, 0o600)
        return tok

    def read(self) -> str:
        return self._path.read_text().strip()


_basic = HTTPBasic(auto_error=False)


def make_require_admin(
    token_store: AdminTokenStore, *, require_auth: bool
) -> Callable[..., Awaitable[None]]:
    async def _dep(creds: HTTPBasicCredentials | None = Depends(_basic)) -> None:  # noqa: B008
        if not require_auth:
            return
        if creds is None or creds.username != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "auth-required", "detail": "admin token needed"},
                headers={"WWW-Authenticate": "Basic"},
            )
        token = token_store.read()
        if not secrets.compare_digest(creds.password, token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "auth-invalid", "detail": "bad token"},
            )
    return _dep
