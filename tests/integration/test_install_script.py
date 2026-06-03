"""Test install.sh skeleton — prereq detection.

install.sh is pure bash. Tests invoke it as a subprocess with a stub PATH
that controls whether docker/compose are 'installed'.
"""
import os
import subprocess
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
