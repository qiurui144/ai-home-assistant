"""Entry point — `python -m ai_ha`.

Spec-stage placeholder. v0.1.0 work item: replace the stub below with
the real FastAPI app per spec §4 / §5.1.
"""
import os
import sys


def main() -> int:
    config = os.environ.get("AI_HA_CONFIG", "/data/config.toml")
    data_dir = os.environ.get("AI_HA_DATA_DIR", "/data")

    print("[ai-ha] Starting ai-home-assistant (spec-stage build).", flush=True)
    print(f"[ai-ha] Config: {config}", flush=True)
    print(f"[ai-ha] Data dir: {data_dir}", flush=True)
    print(f"[ai-ha] HA URL: {os.environ.get('HA_URL', '<unset>')}", flush=True)
    print("[ai-ha] Listening on :8124 (planned — not implemented in this build).", flush=True)
    print("[ai-ha] Spec: docs/specs/2026-05-25-ai-home-assistant-architecture.md", flush=True)
    print("[ai-ha] v0.1.0 ETA: ~6 weeks from spec date 2026-05-25.", flush=True)
    print("[ai-ha] Container is healthy but does not yet do anything useful.", flush=True)

    # Wait for SIGTERM so the container stays "running" for docker-compose
    # status checks during the spec-stage period. Healthcheck endpoint will
    # 404 until web/ module lands; that's expected.
    try:
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("[ai-ha] Stopping.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
