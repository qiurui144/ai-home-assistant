#!/usr/bin/env bash
# ai-home-assistant install.sh — interactive one-shot deploy
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/qiurui144/ai-home-assistant/main/install.sh | bash
#   bash install.sh [--help] [--dry-run]
#
# Env:
#   INSTALL_DIR      where to clone the repo (default: /opt/ai-ha)
#   HA_PORT          Home Assistant port (default: 8123)
#   AIHA_PORT        ai-home-assistant port (default: 8124)
#   AIHA_DRY_RUN=1   skip side effects (for tests)

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/ai-ha}"
HA_PORT="${HA_PORT:-8123}"
AIHA_PORT="${AIHA_PORT:-8124}"
DRY_RUN="${AIHA_DRY_RUN:-}"
INSTALL_INCOMPLETE=""

cleanup() {
  local code=$?
  if [[ $code -ne 0 && -n "${INSTALL_INCOMPLETE:-}" && -z "$DRY_RUN" ]]; then
    echo "❌ install aborted (exit $code). Cleaning up..." >&2
    docker compose -f "$INSTALL_DIR/docker/docker-compose.with-ha.yml" down 2>/dev/null || true
  fi
}
trap cleanup EXIT

usage() {
  cat <<EOF
ai-home-assistant install.sh

Interactive one-shot deploy:
  1. Prereq check (docker, compose, ports)
  2. Clone repo + pull images
  3. Start Home Assistant
  4. Guide you to create HA long-lived access token
  5. Start ai-home-assistant
  6. Print success banner with URLs

Usage:
  bash install.sh           # full install
  bash install.sh --help    # this message
  bash install.sh --dry-run # validate without side effects

Env vars: INSTALL_DIR, HA_PORT, AIHA_PORT
EOF
}

check_prereq() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "ERR: Docker not found. Install: https://docs.docker.com/engine/install/" >&2
    exit 78
  fi
  if ! docker compose version >/dev/null 2>&1; then
    echo "ERR: docker compose plugin missing. Install: https://docs.docker.com/compose/install/" >&2
    exit 78
  fi
  if ss -tln 2>/dev/null | grep -q ":${HA_PORT} "; then
    echo "ERR: port ${HA_PORT} (HA) is in use. Stop the process or set HA_PORT=..." >&2
    exit 78
  fi
  if ss -tln 2>/dev/null | grep -q ":${AIHA_PORT} "; then
    echo "ERR: port ${AIHA_PORT} (ai-ha) is in use. Stop the process or set AIHA_PORT=..." >&2
    exit 78
  fi
  echo "✓ Prereqs OK (docker ✓ compose ✓ ports ${HA_PORT}/${AIHA_PORT} free)"
}

main() {
  if [[ "${1:-}" == "--help" ]]; then usage; exit 0; fi
  if [[ "${1:-}" == "--dry-run" ]]; then DRY_RUN=1; fi
  check_prereq
  if [[ -n "$DRY_RUN" ]]; then
    echo "✓ Dry run complete. Prereq passed."
    exit 0
  fi
  echo "TODO: fetch_repo / pull_images / start_ha / prompt_token / start_aiha / banner"
  echo "(future tasks)"
}

main "$@"
