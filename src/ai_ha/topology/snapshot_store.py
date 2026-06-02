"""Append-only versioned topology snapshots.

Each TopologyPayload is hashed (canonical JSON, sha256). If hash matches the most
recent snapshot, no new row is inserted — same snapshot_id is returned. Otherwise
a new row appends with auto-incrementing snapshot_id. Old rows are never modified.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from ai_ha.store.db import Database


@dataclass(frozen=True)
class TopologyPayload:
    areas: list[dict[str, Any]] = field(default_factory=list)
    devices: list[dict[str, Any]] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)

    def to_canonical_json(self) -> str:
        return json.dumps(
            {"areas": self.areas, "devices": self.devices, "entities": self.entities},
            sort_keys=True,
            separators=(",", ":"),
        )

    def hash_hex(self) -> str:
        return hashlib.sha256(self.to_canonical_json().encode()).hexdigest()


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: int
    ts_ms: int
    payload_hash: str
    payload: TopologyPayload
    diff_summary: str | None


class SnapshotStore:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_current(self) -> Snapshot | None:
        async with self._db.connect() as c:
            row = await (await c.execute(
                "SELECT snapshot_id, ts, payload_hash, payload, diff_summary "
                "FROM topology_snapshots ORDER BY snapshot_id DESC LIMIT 1"
            )).fetchone()
        if row is None:
            return None
        return _row_to_snapshot(row)

    async def insert_if_changed(
        self,
        payload: TopologyPayload,
        *,
        ts_ms: int,
        diff_summary: str | None = None,
    ) -> tuple[int, bool]:
        new_hash = payload.hash_hex()
        async with self._db.connect() as c:
            row = await (await c.execute(
                "SELECT snapshot_id FROM topology_snapshots WHERE payload_hash=?",
                (new_hash,),
            )).fetchone()
            if row is not None:
                return int(row[0]), False
            cur = await c.execute(
                "INSERT INTO topology_snapshots(ts, payload_hash, payload, diff_summary) "
                "VALUES (?, ?, ?, ?)",
                (ts_ms, new_hash, payload.to_canonical_json(), diff_summary),
            )
            await c.commit()
            assert cur.lastrowid is not None
            return int(cur.lastrowid), True


def _row_to_snapshot(row: Any) -> Snapshot:
    raw = json.loads(row[3])
    return Snapshot(
        snapshot_id=int(row[0]),
        ts_ms=int(row[1]),
        payload_hash=str(row[2]),
        payload=TopologyPayload(
            areas=raw.get("areas", []),
            devices=raw.get("devices", []),
            entities=raw.get("entities", []),
        ),
        diff_summary=row[4],
    )
