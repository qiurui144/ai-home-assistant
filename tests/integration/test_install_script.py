"""Test install.sh skeleton — prereq detection.

install.sh is pure bash. Tests invoke it as a subprocess with a stub PATH
that controls whether docker/compose are 'installed'.
"""
import contextlib
import http.server
import os
import socketserver
import subprocess
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"


def _run_install(
    args: list[str], env_extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        env=env, capture_output=True, text=True, check=False,
    )


def test_install_sh_exists_executable():
    assert INSTALL_SH.exists()
    assert os.access(INSTALL_SH, os.R_OK)


def test_help_flag_prints_usage():
    r = _run_install(["--help"])
    assert r.returncode == 0
    assert "ai-home-assistant" in r.stdout.lower()
    assert "install" in r.stdout.lower()


def test_missing_docker_exits_78(tmp_path):
    # Stub PATH with no docker — prepend fake empty bin dir so bash/ss remain
    # reachable but docker is not found.
    fake_path = tmp_path / "bin"
    fake_path.mkdir()
    stub_path = str(fake_path) + ":" + os.environ.get("PATH", "/usr/bin:/bin")
    r = _run_install([], env_extra={"PATH": stub_path, "AIHA_DRY_RUN": "1"})
    assert r.returncode == 78
    assert "docker" in r.stderr.lower()


def test_dry_run_shows_pull_plan(tmp_path):
    # Provide stub docker + ss so prereq passes, then dry-run skips real pulls.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "docker").write_text("#!/bin/sh\nexit 0\n")
    (fake_bin / "docker").chmod(0o755)
    (fake_bin / "ss").write_text("#!/bin/sh\nexit 0\n")
    (fake_bin / "ss").chmod(0o755)
    stub_path = str(fake_bin) + ":" + os.environ.get("PATH", "/usr/bin:/bin")
    r = _run_install(["--dry-run"], env_extra={
        "PATH": stub_path,
        "INSTALL_DIR": str(tmp_path / "ai-ha"),
    })
    # Dry-run after Task 2 should report intended docker pull
    assert r.returncode == 0
    assert "ghcr.io/qiurui144/ai-home-assistant" in r.stdout


def test_dry_run_mentions_ha_health_wait(tmp_path):
    fake_path = tmp_path / "bin"
    fake_path.mkdir()
    for binary in ("docker", "ss"):
        stub = fake_path / binary
        stub.write_text("#!/bin/sh\nexit 0\n")
        stub.chmod(0o755)
    r = _run_install(["--dry-run"], env_extra={
        "PATH": f"{fake_path}:{os.environ['PATH']}",
        "INSTALL_DIR": str(tmp_path / "ai-ha"),
    })
    assert r.returncode == 0
    assert "health" in r.stdout.lower() or "8123" in r.stdout


@contextlib.contextmanager
def mock_ha_validator(token: str = "valid-token"):  # noqa: S107
    """Tiny HTTP server that 200's for Bearer <token>, 401 otherwise."""
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            auth = self.headers.get("Authorization", "")
            if auth == f"Bearer {token}":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"message":"API running."}')
            else:
                self.send_response(401)
                self.end_headers()

        def log_message(self, *_args, **_kwargs):
            pass

    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()


def test_token_validation_rejects_invalid(tmp_path):
    """install.sh token validation should reject 401."""
    with mock_ha_validator("the-good-token") as port:
        r = subprocess.run(
            ["bash", "-c", f"source {INSTALL_SH}; HA_PORT={port} validate_token wrong-token"],
            capture_output=True, text=True, check=False,
        )
        assert r.returncode == 78
        assert "401" in r.stderr or "invalid" in r.stderr.lower()


def test_token_validation_accepts_valid(tmp_path):
    with mock_ha_validator("the-good-token") as port:
        r = subprocess.run(
            ["bash", "-c", f"source {INSTALL_SH}; HA_PORT={port} validate_token the-good-token"],
            capture_output=True, text=True, check=False,
        )
        assert r.returncode == 0
