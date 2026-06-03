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

REPO_URL="${REPO_URL:-https://github.com/qiurui144/ai-home-assistant.git}"
IMAGE_AIHA="${IMAGE_AIHA:-ghcr.io/qiurui144/ai-home-assistant:0.1.5}"
IMAGE_HA="${IMAGE_HA:-ghcr.io/home-assistant/home-assistant:stable}"

fetch_repo() {
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    echo "↻ Updating $INSTALL_DIR..."
    [[ -n "$DRY_RUN" ]] || (cd "$INSTALL_DIR" && git pull --ff-only)
  else
    echo "↓ Cloning to $INSTALL_DIR..."
    [[ -n "$DRY_RUN" ]] || git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
  fi
}

pull_images() {
  echo "↓ Pulling Docker images (5-10 min on first run)..."
  echo "  - $IMAGE_HA"
  echo "  - $IMAGE_AIHA"
  if [[ -z "$DRY_RUN" ]]; then
    docker pull "$IMAGE_HA"
    docker pull "$IMAGE_AIHA"
  fi
}

start_ha() {
  echo "▶ Starting Home Assistant on port ${HA_PORT}..."
  if [[ -n "$DRY_RUN" ]]; then
    echo "  (dry-run) would compose up homeassistant + wait health on :${HA_PORT}"
    return 0
  fi
  cd "$INSTALL_DIR/docker"
  INSTALL_INCOMPLETE=1
  docker compose -f docker-compose.with-ha.yml up -d homeassistant
  echo "↻ Waiting HA to be ready (max 60s)..."
  local attempt
  for attempt in 1 2 3 4 5 6; do
    if curl -fsS --max-time 5 "http://localhost:${HA_PORT}/" >/dev/null 2>&1; then
      echo "✓ HA ready at http://localhost:${HA_PORT}"
      return 0
    fi
    sleep 10
  done
  echo "ERR: HA didn't start in 60s. Recent logs:" >&2
  docker compose -f docker-compose.with-ha.yml logs --tail=20 homeassistant >&2
  exit 70
}

validate_token() {
  local token="$1"
  if [[ ! "$token" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "ERR: token contains invalid characters (allowed: A-Za-z0-9._-)" >&2
    return 78
  fi
  local code
  code=$(curl -sS -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $token" --max-time 5 \
    "http://localhost:${HA_PORT}/api/" || echo "000")
  if [[ "$code" != "200" ]]; then
    echo "ERR: token rejected by HA (HTTP $code)" >&2
    return 78
  fi
  return 0
}

prompt_token() {
  cat <<EOF

════════════════════════════════════════════════════════════
║ NEXT STEP — Generate a Home Assistant access token
║
║ 1. Open in your browser:  http://<this-host>:${HA_PORT}
║ 2. Create your HA account (or sign in)
║ 3. Click your username (bottom-left) → "Security"
║ 4. Long-Lived Access Tokens → "Create Token"
║ 5. Name it "ai-home-assistant", copy the value
║ 6. Paste below (input hidden):
════════════════════════════════════════════════════════════
EOF

  if [[ -n "$DRY_RUN" ]]; then
    echo "  (dry-run) skipping interactive prompt"
    return 0
  fi

  local token attempt=0
  while [[ $attempt -lt 3 ]]; do
    read -rs -p "HA token: " token; echo
    token=$(echo "$token" | tr -d '[:space:]')
    if [[ -z "$token" ]]; then
      echo "ERR: empty token. Try again." >&2
      attempt=$((attempt+1)); continue
    fi
    if validate_token "$token"; then
      echo "HA_TOKEN=$token" > "$INSTALL_DIR/docker/.env"
      chmod 600 "$INSTALL_DIR/docker/.env"
      echo "✓ Token validated and saved to $INSTALL_DIR/docker/.env (0600)"
      return 0
    fi
    attempt=$((attempt+1))
  done
  echo "ERR: 3 token attempts failed. Aborting." >&2
  exit 78
}

main() {
  if [[ "${1:-}" == "--help" ]]; then usage; exit 0; fi
  if [[ "${1:-}" == "--dry-run" ]]; then DRY_RUN=1; fi
  check_prereq
  fetch_repo
  pull_images
  start_ha
  prompt_token
  if [[ -n "$DRY_RUN" ]]; then
    echo "✓ Dry run complete (all stages except actual exec)."
    exit 0
  fi
  echo "TODO: start_aiha / banner (final task)"
}

# Only run main when executed directly, not when sourced (e.g. for unit tests).
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main "$@"; fi
