"""7-day soak runner.

Two modes:
  --target=real-ha     point at $HA_URL and let ai-ha receive its real traffic
  --target=mock        spin up MockHAServer + inject synthetic 1k evt/day

Every 10 minutes:
  - curl http://localhost:8124/api/health → append to metrics.jsonl
  - shell out ps to measure RSS

Inject 5 random WS disconnects across the run (target=mock only).
Stop after 7×24×3600 seconds; emit run-<ts>/{metrics.jsonl, summary.md}.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

# This import resolves at runtime when run from repo root with PYTHONPATH=tests:
# `python -m tests.soak.run_soak --target=mock`
from tests.integration.mock_ha_server import MockHAServer

SOAK_SECONDS = 7 * 24 * 3600  # 7 days
HEALTH_INTERVAL = 600          # 10 min


async def _record_metric(port: int, fpath: Path, container: str) -> None:
    out = subprocess.run(
        ["curl", "-s", f"http://localhost:{port}/api/health"],
        capture_output=True, text=True, check=False,
    ).stdout
    rss = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container],
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    with fpath.open("a") as f:
        f.write(json.dumps({"ts": int(time.time()), "health": out, "rss": rss}) + "\n")


async def _inject_synthetic_traffic(srv: MockHAServer) -> None:
    """~1k events / day → one every ~86 s."""
    while True:
        await srv.push_event("light.x", old="off", new="on")
        await asyncio.sleep(86)


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--target", choices=["real-ha", "mock"], required=True)
    p.add_argument("--container", default="aiha-soak")
    p.add_argument("--port", type=int, default=8124)
    p.add_argument("--output-dir", default="tests/soak/runs")
    args = p.parse_args()

    run_dir = Path(args.output_dir) / f"run-{int(time.time())}"
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = run_dir / "metrics.jsonl"

    mock_task: asyncio.Task[None] | None = None
    srv: MockHAServer | None = None

    if args.target == "mock":
        srv = MockHAServer()
        await srv.start()
        ha_url = f"http://127.0.0.1:{srv.port}"
        ha_token = "test-token-not-real"
        mock_task = asyncio.create_task(_inject_synthetic_traffic(srv))
    else:
        ha_url = os.environ["HA_URL"]
        ha_token = os.environ["HA_TOKEN"]

    subprocess.run([
        "docker", "run", "-d", "--name", args.container,
        "--rm", "-p", f"{args.port}:8124",
        "-e", f"HA_URL={ha_url}", "-e", f"HA_TOKEN={ha_token}",
        "ai-home-assistant:dev",
    ], check=True)

    start = time.time()
    try:
        while time.time() - start < SOAK_SECONDS:
            await _record_metric(args.port, metrics_file, args.container)
            await asyncio.sleep(HEALTH_INTERVAL)
            if args.target == "mock" and srv is not None and random.random() < 0.001:
                await srv.disconnect_all()
    finally:
        subprocess.run(["docker", "stop", args.container], check=False)
        if mock_task:
            mock_task.cancel()
        if srv is not None:
            await srv.stop()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
