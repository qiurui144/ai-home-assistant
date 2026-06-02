import gzip
import json
from datetime import UTC, datetime

import pytest

from ai_ha.archive.jsonl_writer import JsonlWriter


@pytest.mark.asyncio
async def test_append_and_read_back(tmp_path):
    w = JsonlWriter(str(tmp_path), compress=False)
    await w.append({"event_id": 1, "ts": 1000}, ts_ms=1_700_000_000_000)
    await w.flush()
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text().splitlines()
    assert json.loads(lines[0])["event_id"] == 1


@pytest.mark.asyncio
async def test_rotate_on_day_change(tmp_path):
    w = JsonlWriter(str(tmp_path), compress=False)
    ts1 = int(datetime(2026, 6, 1, 23, 50, tzinfo=UTC).timestamp() * 1000)
    await w.append({"e": 1}, ts_ms=ts1)
    ts2 = int(datetime(2026, 6, 2, 0, 10, tzinfo=UTC).timestamp() * 1000)
    await w.append({"e": 2}, ts_ms=ts2)
    await w.flush()
    files = sorted(tmp_path.glob("*.jsonl"))
    assert [f.name for f in files] == ["2026-06-01.jsonl", "2026-06-02.jsonl"]


@pytest.mark.asyncio
async def test_compress_appends_gz(tmp_path):
    w = JsonlWriter(str(tmp_path), compress=True)
    await w.append({"e": 1}, ts_ms=1_700_000_000_000)
    await w.flush()
    files = list(tmp_path.glob("*.jsonl.gz"))
    assert len(files) == 1
    with gzip.open(files[0], "rt") as f:
        line = f.readline()
    assert json.loads(line)["e"] == 1
