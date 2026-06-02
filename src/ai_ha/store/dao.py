"""Data Access Objects for v0.1.0 schema.

Each DAO method maps to one or two SQL statements. UPSERT semantics preserve
first_seen_at on conflict. Bulk inserts use executemany. Queries return frozen
dataclasses so the calling code is type-safe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_ha.store.db import Database


@dataclass(frozen=True)
class AreaRow:
    area_id: str
    name: str
    floor_id: str | None
    icon: str | None
    aliases: str
    snapshot_id: int
    first_seen_at: int
    last_seen_at: int


@dataclass(frozen=True)
class DeviceRow:
    device_id: str
    name: str | None
    manufacturer: str | None
    model: str | None
    area_id: str | None
    sw_version: str | None
    snapshot_id: int
    first_seen_at: int
    last_seen_at: int


@dataclass(frozen=True)
class EntityRow:
    entity_id: str
    friendly_name: str | None
    domain: str
    device_class: str | None
    device_id: str | None
    area_id: str | None
    disabled: int
    snapshot_id: int
    first_seen_at: int
    last_seen_at: int
    event_count_24h: int
    total_event_count: int


@dataclass(frozen=True)
class EventRow:
    ts: int
    received_at: int
    entity_id: str
    event_type: str
    old_state: str | None
    new_state: str | None
    context_user_id: str | None
    context_parent_id: str | None
    area_id: str | None
    device_id: str | None
    device_class: str | None
    snapshot_id: int


class StoreDAO:
    def __init__(self, db: Database) -> None:
        self._db = db

    # ---------- areas ----------
    async def upsert_areas(self, rows: list[AreaRow]) -> None:
        if not rows:
            return
        async with self._db.connect() as c:
            await c.executemany(
                "INSERT INTO areas(area_id, name, floor_id, icon, aliases, "
                "  snapshot_id, first_seen_at, last_seen_at) "
                "VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(area_id) DO UPDATE SET "
                "  name=excluded.name, floor_id=excluded.floor_id, icon=excluded.icon, "
                "  aliases=excluded.aliases, snapshot_id=excluded.snapshot_id, "
                "  last_seen_at=excluded.last_seen_at",
                [(r.area_id, r.name, r.floor_id, r.icon, r.aliases,
                  r.snapshot_id, r.first_seen_at, r.last_seen_at) for r in rows],
            )
            await c.commit()

    async def list_areas(self) -> list[AreaRow]:
        async with self._db.connect() as c:
            rows = await (await c.execute(
                "SELECT area_id, name, floor_id, icon, aliases, "
                "snapshot_id, first_seen_at, last_seen_at FROM areas ORDER BY name"
            )).fetchall()
        return [AreaRow(*r) for r in rows]

    # ---------- devices ----------
    async def upsert_devices(self, rows: list[DeviceRow]) -> None:
        if not rows:
            return
        async with self._db.connect() as c:
            await c.executemany(
                "INSERT INTO devices(device_id, name, manufacturer, model, area_id, "
                "  sw_version, snapshot_id, first_seen_at, last_seen_at) "
                "VALUES(?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(device_id) DO UPDATE SET "
                "  name=excluded.name, manufacturer=excluded.manufacturer, "
                "  model=excluded.model, area_id=excluded.area_id, "
                "  sw_version=excluded.sw_version, snapshot_id=excluded.snapshot_id, "
                "  last_seen_at=excluded.last_seen_at",
                [(r.device_id, r.name, r.manufacturer, r.model, r.area_id,
                  r.sw_version, r.snapshot_id, r.first_seen_at, r.last_seen_at)
                 for r in rows],
            )
            await c.commit()

    # ---------- entities ----------
    async def upsert_entities(self, rows: list[EntityRow]) -> None:
        if not rows:
            return
        async with self._db.connect() as c:
            await c.executemany(
                "INSERT INTO entities(entity_id, friendly_name, domain, device_class, "
                "  device_id, area_id, disabled, snapshot_id, first_seen_at, "
                "  last_seen_at, event_count_24h, total_event_count) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(entity_id) DO UPDATE SET "
                "  friendly_name=excluded.friendly_name, "
                "  domain=excluded.domain, device_class=excluded.device_class, "
                "  device_id=excluded.device_id, area_id=excluded.area_id, "
                "  disabled=excluded.disabled, snapshot_id=excluded.snapshot_id, "
                "  last_seen_at=excluded.last_seen_at",
                [(r.entity_id, r.friendly_name, r.domain, r.device_class,
                  r.device_id, r.area_id, r.disabled, r.snapshot_id,
                  r.first_seen_at, r.last_seen_at,
                  r.event_count_24h, r.total_event_count) for r in rows],
            )
            await c.commit()

    async def bump_entity_event_counts(
        self, *, entity_id: str, last_seen_at: int
    ) -> None:
        async with self._db.connect() as c:
            await c.execute(
                "UPDATE entities SET "
                "  event_count_24h = event_count_24h + 1, "
                "  total_event_count = total_event_count + 1, "
                "  last_seen_at = ? "
                "WHERE entity_id = ?",
                (last_seen_at, entity_id),
            )
            await c.commit()

    async def list_entities(
        self, *, area_id: str | None = None,
        orphan: bool = False, device_class: str | None = None,
        limit: int = 1000,
    ) -> list[EntityRow]:
        clauses = []
        params: list[Any] = []
        if orphan:
            clauses.append("area_id IS NULL")
        elif area_id is not None:
            clauses.append("area_id = ?")
            params.append(area_id)
        if device_class is not None:
            clauses.append("device_class = ?")
            params.append(device_class)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        async with self._db.connect() as c:
            rows = await (await c.execute(
                "SELECT entity_id, friendly_name, domain, device_class, "  # noqa: S608
                "  device_id, area_id, disabled, snapshot_id, first_seen_at, "
                "  last_seen_at, event_count_24h, total_event_count "
                f"FROM entities{where} LIMIT ?",
                params,
            )).fetchall()
        return [EntityRow(*r) for r in rows]

    # ---------- events ----------
    async def insert_events(self, rows: list[EventRow]) -> None:
        if not rows:
            return
        async with self._db.connect() as c:
            await c.executemany(
                "INSERT INTO events(ts, received_at, entity_id, event_type, "
                "  old_state, new_state, context_user_id, context_parent_id, "
                "  area_id, device_id, device_class, snapshot_id) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                [(r.ts, r.received_at, r.entity_id, r.event_type,
                  r.old_state, r.new_state, r.context_user_id, r.context_parent_id,
                  r.area_id, r.device_id, r.device_class, r.snapshot_id)
                 for r in rows],
            )
            await c.commit()

    async def list_events(
        self, *, entity_id: str | None = None, area_id: str | None = None,
        since_ts: int | None = None, until_ts: int | None = None,
        cursor: int | None = None, limit: int = 100,
    ) -> list[EventRow]:
        clauses = []
        params: list[Any] = []
        if entity_id:
            clauses.append("entity_id = ?")
            params.append(entity_id)
        if area_id:
            clauses.append("area_id = ?")
            params.append(area_id)
        if since_ts is not None:
            clauses.append("ts >= ?")
            params.append(since_ts)
        if until_ts is not None:
            clauses.append("ts <= ?")
            params.append(until_ts)
        if cursor is not None:
            # cursor is an event_id; return rows with event_id < cursor (older page)
            clauses.append("event_id < ?")
            params.append(cursor)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        async with self._db.connect() as c:
            rows = await (await c.execute(
                "SELECT ts, received_at, entity_id, event_type, "  # noqa: S608
                "  old_state, new_state, context_user_id, context_parent_id, "
                "  area_id, device_id, device_class, snapshot_id "
                f"FROM events{where} ORDER BY event_id DESC LIMIT ?",
                params,
            )).fetchall()
        return [EventRow(*r) for r in rows]

    # ---------- counters ----------
    async def increment_counter(
        self, area_id: str, *, hour_bucket_utc: int, by: int = 1
    ) -> None:
        async with self._db.connect() as c:
            await c.execute(
                "INSERT INTO counters_per_area(area_id, hour_bucket_utc, event_count) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(area_id, hour_bucket_utc) DO UPDATE SET "
                "  event_count = event_count + excluded.event_count",
                (area_id, hour_bucket_utc, by),
            )
            await c.commit()

    async def get_counters_24h(self, *, now_hour: int) -> dict[tuple[str, int], int]:
        async with self._db.connect() as c:
            rows = await (await c.execute(
                "SELECT area_id, hour_bucket_utc, event_count "
                "FROM counters_per_area WHERE hour_bucket_utc > ?",
                (now_hour - 24,),
            )).fetchall()
        return {(r[0], r[1]): r[2] for r in rows}

    # ---------- privacy_drops ----------
    async def increment_privacy_drop(self, *, hour_bucket_utc: int, by: int = 1) -> None:
        async with self._db.connect() as c:
            await c.execute(
                "INSERT INTO privacy_drops(hour_bucket_utc, drop_count) "
                "VALUES (?, ?) "
                "ON CONFLICT(hour_bucket_utc) DO UPDATE SET "
                "  drop_count = drop_count + excluded.drop_count",
                (hour_bucket_utc, by),
            )
            await c.commit()

    async def get_privacy_drops_24h(self, *, now_hour: int) -> dict[int, int]:
        async with self._db.connect() as c:
            rows = await (await c.execute(
                "SELECT hour_bucket_utc, drop_count FROM privacy_drops "
                "WHERE hour_bucket_utc > ?",
                (now_hour - 24,),
            )).fetchall()
        return {r[0]: r[1] for r in rows}

    # ---------- kv_meta ----------
    async def get_meta(self, key: str) -> str | None:
        async with self._db.connect() as c:
            row = await (await c.execute(
                "SELECT value FROM kv_meta WHERE key=?", (key,)
            )).fetchone()
        return row[0] if row else None

    async def set_meta(self, key: str, value: str, *, ts_ms: int) -> None:
        async with self._db.connect() as c:
            await c.execute(
                "INSERT OR REPLACE INTO kv_meta(key, value, updated_at) "
                "VALUES (?, ?, ?)",
                (key, value, ts_ms),
            )
            await c.commit()
