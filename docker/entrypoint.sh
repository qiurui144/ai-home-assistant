#!/bin/sh
# ai-home-assistant entrypoint — bootstraps config on first run, then exec the
# main process. Idempotent across container restarts.
set -e

CONFIG="${AI_HA_CONFIG:-/data/config.toml}"
DEFAULT_CONFIG="/app/config/default.toml"

if [ ! -f "$CONFIG" ]; then
    echo "[ai-ha] first-run: seeding config.toml from default"
    cp "$DEFAULT_CONFIG" "$CONFIG"
fi

# Apply environment overrides for the most common knobs.
if [ -n "${HA_URL:-}" ]; then
    echo "[ai-ha] HA_URL=$HA_URL"
fi
if [ -n "${HA_TOKEN:-}" ]; then
    echo "[ai-ha] HA_TOKEN set (length ${#HA_TOKEN})"
fi

exec "$@"
