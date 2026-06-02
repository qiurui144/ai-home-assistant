"""Read run-<ts>/metrics.jsonl, compute uptime% / mem trend / disconnect count."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def main(run_dir: str) -> int:
    p = Path(run_dir) / "metrics.jsonl"
    rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    if not rows:
        print("no rows")
        return 1
    total = len(rows)
    healthy = sum(1 for r in rows if '"status": "healthy"' in r.get("health", ""))
    uptime_pct = healthy / total * 100
    disconnects = 0
    for r in rows:
        m = re.search(r'"disconnect_count":\s*(\d+)', r.get("health", ""))
        if m:
            disconnects += int(m.group(1))
    summary = Path(run_dir) / "summary.md"
    summary.write_text(
        f"# Soak summary\n\n"
        f"- samples: {total}\n"
        f"- ws_connected uptime: {uptime_pct:.2f}% (G1 ≥ 99.5%)\n"
        f"- disconnect events: {disconnects}\n"
    )
    print(summary.read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
