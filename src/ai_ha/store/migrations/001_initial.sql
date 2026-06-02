-- kv_meta
CREATE TABLE kv_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  INTEGER NOT NULL
) WITHOUT ROWID;

-- topology_snapshots
CREATE TABLE topology_snapshots (
    snapshot_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           INTEGER NOT NULL,
    payload_hash TEXT    NOT NULL,
    payload      TEXT    NOT NULL,
    diff_summary TEXT,
    UNIQUE(payload_hash)
);
CREATE INDEX idx_topology_ts ON topology_snapshots(ts DESC);

-- areas
CREATE TABLE areas (
    area_id        TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    floor_id       TEXT,
    icon           TEXT,
    aliases        TEXT,
    snapshot_id    INTEGER NOT NULL,
    first_seen_at  INTEGER NOT NULL,
    last_seen_at   INTEGER NOT NULL
) WITHOUT ROWID;
CREATE INDEX idx_areas_floor ON areas(floor_id);
CREATE INDEX idx_areas_snapshot ON areas(snapshot_id);

-- devices
CREATE TABLE devices (
    device_id      TEXT PRIMARY KEY,
    name           TEXT,
    manufacturer   TEXT,
    model          TEXT,
    area_id        TEXT,
    sw_version     TEXT,
    snapshot_id    INTEGER NOT NULL,
    first_seen_at  INTEGER NOT NULL,
    last_seen_at   INTEGER NOT NULL
) WITHOUT ROWID;
CREATE INDEX idx_devices_area ON devices(area_id);
CREATE INDEX idx_devices_snapshot ON devices(snapshot_id);

-- entities
CREATE TABLE entities (
    entity_id          TEXT PRIMARY KEY,
    friendly_name      TEXT,
    domain             TEXT NOT NULL,
    device_class       TEXT,
    device_id          TEXT,
    area_id            TEXT,
    disabled           INTEGER NOT NULL DEFAULT 0,
    snapshot_id        INTEGER NOT NULL,
    first_seen_at      INTEGER NOT NULL,
    last_seen_at       INTEGER NOT NULL,
    event_count_24h    INTEGER NOT NULL DEFAULT 0,
    total_event_count  INTEGER NOT NULL DEFAULT 0
) WITHOUT ROWID;
CREATE INDEX idx_entities_area ON entities(area_id);
CREATE INDEX idx_entities_device ON entities(device_id);
CREATE INDEX idx_entities_class ON entities(device_class);
CREATE INDEX idx_entities_domain ON entities(domain);
CREATE INDEX idx_entities_snapshot ON entities(snapshot_id);
CREATE INDEX idx_entities_orphan ON entities(area_id) WHERE area_id IS NULL;

-- events
CREATE TABLE events (
    event_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                INTEGER NOT NULL,
    received_at       INTEGER NOT NULL,
    entity_id         TEXT NOT NULL,
    event_type        TEXT NOT NULL,
    old_state         TEXT,
    new_state         TEXT,
    context_user_id   TEXT,
    context_parent_id TEXT,
    area_id           TEXT,
    device_id         TEXT,
    device_class      TEXT,
    snapshot_id       INTEGER NOT NULL
);
CREATE INDEX idx_events_ts ON events(ts DESC);
CREATE INDEX idx_events_entity_ts ON events(entity_id, ts DESC);
CREATE INDEX idx_events_area_ts ON events(area_id, ts DESC);
CREATE INDEX idx_events_received ON events(received_at DESC);

-- counters_per_area
CREATE TABLE counters_per_area (
    area_id          TEXT NOT NULL,
    hour_bucket_utc  INTEGER NOT NULL,
    event_count      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (area_id, hour_bucket_utc)
) WITHOUT ROWID;
CREATE INDEX idx_counters_bucket ON counters_per_area(hour_bucket_utc DESC);

-- privacy_drops
CREATE TABLE privacy_drops (
    hour_bucket_utc  INTEGER PRIMARY KEY,
    drop_count       INTEGER NOT NULL
) WITHOUT ROWID;
