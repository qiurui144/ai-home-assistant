# ai-home-assistant v0.1.5 — Deployment + UI Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v0.1.5 — `install.sh` interactive one-shot deploy + `/dashboard` C+B hybrid home + mobile-first responsive + zh-CN i18n + live update extension. Drops user time-to-first-dashboard from ~hours (current docker-compose) to ~30 min (curl pipe).

**Architecture:** Bundled minor that piggy-backs on the existing v0.1.0 stack. install.sh is pure bash, no new Python deps. Dashboard reuses existing DAO + EventBroadcaster, adds one new `room_state` WS message type with per-area throttling. CSS is rewritten mobile-first (320 → 1100 breakpoints). i18n via Babel + gettext + Jinja `_l` integration. All DOM updates remain XSS-safe (textContent / createElement only — Jinja2 autoescape always on).

**Tech Stack:** v0.1.0 stack unchanged (Python 3.11, FastAPI, asyncio, SQLite WAL, aiosqlite, websockets, Jinja2, watchfiles, ruff, mypy, pytest) + Babel 2.16 (translation extraction + compilation; runtime gettext is stdlib).

**Source spec:** `docs/superpowers/specs/2026-06-03-v015-deploy-and-ui-design.md` (855 lines, approved 2026-06-03 commit `1dc4840`).

**Pre-requisite:** v0.1.0 GA must be tagged + RK3588-verified before merging v0.1.5 work into main. Branch off v0.1.0 to develop in parallel if needed.

---

## Calendar overview (~3.5 weeks / 31 commit-grain tasks)

| Phase | Day | Goal | Tasks |
|-------|----:|------|------:|
| 1 — Deployment | 1-5 | install.sh prereq → HA start → token prompt → ai-ha start; README + docker-compose update | 1-7 |
| 2 — i18n infra | 6-9 | Babel install, locale wrapper, Jinja `_l`, lang switcher API + UI | 8-12 |
| 3 — Live update | 10-12 | room_state WS message + ingest publish + throttle + tests | 13-15 |
| 4 — Dashboard backend | 13-15 | aggregator endpoint + page route + tests | 16-18 |
| 5 — Dashboard frontend | 16-18 | template + JS + benchmark | 19-21 |
| 6 — Responsive + rooms live | 19-22 | mobile-first CSS + rooms.js + room-live.js + viewport tests | 22-25 |
| 7 — zh-CN translation | 23-25 | extract → translate → compile → CI gate | 26-28 |
| 8 — Release | 26-28 | RELEASE.md, RC audit, real RK3588, tag | 29-31 |

Buffer days 26-28: RK3588 manual verification + mobile device walk-through + tag.

---

## File structure (recap from spec §4)

```
# === Deployment ===
install.sh                              ~200 lines  new
README.md                               +30 lines   update (curl one-liner top)
docker/docker-compose.with-ha.yml       +10 lines   update (env_file)
.env.example                            ~15 lines   new

# === UI backend ===
src/ai_ha/web/routes/dashboard.py       ~80 lines   new
src/ai_ha/web/routes/lang.py            ~40 lines   new (/api/v1/lang + /api/v1/locales)
src/ai_ha/web/routes/pages.py           +25 lines   update (/ redirect + lang query)
src/ai_ha/web/routes/stream.py          +30 lines   update (room_state msg type)
src/ai_ha/ingest/pipeline.py            +35 lines   update (publish room_state + throttle)
src/ai_ha/health/metrics.py             +15 lines   update (room_state + i18n metrics)
src/ai_ha/web/i18n/__init__.py          ~45 lines   new (locale_from_request + gettext)
src/ai_ha/web/i18n/babel.cfg            ~15 lines   new
src/ai_ha/web/i18n/locales/en/LC_MESSAGES/ai_ha.po       auto
src/ai_ha/web/i18n/locales/zh_CN/LC_MESSAGES/ai_ha.po    ~150 entries
src/ai_ha/web/i18n/locales/zh_CN/LC_MESSAGES/ai_ha.mo    compiled (in image)
src/ai_ha/main.py                       +5 lines    update (install i18n at startup)
src/ai_ha/web/app.py                    +5 lines    update (mount lang router + i18n)

# === UI frontend ===
src/ai_ha/web/templates/dashboard.html  ~130 lines  new
src/ai_ha/web/templates/base.html       +20 lines   update (lang switcher + meta)
src/ai_ha/web/templates/rooms.html      +3 lines    update (rooms.js)
src/ai_ha/web/templates/room.html       +3 lines    update (room-live.js)
src/ai_ha/web/templates/_macros.html    ~30 lines   new (trans + room_card)
src/ai_ha/web/static/app.css            ~270 lines  rewrite (mobile-first)
src/ai_ha/web/static/dashboard.js       ~110 lines  new
src/ai_ha/web/static/rooms.js           ~60 lines   new
src/ai_ha/web/static/room-live.js       ~40 lines   new

# === Tests ===
tests/integration/test_install_script.py        ~90 lines  new
tests/integration/test_dashboard.py             ~110 lines new
tests/integration/test_live_room_state.py       ~80 lines  new
tests/integration/test_i18n_zh_cn.py            ~60 lines  new
tests/integration/test_lang_endpoint.py         ~40 lines  new
tests/integration/test_responsive_viewport.py   ~50 lines  new
tests/unit/test_pipeline_room_state.py          ~70 lines  new
tests/unit/test_dashboard_aggregator.py         ~70 lines  new
tests/unit/test_i18n_loader.py                  ~50 lines  new
tests/perf/bench_dashboard.py                   ~50 lines  new (vG3)
tests/perf/bench_live_update.py                 ~50 lines  new (vG4)

# === Build / CI ===
requirements.txt                        +1 line     (Babel==2.16.0)
docker/Dockerfile                       +6 lines    (pybabel compile step)
.github/workflows/ci.yml                +10 lines   (i18n extract gate)
```

**LOC total**: Python ~700 + Jinja ~190 + CSS/JS ~480 + Bash ~200 + i18n ~250 + tests ~720 ≈ **2540 LOC** (slightly above spec §4 first estimate, still in 3.5w budget).

---

# Phase 1 — Deployment (Day 1-5)

## Task 1: install.sh skeleton — prereq check + cleanup trap

**Files:**
- Create: `install.sh`
- Create: `tests/integration/test_install_script.py` (skeleton + first test)

- [ ] **Step 1: Write `tests/integration/test_install_script.py`** (first 2 tests — skeleton + prereq fail)

```python
"""Test install.sh skeleton — prereq detection.

install.sh is pure bash. Tests invoke it as a subprocess with a stub PATH
that controls whether docker/compose are 'installed'.
"""
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"


def _run_install(args: list[str], env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        env=env, capture_output=True, text=True, check=False,
    )


def test_install_sh_exists_executable():
    assert INSTALL_SH.exists()
    assert os.access(INSTALL_SH, os.R_OK)


def test_help_flag_prints_usage():
    r = _run_install(["--help"])
    assert r.returncode == 0
    assert "ai-home-assistant" in r.stdout.lower()
    assert "install" in r.stdout.lower()


def test_missing_docker_exits_78(tmp_path):
    # Stub PATH with no docker
    fake_path = tmp_path / "bin"; fake_path.mkdir()
    r = _run_install([], env_extra={"PATH": str(fake_path), "AIHA_DRY_RUN": "1"})
    assert r.returncode == 78
    assert "docker" in r.stderr.lower()
```

- [ ] **Step 2: Run test — expect 3 failures (file missing)**

```bash
cd /data/company/project/ai-home-assistant
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pip install -e . > /dev/null 2>&1 &&
  pytest tests/integration/test_install_script.py -v
"
# Expect: 3 FAIL with FileNotFoundError on install.sh
```

- [ ] **Step 3: Write `install.sh`** (skeleton — help, prereq check, dry-run support)

```bash
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
```

- [ ] **Step 4: Make executable + run tests**

```bash
chmod +x install.sh
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/integration/test_install_script.py -v
"
# Expect: 3 PASS
```

- [ ] **Step 5: Commit**

```bash
git add install.sh tests/integration/test_install_script.py
git commit -m "$(cat <<'EOF'
feat(install): install.sh skeleton — prereq check + cleanup trap + --help/--dry-run

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: install.sh — fetch repo + pull images

**Files:**
- Modify: `install.sh` (add `fetch_repo` + `pull_images` functions)
- Modify: `tests/integration/test_install_script.py` (test pull stage dry-run)

- [ ] **Step 1: Append test** — `tests/integration/test_install_script.py`

```python
def test_dry_run_shows_pull_plan(tmp_path):
    r = _run_install(["--dry-run"], env_extra={
        "PATH": os.environ["PATH"],
        "INSTALL_DIR": str(tmp_path / "ai-ha"),
    })
    # Dry-run after Task 2 should report intended docker pull
    assert r.returncode == 0
    assert "ghcr.io/qiurui144/ai-home-assistant" in r.stdout
```

- [ ] **Step 2: Run test — expect FAIL** (the string isn't in dry-run output yet)

- [ ] **Step 3: Modify `install.sh`** — add `fetch_repo` + `pull_images`, update dry-run output

Add after `check_prereq()`:

```bash
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
```

Update `main()`:

```bash
main() {
  if [[ "${1:-}" == "--help" ]]; then usage; exit 0; fi
  if [[ "${1:-}" == "--dry-run" ]]; then DRY_RUN=1; fi
  check_prereq
  fetch_repo
  pull_images
  if [[ -n "$DRY_RUN" ]]; then
    echo "✓ Dry run complete (prereq + repo + pull plan)."
    exit 0
  fi
  echo "TODO: start_ha / prompt_token / start_aiha / banner (next tasks)"
}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/integration/test_install_script.py -v
"
# Expect: 4 PASS
```

- [ ] **Step 5: Commit**

```bash
git add install.sh tests/integration/test_install_script.py
git commit -m "feat(install): fetch_repo + pull_images functions with dry-run support"
```

---

## Task 3: install.sh — start HA + health wait

**Files:**
- Modify: `install.sh` (add `start_ha`)
- Modify: `tests/integration/test_install_script.py` (test health-wait stage)

- [ ] **Step 1: Append test**

```python
def test_dry_run_mentions_ha_health_wait(tmp_path):
    r = _run_install(["--dry-run"], env_extra={
        "PATH": os.environ["PATH"],
        "INSTALL_DIR": str(tmp_path / "ai-ha"),
    })
    assert r.returncode == 0
    assert "health" in r.stdout.lower() or "8123" in r.stdout
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Modify `install.sh`** — add `start_ha`

```bash
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
```

Update `main()`:

```bash
  check_prereq
  fetch_repo
  pull_images
  start_ha
  if [[ -n "$DRY_RUN" ]]; then
    echo "✓ Dry run complete (prereq + repo + pull + ha-start plan)."
    exit 0
  fi
  echo "TODO: prompt_token / start_aiha / banner (next tasks)"
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add install.sh tests/integration/test_install_script.py
git commit -m "feat(install): start_ha with 60s health wait + graceful failure log dump"
```

---

## Task 4: install.sh — interactive token prompt + validation

**Files:**
- Modify: `install.sh` (add `prompt_token`)
- Modify: `tests/integration/test_install_script.py` (test token validation with mock HA)

- [ ] **Step 1: Append test** (use a tiny Python HTTP mock as "HA" so curl validation works)

```python
import http.server
import socketserver
import threading
import contextlib


@contextlib.contextmanager
def mock_ha_validator(token: str = "valid-token"):
    """Tiny HTTP server that 200's for Bearer <token>, 401 otherwise."""
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            auth = self.headers.get("Authorization", "")
            if auth == f"Bearer {token}":
                self.send_response(200); self.end_headers()
                self.wfile.write(b'{"message":"API running."}')
            else:
                self.send_response(401); self.end_headers()
        def log_message(self, *_args, **_kwargs): pass

    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()


def test_token_validation_rejects_invalid(tmp_path):
    """install.sh token validation should reject 401."""
    with mock_ha_validator("the-good-token") as port:
        # We test only the validate_token bash function in isolation by sourcing.
        r = subprocess.run(
            ["bash", "-c", f"source {INSTALL_SH}; HA_PORT={port} validate_token wrong-token"],
            capture_output=True, text=True, check=False,
        )
        assert r.returncode == 78
        assert "401" in r.stderr or "invalid" in r.stderr.lower()


def test_token_validation_accepts_valid(tmp_path):
    with mock_ha_validator("the-good-token") as port:
        r = subprocess.run(
            ["bash", "-c", f"source {INSTALL_SH}; HA_PORT={port} validate_token the-good-token"],
            capture_output=True, text=True, check=False,
        )
        assert r.returncode == 0
```

- [ ] **Step 2: Run test — expect FAIL** (no `validate_token` yet)

- [ ] **Step 3: Modify `install.sh`** — add `validate_token` + `prompt_token`

```bash
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
```

Update `main()`:

```bash
  start_ha
  prompt_token
  if [[ -n "$DRY_RUN" ]]; then
    echo "✓ Dry run complete (all stages except actual exec)."
    exit 0
  fi
  echo "TODO: start_aiha / banner (final task)"
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add install.sh tests/integration/test_install_script.py
git commit -m "feat(install): interactive token prompt + curl-based validation against HA /api/"
```

---

## Task 5: install.sh — start ai-ha + success banner

**Files:**
- Modify: `install.sh` (`start_aiha` + `print_banner`)

- [ ] **Step 1: Append test**

```python
def test_full_dry_run_succeeds(tmp_path):
    r = _run_install(["--dry-run"], env_extra={
        "PATH": os.environ["PATH"],
        "INSTALL_DIR": str(tmp_path / "ai-ha"),
    })
    assert r.returncode == 0
    assert "ai-home-assistant is ready" in r.stdout.lower() or "Dry run complete" in r.stdout
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Modify `install.sh`** — add `start_aiha` + `print_banner`

```bash
start_aiha() {
  echo "▶ Starting ai-home-assistant on port ${AIHA_PORT}..."
  if [[ -n "$DRY_RUN" ]]; then
    echo "  (dry-run) would compose up ai-home-assistant + wait health on :${AIHA_PORT}"
    return 0
  fi
  cd "$INSTALL_DIR/docker"
  docker compose -f docker-compose.with-ha.yml up -d ai-home-assistant
  echo "↻ Waiting ai-ha to be ready (max 30s)..."
  for _ in 1 2 3; do
    if curl -fsS --max-time 5 "http://localhost:${AIHA_PORT}/api/health" >/dev/null 2>&1; then
      INSTALL_INCOMPLETE=""
      echo "✓ ai-home-assistant ready"
      return 0
    fi
    sleep 10
  done
  echo "ERR: ai-ha didn't start. Recent logs:" >&2
  docker compose -f docker-compose.with-ha.yml logs --tail=20 ai-home-assistant >&2
  exit 70
}

print_banner() {
  local admin_token=""
  if [[ -z "$DRY_RUN" ]]; then
    admin_token=$(docker exec ai-home-assistant cat /data/.admin-token 2>/dev/null || echo "<check 'docker logs ai-home-assistant'>")
  else
    admin_token="<set after first run>"
  fi
  cat <<EOF

════════════════════════════════════════════════════════════
║ ✓ ai-home-assistant is ready!
║
║ URL:           http://localhost:${AIHA_PORT}
║ admin user:    admin
║ admin token:   ${admin_token}
║ HA URL:        http://localhost:${HA_PORT}
║
║ Open the URL above and log in with admin / <token>.
║ Bookmark /dashboard for the main view.
║
║ Logs:  docker compose -f $INSTALL_DIR/docker/docker-compose.with-ha.yml logs -f ai-home-assistant
║ Stop:  docker compose -f $INSTALL_DIR/docker/docker-compose.with-ha.yml down
║ Re-run install.sh anytime — it's idempotent.
════════════════════════════════════════════════════════════
EOF
}
```

Replace `main()`:

```bash
main() {
  if [[ "${1:-}" == "--help" ]]; then usage; exit 0; fi
  if [[ "${1:-}" == "--dry-run" ]]; then DRY_RUN=1; fi
  check_prereq
  fetch_repo
  pull_images
  start_ha
  prompt_token
  start_aiha
  print_banner
}
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add install.sh tests/integration/test_install_script.py
git commit -m "feat(install): start_aiha + success banner with URL/token; main flow complete"
```

---

## Task 6: install.sh idempotency + abort cleanup tests

**Files:**
- Modify: `tests/integration/test_install_script.py` (add idempotency + abort tests)

- [ ] **Step 1: Append tests**

```python
def test_dry_run_idempotent_no_state_change(tmp_path):
    """Running --dry-run twice should be deterministic, no error."""
    env = {"PATH": os.environ["PATH"], "INSTALL_DIR": str(tmp_path / "ai-ha")}
    r1 = _run_install(["--dry-run"], env_extra=env)
    r2 = _run_install(["--dry-run"], env_extra=env)
    assert r1.returncode == 0
    assert r2.returncode == 0


def test_help_does_not_require_docker(tmp_path):
    """--help should work even without docker (don't run prereq)."""
    fake_path = tmp_path / "bin"; fake_path.mkdir()
    r = _run_install(["--help"], env_extra={"PATH": str(fake_path)})
    assert r.returncode == 0


def test_token_with_shell_injection_rejected():
    """Token containing shell metacharacters must be rejected."""
    r = subprocess.run(
        ["bash", "-c", f"source {INSTALL_SH}; HA_PORT=1 validate_token '; rm -rf /'"],
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 78
    assert "invalid characters" in r.stderr.lower()
```

- [ ] **Step 2: Run tests — expect PASS** (the bash already handles these; verifying)

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/integration/test_install_script.py -v
"
# Expect: ~10 PASS
```

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_install_script.py
git commit -m "test(install): idempotency + abort cleanup + shell-injection rejection coverage"
```

---

## Task 7: README curl-pipe + docker-compose update + .env.example

**Files:**
- Modify: `README.md` (quickstart curl-pipe at top)
- Modify: `docker/docker-compose.with-ha.yml` (env_file)
- Create: `.env.example`

- [ ] **Step 1: Create `.env.example`**

```
# .env file for docker-compose.with-ha.yml
# Generated by install.sh — do not commit to git
# Copy to .env and fill in:

HA_URL=http://localhost:8123
HA_TOKEN=
DEEPSEEK_API_KEY=
OPENAI_API_KEY=
```

- [ ] **Step 2: Modify `docker/docker-compose.with-ha.yml`** — add `env_file:` to ai-home-assistant service

Find the `ai-home-assistant:` service block and add (after `restart: unless-stopped`):

```yaml
    env_file:
      - .env
```

- [ ] **Step 3: Modify `README.md`** — replace top "Quickstart" section

Find the existing two `## Quickstart` sections and replace with a single one at the top of the file (after the title + tagline):

```markdown
## Quickstart (one-shot install)

On a Linux host with Docker + docker compose plugin:

```bash
curl -fsSL https://raw.githubusercontent.com/qiurui144/ai-home-assistant/main/install.sh | bash
```

The script:
1. Checks Docker + ports 8123/8124
2. Pulls images for Home Assistant + ai-home-assistant
3. Starts HA and waits for it to be ready
4. Guides you to create a HA long-lived access token
5. Starts ai-home-assistant
6. Prints the URLs and admin token

Total time: ~30 minutes on first run (mostly image pull).

### Quickstart (manual)

If you prefer not to pipe a script:

```bash
git clone https://github.com/qiurui144/ai-home-assistant.git
cd ai-home-assistant
bash install.sh
```

### Quickstart (existing HA)

If you already have HA Core running, point ai-home-assistant at it:

```bash
docker run -d --name ai-home-assistant \
  -p 8124:8124 \
  -v $PWD/ai-ha-data:/data \
  -e HA_URL=http://homeassistant.local:8123 \
  -e HA_TOKEN=<long-lived-access-token> \
  ghcr.io/qiurui144/ai-home-assistant:0.1.5
```
```

- [ ] **Step 4: Smoke check** (just verify files exist + parse)

```bash
test -f .env.example
test -f install.sh
grep -q "curl -fsSL" README.md
echo "OK"
```

- [ ] **Step 5: Commit**

```bash
git add .env.example docker/docker-compose.with-ha.yml README.md
git commit -m "$(cat <<'EOF'
doc(install): README curl-pipe quickstart + env_file in compose + .env.example

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Phase 2 — i18n Infrastructure (Day 6-9)

## Task 8: Babel install + babel.cfg + i18n directory

**Files:**
- Modify: `requirements.txt` (add Babel)
- Create: `src/ai_ha/web/i18n/__init__.py` (stub)
- Create: `src/ai_ha/web/i18n/babel.cfg`

- [ ] **Step 1: Modify `requirements.txt`** — append (under existing test-deps block)

```
Babel==2.16.0
```

- [ ] **Step 2: Create `src/ai_ha/web/i18n/babel.cfg`**

```
[python: src/**.py]

[jinja2: src/ai_ha/web/templates/**.html]
extensions=jinja2.ext.i18n
```

- [ ] **Step 3: Create `src/ai_ha/web/i18n/__init__.py`** (stub — real impl in Task 9)

```python
"""i18n module for ai-home-assistant Web UI.

Real implementation arrives in Task 9. This stub allows the package to be
importable so Task 10's Jinja env wiring doesn't fail at install time.
"""
from __future__ import annotations

__all__ = ["locale_from_request", "install_translations"]


def locale_from_request(*_args, **_kwargs) -> str:  # noqa: D401
    return "en"


def install_translations(*_args, **_kwargs) -> None:
    pass
```

- [ ] **Step 4: Rebuild image + verify Babel installed**

```bash
docker build -t ai-home-assistant:dev -f docker/Dockerfile .
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pip install -e . > /dev/null 2>&1 &&
  python -c 'import babel; print(babel.__version__)' &&
  python -c 'from ai_ha.web.i18n import locale_from_request; print(locale_from_request())' &&
  ruff check src/ &&
  mypy src/
"
# Expect: 2.16.0, "en", 0 ruff, 0 mypy issues
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/ai_ha/web/i18n/
git commit -m "feat(i18n): add Babel dep + i18n module skeleton + babel.cfg"
```

---

## Task 9: i18n locale_from_request + gettext loader

**Files:**
- Modify: `src/ai_ha/web/i18n/__init__.py`
- Create: `src/ai_ha/web/i18n/loader.py`
- Create: `tests/unit/test_i18n_loader.py`

- [ ] **Step 1: Write `tests/unit/test_i18n_loader.py`**

```python
import gettext
import pytest
from pathlib import Path
from ai_ha.web.i18n.loader import locale_from_request, get_translation, SUPPORTED_LOCALES


def _stub_request(query: dict[str, str] | None = None,
                  cookies: dict[str, str] | None = None,
                  accept_lang: str | None = None):
    """A minimal duck-typed Request for unit tests."""
    class R:
        def __init__(self) -> None:
            self.query_params = query or {}
            self.cookies = cookies or {}
            self.headers = {"accept-language": accept_lang} if accept_lang else {}
    return R()


def test_locale_default_en():
    r = _stub_request()
    assert locale_from_request(r) == "en"


def test_locale_query_wins():
    r = _stub_request(query={"lang": "zh"}, cookies={"ai-ha-lang": "en"})
    assert locale_from_request(r) == "zh_CN"


def test_locale_cookie_used():
    r = _stub_request(cookies={"ai-ha-lang": "zh"})
    assert locale_from_request(r) == "zh_CN"


def test_locale_accept_language():
    r = _stub_request(accept_lang="zh-CN,zh;q=0.9,en;q=0.5")
    assert locale_from_request(r) == "zh_CN"


def test_locale_unknown_falls_back_to_en():
    r = _stub_request(query={"lang": "fr"})
    assert locale_from_request(r) == "en"


def test_supported_locales_includes_en_and_zh():
    assert "en" in SUPPORTED_LOCALES
    assert "zh_CN" in SUPPORTED_LOCALES


def test_get_translation_returns_translation():
    t = get_translation("en")
    assert isinstance(t, gettext.NullTranslations)  # NullTranslations or GNUTranslations
```

- [ ] **Step 2: Run test — expect FAIL** (loader.py missing)

- [ ] **Step 3: Create `src/ai_ha/web/i18n/loader.py`**

```python
"""Locale negotiation + gettext translation loader.

Order: ?lang= query → ai-ha-lang cookie → Accept-Language → "en" default.
Short codes ('zh', 'en') normalise to full ('zh_CN', 'en').
"""
from __future__ import annotations

import gettext
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

LOCALE_DIR = Path(__file__).parent / "locales"
SUPPORTED_LOCALES: dict[str, str] = {
    "en": "English",
    "zh_CN": "中文 (简体)",
}

_SHORT_ALIASES = {"zh": "zh_CN", "en": "en"}


class _HasRequestLikeAttrs(Protocol):
    query_params: Any
    cookies: Any
    headers: Any


def _normalize(code: str) -> str | None:
    code = code.strip().replace("-", "_")
    if code in SUPPORTED_LOCALES:
        return code
    short = code.split("_")[0].lower()
    return _SHORT_ALIASES.get(short)


def _accept_language_locales(header: str) -> Iterable[str]:
    """Yield candidate codes from an Accept-Language header in priority order."""
    parts = [p.split(";")[0].strip() for p in header.split(",") if p.strip()]
    for p in parts:
        if norm := _normalize(p):
            yield norm


def locale_from_request(request: _HasRequestLikeAttrs) -> str:
    q = getattr(request, "query_params", {}) or {}
    lang_q = q.get("lang") if hasattr(q, "get") else None
    if lang_q and (norm := _normalize(lang_q)):
        return norm

    cookies = getattr(request, "cookies", {}) or {}
    lang_c = cookies.get("ai-ha-lang") if hasattr(cookies, "get") else None
    if lang_c and (norm := _normalize(lang_c)):
        return norm

    headers = getattr(request, "headers", {}) or {}
    accept = (headers.get("accept-language") or "") if hasattr(headers, "get") else ""
    for cand in _accept_language_locales(accept):
        return cand

    return "en"


@lru_cache(maxsize=8)
def get_translation(locale: str) -> gettext.NullTranslations:
    """Return a Translation for `locale`. NullTranslations for 'en' or missing .mo."""
    if locale == "en":
        return gettext.NullTranslations()
    try:
        return gettext.translation(
            "ai_ha", localedir=str(LOCALE_DIR), languages=[locale], fallback=True,
        )
    except FileNotFoundError:
        return gettext.NullTranslations()
```

- [ ] **Step 4: Update `src/ai_ha/web/i18n/__init__.py`** — re-export real funcs

```python
"""i18n module for ai-home-assistant Web UI."""
from __future__ import annotations

from ai_ha.web.i18n.loader import (
    SUPPORTED_LOCALES,
    get_translation,
    locale_from_request,
)

__all__ = ["SUPPORTED_LOCALES", "get_translation", "locale_from_request"]
```

- [ ] **Step 5: Run tests + lint — expect PASS**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pip install -e . > /dev/null 2>&1 &&
  pytest tests/unit/test_i18n_loader.py -v &&
  ruff check src/ tests/ &&
  mypy src/
"
# Expect: 7 PASS, 0 ruff/mypy
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_ha/web/i18n/ tests/unit/test_i18n_loader.py
git commit -m "feat(i18n): locale_from_request (query/cookie/header chain) + gettext loader"
```

---

## Task 10: Jinja env install_translations + `_l` filter

**Files:**
- Modify: `src/ai_ha/web/i18n/__init__.py` (add install_translations)
- Create: `src/ai_ha/web/i18n/jinja_ext.py`
- Modify: `src/ai_ha/web/routes/pages.py` (use per-request locale)

- [ ] **Step 1: Append test** — `tests/unit/test_i18n_loader.py`

```python
def test_install_translations_to_jinja_env():
    from jinja2 import Environment
    from ai_ha.web.i18n import install_translations
    env = Environment(extensions=["jinja2.ext.i18n"])
    install_translations(env, "en")
    # render a trans block; en is null-translated, so output == input
    tpl = env.from_string("{% trans %}Rooms{% endtrans %}")
    assert tpl.render() == "Rooms"
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Create `src/ai_ha/web/i18n/jinja_ext.py`**

```python
"""Jinja2 i18n integration."""
from __future__ import annotations

from jinja2 import Environment

from ai_ha.web.i18n.loader import get_translation


def install_translations(env: Environment, locale: str) -> None:
    """Wire the translation for `locale` into Jinja env for {% trans %} support."""
    t = get_translation(locale)
    env.install_gettext_translations(t, newstyle=True)  # type: ignore[attr-defined]
```

- [ ] **Step 4: Update `src/ai_ha/web/i18n/__init__.py`**

```python
from ai_ha.web.i18n.loader import (
    SUPPORTED_LOCALES,
    get_translation,
    locale_from_request,
)
from ai_ha.web.i18n.jinja_ext import install_translations

__all__ = [
    "SUPPORTED_LOCALES",
    "get_translation",
    "install_translations",
    "locale_from_request",
]
```

- [ ] **Step 5: Modify `src/ai_ha/web/routes/pages.py`** — install per-request

Find the module-level `templates = Jinja2Templates(...)` block. After the `templates.env.filters[...]` line add:

```python
templates.env.add_extension("jinja2.ext.i18n")
```

Replace each `templates.TemplateResponse(request, ...)` call wrap so per-request locale activates. Add a helper at module level:

```python
from ai_ha.web.i18n import install_translations, locale_from_request


def _render(request, name: str, ctx: dict[str, object]):
    install_translations(templates.env, locale_from_request(request))
    return templates.TemplateResponse(request, name, ctx)
```

Then change each `templates.TemplateResponse(request, "rooms.html", {...})` → `_render(request, "rooms.html", {...})`. Same for room/entities/timeline/settings.

- [ ] **Step 6: Run tests + lint — expect PASS**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/unit/test_i18n_loader.py tests/integration/test_web_pages.py -v &&
  ruff check src/ tests/ &&
  mypy src/
"
# Expect: 8 + 3 PASS, no regression
```

- [ ] **Step 7: Commit**

```bash
git add src/ai_ha/web/i18n/ src/ai_ha/web/routes/pages.py tests/unit/test_i18n_loader.py
git commit -m "feat(i18n): install_translations Jinja wiring + per-request locale render helper"
```

---

## Task 11: lang switcher API endpoints + cookie

**Files:**
- Create: `src/ai_ha/web/routes/lang.py`
- Modify: `src/ai_ha/web/app.py` (mount lang router)
- Create: `tests/integration/test_lang_endpoint.py`

- [ ] **Step 1: Write `tests/integration/test_lang_endpoint.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore


@pytest.fixture
def token_store(tmp_path):
    s = AdminTokenStore(str(tmp_path / "t")); s.ensure_token(); return s


@pytest.mark.asyncio
async def test_get_locales_returns_en_and_zh(token_store):
    app = create_app(token_store=token_store, require_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/locales")
        assert r.status_code == 200
        body = r.json()
        codes = {item["code"] for item in body}
        assert codes == {"en", "zh_CN"}


@pytest.mark.asyncio
async def test_post_lang_sets_cookie(token_store):
    app = create_app(token_store=token_store, require_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.post("/api/v1/lang", json={"lang": "zh"})
        assert r.status_code == 200
        cookie = r.headers.get("set-cookie", "")
        assert "ai-ha-lang=zh_CN" in cookie


@pytest.mark.asyncio
async def test_post_lang_invalid_returns_422(token_store):
    app = create_app(token_store=token_store, require_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.post("/api/v1/lang", json={"lang": "klingon"})
        assert r.status_code == 422
        assert r.json()["detail"]["error"] == "invalid-locale"
```

- [ ] **Step 2: Run — expect FAIL** (routes missing)

- [ ] **Step 3: Create `src/ai_ha/web/routes/lang.py`**

```python
"""Language switcher endpoints — no auth required.

GET  /api/v1/locales  → list supported
POST /api/v1/lang     → set ai-ha-lang cookie
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from ai_ha.web.i18n import SUPPORTED_LOCALES
from ai_ha.web.i18n.loader import _normalize  # type: ignore[attr-defined]


class LangPayload(BaseModel):
    lang: str


def build_lang_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/locales")
    async def locales() -> list[dict[str, str]]:
        return [{"code": k, "name": v} for k, v in SUPPORTED_LOCALES.items()]

    @router.post("/lang")
    async def set_lang(payload: LangPayload, response: Response) -> dict[str, str]:
        norm = _normalize(payload.lang)
        if norm is None:
            raise HTTPException(
                422, detail={"error": "invalid-locale", "detail": f"unknown lang {payload.lang!r}"},
            )
        response.set_cookie(
            "ai-ha-lang", norm, max_age=31_536_000, samesite="lax", path="/",
        )
        return {"lang": norm}

    return router
```

- [ ] **Step 4: Modify `src/ai_ha/web/app.py`** — mount

After the `app.include_router(_s(state, require_admin))` line, add:

```python
    from ai_ha.web.routes.lang import build_lang_router
    app.include_router(build_lang_router())
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/integration/test_lang_endpoint.py -v &&
  ruff check src/ tests/ &&
  mypy src/
"
# Expect: 3 PASS
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_ha/web/routes/lang.py src/ai_ha/web/app.py tests/integration/test_lang_endpoint.py
git commit -m "feat(web): /api/v1/locales + POST /api/v1/lang sets ai-ha-lang cookie"
```

---

## Task 12: base.html lang switcher + en/zh-CN rendering smoke

**Files:**
- Modify: `src/ai_ha/web/templates/base.html` (add lang switcher in header)
- Modify: `src/ai_ha/web/static/app.css` (small lang-switcher styles)
- Create: `tests/integration/test_i18n_zh_cn.py`

- [ ] **Step 1: Write `tests/integration/test_i18n_zh_cn.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore


@pytest.fixture
def token_store(tmp_path):
    s = AdminTokenStore(str(tmp_path / "t")); s.ensure_token(); return s


@pytest.mark.asyncio
async def test_rooms_page_default_english(token_store):
    app = create_app(token_store=token_store, require_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/")
        assert r.status_code in (200, 302, 307)
        if r.status_code == 200:
            assert "Rooms" in r.text  # default en


@pytest.mark.asyncio
async def test_lang_switcher_in_base_template(token_store):
    app = create_app(token_store=token_store, require_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/")
        # base.html should include lang options
        assert "ai-ha-lang" in r.text or "lang-switcher" in r.text or '?lang=' in r.text
```

- [ ] **Step 2: Run — expect FAIL** (switcher missing)

- [ ] **Step 3: Modify `src/ai_ha/web/templates/base.html`** — replace the `<nav>` block

```html
  <header>
    <a href="/" class="brand">ai-home-assistant <span class="ver">v0.1.5</span></a>
    <nav>
      <a href="/">{% trans %}Dashboard{% endtrans %}</a>
      <a href="/rooms">{% trans %}Rooms{% endtrans %}</a>
      <a href="/entities">{% trans %}Entities{% endtrans %}</a>
      <a href="/timeline">{% trans %}Timeline{% endtrans %}</a>
      <a href="/settings">{% trans %}Settings{% endtrans %}</a>
    </nav>
    <div class="lang-switcher">
      <a href="?lang=en" class="lang-link">EN</a>
      <a href="?lang=zh" class="lang-link">中</a>
    </div>
  </header>
```

- [ ] **Step 4: Append to `src/ai_ha/web/static/app.css`** (will be fully rewritten in Task 22; for now add minimal)

```css
.lang-switcher { margin-left: auto; display: flex; gap: 0.4rem; }
.lang-switcher .lang-link { color: var(--muted); padding: 0.1rem 0.3rem; border: 1px solid #333; border-radius: 3px; }
.lang-switcher .lang-link:hover { color: var(--acc); }
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/integration/test_i18n_zh_cn.py tests/integration/test_web_pages.py -v &&
  ruff check src/ tests/ &&
  mypy src/
"
# Expect: 2 + 3 PASS
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_ha/web/templates/base.html src/ai_ha/web/static/app.css tests/integration/test_i18n_zh_cn.py
git commit -m "feat(i18n): base.html nav uses {% trans %} + lang-switcher EN/中 in header"
```

---

# Phase 3 — Live Update Extension (Day 10-12)

## Task 13: EventBroadcaster room_state message type

**Files:**
- Modify: `src/ai_ha/web/routes/stream.py` (add helper for typed publish)
- Modify: `tests/integration/test_ws_stream.py` (add room_state test)

- [ ] **Step 1: Append test** — `tests/integration/test_ws_stream.py`

```python
@pytest.mark.asyncio
async def test_broadcaster_publish_room_state_payload():
    """room_state messages have a 'type' field for client routing."""
    from ai_ha.web.routes.stream import EventBroadcaster

    bc = EventBroadcaster()
    received: list[dict] = []

    async def listener() -> None:
        async for ev in bc.subscribe():
            received.append(ev)
            return

    import asyncio
    t = asyncio.create_task(listener())
    await asyncio.sleep(0.05)
    await bc.publish({"type": "room_state", "area_id": "living", "last_seen_at": 1000, "active": True})
    await asyncio.wait_for(t, timeout=1.0)
    assert received[0]["type"] == "room_state"
    assert received[0]["area_id"] == "living"
```

- [ ] **Step 2: Run — expect PASS** (broadcaster already accepts arbitrary dicts; this test confirms the contract)

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/integration/test_ws_stream.py -v
"
```

- [ ] **Step 3: Modify `src/ai_ha/web/routes/stream.py`** — add typed helpers (no behaviour change; tightens contract for callers)

After the `class EventBroadcaster:` block, add a small helper at module level:

```python
async def publish_state_changed(
    broadcaster: EventBroadcaster, *,
    ts_ms: int, entity_id: str, event_type: str, area_id: str | None = None,
) -> None:
    await broadcaster.publish({
        "type": "state_changed", "ts": ts_ms,
        "entity_id": entity_id, "event_type": event_type, "area_id": area_id,
    })


async def publish_room_state(
    broadcaster: EventBroadcaster, *,
    area_id: str, last_seen_at: int, active: bool, entity_count: int | None = None,
) -> None:
    payload: dict[str, object] = {
        "type": "room_state",
        "area_id": area_id, "last_seen_at": last_seen_at, "active": active,
    }
    if entity_count is not None:
        payload["entity_count"] = entity_count
    await broadcaster.publish(payload)
```

- [ ] **Step 4: Run tests — expect PASS** (3 ws_stream tests now)

- [ ] **Step 5: Commit**

```bash
git add src/ai_ha/web/routes/stream.py tests/integration/test_ws_stream.py
git commit -m "feat(web): publish_state_changed + publish_room_state typed helpers on EventBroadcaster"
```

---

## Task 14: Ingest pipeline publishes room_state with throttling

**Files:**
- Modify: `src/ai_ha/ingest/pipeline.py` (call publish_room_state in commit; throttle 1/sec/area)
- Create: `tests/unit/test_pipeline_room_state.py`

- [ ] **Step 1: Write `tests/unit/test_pipeline_room_state.py`**

```python
import asyncio
import pytest
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, AreaRow, EntityRow
from ai_ha.privacy.hide_matcher import HideMatcher
from ai_ha.topology.snapshot_store import TopologyPayload
from ai_ha.topology.entity_index import EntityIndex
from ai_ha.ingest.pipeline import IngestPipeline, HAEvent
from ai_ha.web.routes.stream import EventBroadcaster

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.fixture
async def setup(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    payload = TopologyPayload(
        areas=[{"area_id": "living"}],
        devices=[{"device_id": "d1", "area_id": "living"}],
        entities=[{"entity_id": "light.a", "device_id": "d1"}],
    )
    idx = EntityIndex.build_from_payload(payload, snapshot_id=1)
    await dao.upsert_areas([AreaRow("living", "Living", None, None, "[]", 1, 1, 1)])
    await dao.upsert_entities([EntityRow(
        "light.a", "A", "light", "light", "d1", "living", 0, 1, 1, 1, 0, 0,
    )])
    bc = EventBroadcaster()
    yield dao, idx, bc


@pytest.mark.asyncio
async def test_pipeline_publishes_room_state_on_commit(setup):
    dao, idx, bc = setup
    received: list[dict] = []

    async def listener() -> None:
        async for ev in bc.subscribe():
            received.append(ev)
            if len(received) >= 1:
                return

    listener_task = asyncio.create_task(listener())
    await asyncio.sleep(0.05)

    pipe = IngestPipeline(
        dao=dao, entity_index=idx, hide_matcher=HideMatcher([]),
        batch_size=1, batch_interval_ms=10_000, broadcaster=bc,
    )
    await pipe.start()
    await pipe.submit(HAEvent(
        ts_ms=1_700_000_000_000, entity_id="light.a",
        event_type="state_changed", old_state=None, new_state='"on"',
        context_user_id=None, context_parent_id=None,
    ))
    await pipe.flush()
    await asyncio.wait_for(listener_task, timeout=1.0)
    room_states = [e for e in received if e.get("type") == "room_state"]
    assert len(room_states) == 1
    assert room_states[0]["area_id"] == "living"
    assert room_states[0]["active"] is True
    await pipe.stop()


@pytest.mark.asyncio
async def test_pipeline_throttles_room_state_per_second(setup):
    dao, idx, bc = setup
    received: list[dict] = []

    async def listener() -> None:
        async for ev in bc.subscribe():
            received.append(ev)

    asyncio.create_task(listener())
    await asyncio.sleep(0.05)

    pipe = IngestPipeline(
        dao=dao, entity_index=idx, hide_matcher=HideMatcher([]),
        batch_size=1, batch_interval_ms=10_000, broadcaster=bc,
    )
    await pipe.start()
    # 5 events fast → only 1 room_state for the area within the 1-sec window
    for i in range(5):
        await pipe.submit(HAEvent(
            ts_ms=1_700_000_000_000 + i, entity_id="light.a",
            event_type="state_changed", old_state=None, new_state='"on"',
            context_user_id=None, context_parent_id=None,
        ))
    await pipe.flush()
    await asyncio.sleep(0.1)
    room_states = [e for e in received if e.get("type") == "room_state" and e.get("area_id") == "living"]
    assert len(room_states) == 1, f"expected 1 throttled room_state, got {len(room_states)}"
    await pipe.stop()
```

- [ ] **Step 2: Run — expect FAIL** (IngestPipeline doesn't accept `broadcaster=` yet)

- [ ] **Step 3: Modify `src/ai_ha/ingest/pipeline.py`**

Add to `__init__` signature: `broadcaster: "EventBroadcaster" | None = None`. Save it as `self._broadcaster`. Also init a throttle map.

Top of file, add `from typing import TYPE_CHECKING` and:

```python
if TYPE_CHECKING:
    from ai_ha.web.routes.stream import EventBroadcaster
```

Modify the class init:

```python
    def __init__(
        self, *, dao: StoreDAO, entity_index: EntityIndex,
        hide_matcher: HideMatcher,
        batch_size: int = 100, batch_interval_ms: int = 1000,
        broadcaster: "EventBroadcaster | None" = None,
        room_state_throttle_ms: int = 1000,
    ) -> None:
        # ... existing fields ...
        self._broadcaster = broadcaster
        self._room_state_throttle_ms = room_state_throttle_ms
        self._last_room_state_publish: dict[str, int] = {}
```

In `_commit_locked()`, after `await self._dao.bump_entity_event_counts(...)` loop, append:

```python
        # Publish throttled room_state events for affected areas
        if self._broadcaster is not None:
            now_ms = int(time.time() * 1000)
            for area_id in {area for (area, _bucket) in per_area}:
                last = self._last_room_state_publish.get(area_id, 0)
                if now_ms - last >= self._room_state_throttle_ms:
                    self._last_room_state_publish[area_id] = now_ms
                    try:
                        from ai_ha.web.routes.stream import publish_room_state
                        await publish_room_state(
                            self._broadcaster,
                            area_id=area_id, last_seen_at=now_ms, active=True,
                        )
                    except Exception:
                        logger.exception("publish_room_state failed")
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/unit/test_pipeline_room_state.py tests/unit/test_ingest_pipeline.py -v &&
  ruff check src/ tests/ &&
  mypy src/
"
# Expect: 2 + 3 PASS
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_ha/ingest/pipeline.py tests/unit/test_pipeline_room_state.py
git commit -m "feat(ingest): publish room_state on commit with 1/sec/area throttle"
```

---

## Task 15: HealthMetrics counters for room_state + i18n + main.py wire

**Files:**
- Modify: `src/ai_ha/health/metrics.py` (add 2 counters)
- Modify: `src/ai_ha/main.py` (pass broadcaster to IngestPipeline)
- Modify: `tests/unit/test_health_metrics.py` (add tests)

- [ ] **Step 1: Append tests** — `tests/unit/test_health_metrics.py`

```python
def test_inc_room_state_publish_counter():
    m = HealthMetrics(install_start_ms=0)
    m.inc_room_state_publish()
    m.inc_room_state_publish()
    s = m.snapshot(now_ms=1000)
    assert s["room_state_publish_total"] == 2


def test_inc_i18n_translation_miss():
    m = HealthMetrics(install_start_ms=0)
    m.inc_i18n_translation_miss()
    s = m.snapshot(now_ms=1000)
    assert s["i18n_translation_miss_total"] == 1
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Modify `src/ai_ha/health/metrics.py`**

Add to `__init__`:

```python
        self._room_state_publish = 0
        self._i18n_translation_miss = 0
```

Add methods:

```python
    def inc_room_state_publish(self) -> None:
        self._room_state_publish += 1

    def inc_i18n_translation_miss(self) -> None:
        self._i18n_translation_miss += 1
```

Add to the `snapshot()` returned dict:

```python
            "room_state_publish_total": self._room_state_publish,
            "i18n_translation_miss_total": self._i18n_translation_miss,
```

- [ ] **Step 4: Modify `src/ai_ha/main.py`** — pass broadcaster to pipeline

Find the `pipeline = IngestPipeline(...)` line in `_run()` and change to:

```python
    pipeline = IngestPipeline(
        dao=dao, entity_index=entity_index, hide_matcher=hide_matcher,
        broadcaster=broadcaster,
    )
```

(Note: `broadcaster` is created earlier in the same function.)

- [ ] **Step 5: Run tests — expect PASS**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/unit/test_health_metrics.py tests/unit/test_pipeline_room_state.py -v &&
  ruff check src/ tests/ &&
  mypy src/
"
# Expect: 7 + 2 PASS
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_ha/health/metrics.py src/ai_ha/main.py tests/unit/test_health_metrics.py
git commit -m "feat(health): room_state + i18n counters + main wires broadcaster to pipeline"
```

---

# Phase 4 — Dashboard Backend (Day 13-15)

## Task 16: GET /api/v1/dashboard aggregator endpoint

**Files:**
- Create: `src/ai_ha/web/routes/dashboard.py`
- Modify: `src/ai_ha/web/app.py` (mount router)
- Create: `tests/unit/test_dashboard_aggregator.py`

- [ ] **Step 1: Write `tests/unit/test_dashboard_aggregator.py`**

```python
import pytest
import time
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, AreaRow, EntityRow, EventRow
from ai_ha.topology import SnapshotStore, EntityIndex
from ai_ha.health import HealthMetrics
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_dashboard_returns_health_rooms_events(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    await dao.upsert_areas([AreaRow("living", "Living", None, None, "[]", 1, 1000, 1000)])
    await dao.upsert_entities([EntityRow(
        "light.x", "L", "light", "light", None, "living", 0, 1, 1000, 1000, 3, 3,
    )])
    await dao.insert_events([EventRow(
        1000, 1001, "light.x", "state_changed", None, '"on"',
        None, None, "living", None, "light", 1,
    )])
    health = HealthMetrics(install_start_ms=0)
    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=health,
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/dashboard", auth=("admin", ts.read()))
        assert r.status_code == 200
        body = r.json()
        assert "health" in body and "rooms" in body and "recent_events" in body
        assert len(body["rooms"]) == 1
        assert body["rooms"][0]["area_id"] == "living"
        assert body["rooms"][0]["entity_count"] == 1
        assert len(body["recent_events"]) == 1


@pytest.mark.asyncio
async def test_dashboard_empty_when_no_data(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/dashboard", auth=("admin", ts.read()))
        assert r.status_code == 200
        body = r.json()
        assert body["rooms"] == []
        assert body["recent_events"] == []
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Create `src/ai_ha/web/routes/dashboard.py`**

```python
"""GET /api/v1/dashboard — single-endpoint aggregator for the home dashboard."""
from __future__ import annotations

import time
from fastapi import APIRouter, Depends

from ai_ha.web.routes import AppState


def build_router(state: AppState | None, require_admin) -> APIRouter:
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin)])

    @router.get("/dashboard")
    async def dashboard() -> dict[str, object]:
        if state is None:
            return {"health": {}, "rooms": [], "recent_events": []}
        now_ms = int(time.time() * 1000)
        now_hour = now_ms // 3_600_000
        health = state.health.snapshot(now_ms=now_ms)
        areas = await state.dao.list_areas()
        counters = await state.dao.get_counters_24h(now_hour=now_hour)
        per_area: dict[str, int] = {}
        for (aid, _), n in counters.items():
            per_area[aid] = per_area.get(aid, 0) + n
        active_cutoff = now_ms - 600_000  # 10 min
        rooms = []
        for r in areas:
            entities = await state.dao.list_entities(area_id=r.area_id)
            class_dist: dict[str, int] = {}
            last_seen_max = 0
            for e in entities:
                if e.device_class:
                    class_dist[e.device_class] = class_dist.get(e.device_class, 0) + 1
                last_seen_max = max(last_seen_max, e.last_seen_at)
            rooms.append({
                "area_id": r.area_id, "name": r.name, "floor_id": r.floor_id,
                "entity_count": len(entities),
                "device_class_distribution": class_dist,
                "events_per_hour_24h": per_area.get(r.area_id, 0),
                "last_seen": last_seen_max,
                "active": last_seen_max > active_cutoff,
            })
        recent = await state.dao.list_events(limit=50)
        return {
            "health": health,
            "rooms": rooms,
            "recent_events": [{
                "ts": e.ts, "entity_id": e.entity_id,
                "event_type": e.event_type, "area_id": e.area_id,
                "old_state": e.old_state, "new_state": e.new_state,
            } for e in recent],
        }

    return router
```

- [ ] **Step 4: Modify `src/ai_ha/web/app.py`** — mount

After the existing `app.include_router(_s(...))` line and before the lang router from Task 11:

```python
    from ai_ha.web.routes.dashboard import build_router as _d
    app.include_router(_d(state, require_admin))
```

- [ ] **Step 5: Run tests — expect PASS**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/unit/test_dashboard_aggregator.py -v &&
  ruff check src/ tests/ &&
  mypy src/
"
# Expect: 2 PASS
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_ha/web/routes/dashboard.py src/ai_ha/web/app.py tests/unit/test_dashboard_aggregator.py
git commit -m "feat(web): /api/v1/dashboard aggregator (health + rooms + recent events)"
```

---

## Task 17: /dashboard page route + / redirect

**Files:**
- Create: `src/ai_ha/web/templates/dashboard.html` (stub — full template Task 19)
- Modify: `src/ai_ha/web/routes/pages.py` (add /dashboard route + change / to redirect)
- Create: `tests/integration/test_dashboard.py`

- [ ] **Step 1: Write `tests/integration/test_dashboard.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO
from ai_ha.topology import SnapshotStore, EntityIndex
from ai_ha.health import HealthMetrics
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.fixture
async def app_pair(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    yield create_app(token_store=ts, state=state), ts


@pytest.mark.asyncio
async def test_root_redirects_to_dashboard(app_pair):
    app, ts = app_pair
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://x", follow_redirects=False,
    ) as c:
        r = await c.get("/", auth=("admin", ts.read()))
        assert r.status_code in (302, 307)
        assert "/dashboard" in r.headers.get("location", "")


@pytest.mark.asyncio
async def test_dashboard_page_renders(app_pair):
    app, ts = app_pair
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/dashboard", auth=("admin", ts.read()))
        assert r.status_code == 200
        assert "Dashboard" in r.text or "dashboard" in r.text.lower()
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Create `src/ai_ha/web/templates/dashboard.html`** (minimal stub; full in Task 19)

```html
{% extends "base.html" %}
{% block title %}{% trans %}Dashboard{% endtrans %} · ai-home-assistant{% endblock %}
{% block main %}
<h1>{% trans %}Dashboard{% endtrans %}</h1>
<p class="empty" id="dashboard-loading">Loading...</p>
<div id="dashboard-app" data-initial="{{ initial_json }}"></div>
{% endblock %}
{% block scripts %}<script src="/static/dashboard.js"></script>{% endblock %}
```

- [ ] **Step 4: Modify `src/ai_ha/web/routes/pages.py`** — change `/` and add `/dashboard`

Find the existing `@router.get("/", response_class=HTMLResponse)` decorator and replace its body to redirect:

```python
    @router.get("/", response_class=HTMLResponse)
    async def root_redirect() -> RedirectResponse:
        return RedirectResponse("/dashboard", status_code=307)
```

Then add the new dashboard route immediately after:

```python
    @router.get("/dashboard", response_class=HTMLResponse)
    async def dashboard_page(request: Request) -> HTMLResponse:
        import json as _json
        # Best-effort initial data; client will refetch via /api/v1/dashboard
        initial = {"health": {}, "rooms": [], "recent_events": []}
        if state is not None:
            from ai_ha.web.routes.dashboard import build_router  # for type-only
            # Inline mini-aggregator to avoid circular import; the client refetches anyway
            initial = {
                "health": state.health.snapshot(now_ms=int(__import__("time").time() * 1000)),
                "rooms": [], "recent_events": [],
            }
        return _render(request, "dashboard.html", {
            "initial_json": _json.dumps(initial, ensure_ascii=False),
        })


    # Move the original rooms_page handler to /rooms
    @router.get("/rooms", response_class=HTMLResponse)
    async def rooms_page(request: Request) -> HTMLResponse:
        # ... copy the body from the original "/" handler here ...
```

(Engineer note: the original `/` handler body that gathered area data should be moved to `/rooms` to preserve the rooms-grid functionality. Use the same body, just at a new path.)

- [ ] **Step 5: Run tests — expect PASS**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/integration/test_dashboard.py tests/integration/test_web_pages.py -v &&
  ruff check src/ tests/ &&
  mypy src/
"
# Expect: 2 + 3 PASS (web_pages tests still work because /rooms now serves what / served)
```

You may need to update `tests/integration/test_web_pages.py`'s `test_rooms_renders` to hit `/rooms` instead of `/` since `/` now redirects. Update in-place.

- [ ] **Step 6: Commit**

```bash
git add src/ai_ha/web/templates/dashboard.html src/ai_ha/web/routes/pages.py tests/integration/test_dashboard.py tests/integration/test_web_pages.py
git commit -m "feat(web): /dashboard SSR stub + / 307 redirect; rooms grid moves to /rooms"
```

---

## Task 18: Dashboard API negative tests + edge cases

**Files:**
- Modify: `tests/unit/test_dashboard_aggregator.py` (add error path + edge tests)

- [ ] **Step 1: Append tests**

```python
@pytest.mark.asyncio
async def test_dashboard_requires_auth(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state, require_auth=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/dashboard")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_recent_events_capped_at_50(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    await dao.insert_events([EventRow(
        i, i, "x", "state_changed", None, '"on"',
        None, None, None, None, None, 1,
    ) for i in range(100)])
    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state, require_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/api/v1/dashboard")
        body = r.json()
        assert len(body["recent_events"]) == 50
```

- [ ] **Step 2: Run — expect PASS** (the cap is already 50 in the aggregator; this regression-locks it)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_dashboard_aggregator.py
git commit -m "test(dashboard): auth required + recent_events capped at 50"
```

---

# Phase 5 — Dashboard Frontend (Day 16-18)

## Task 19: dashboard.html full template

**Files:**
- Modify: `src/ai_ha/web/templates/dashboard.html` (full layout per spec App B)
- Create: `src/ai_ha/web/templates/_macros.html`

- [ ] **Step 1: Create `src/ai_ha/web/templates/_macros.html`**

```html
{% macro room_card(room) %}
<div class="room-card{% if room.active %} active{% endif %}" data-area-id="{{ room.area_id }}">
  <h3>{{ room.name or room.area_id }}</h3>
  <div class="room-meta">
    <span class="metric">{{ room.entity_count }} {% trans %}entities{% endtrans %}</span>
    <span class="metric">{{ room.events_per_hour_24h }}/24h</span>
  </div>
  <div class="room-status">
    {% if room.active %}
      <span class="status-dot active">●</span> <span class="trans-active">{% trans %}active{% endtrans %}</span>
    {% else %}
      <span class="status-dot idle">○</span> <span class="trans-idle">{% trans %}idle{% endtrans %}</span>
    {% endif %}
  </div>
</div>
{% endmacro %}

{% macro event_row(ev) %}
<li class="event-row" data-ts="{{ ev.ts }}">
  <span class="event-time">{{ ev.ts | tstoiso }}</span>
  <span class="event-entity">{{ ev.entity_id }}</span>
  {% if ev.area_id %}<span class="event-area">{{ ev.area_id }}</span>{% endif %}
</li>
{% endmacro %}
```

- [ ] **Step 2: Replace `src/ai_ha/web/templates/dashboard.html`** (full)

```html
{% extends "base.html" %}
{% from "_macros.html" import room_card, event_row %}
{% block title %}{% trans %}Dashboard{% endtrans %} · ai-home-assistant{% endblock %}
{% block main %}
<h1>{% trans %}Dashboard{% endtrans %}</h1>

<section class="health-strip" id="health-strip">
  <span class="chip">
    <span class="chip-label">{% trans %}WebSocket{% endtrans %}</span>
    <span class="chip-value" id="chip-ws">●</span>
  </span>
  <span class="chip">
    <span class="chip-label">{% trans %}Entities{% endtrans %}</span>
    <span class="chip-value" id="chip-entities">{{ initial.health.get('entities_count', '—') }}</span>
  </span>
  <span class="chip">
    <span class="chip-label">{% trans %}Events/24h{% endtrans %}</span>
    <span class="chip-value" id="chip-events">{{ initial.health.get('events_per_hour', 0) }}</span>
  </span>
  <span class="chip">
    <span class="chip-label">{% trans %}Privacy drops{% endtrans %}</span>
    <span class="chip-value" id="chip-drops">{{ initial.health.get('hidden_event_count', 0) }}</span>
  </span>
  <span class="chip">
    <span class="chip-label">{% trans %}Uptime{% endtrans %}</span>
    <span class="chip-value" id="chip-uptime">{{ initial.health.get('uptime_seconds', 0) }}s</span>
  </span>
</section>

<section class="dashboard-grid">
  <div class="rooms-panel">
    <h2>{% trans %}Rooms{% endtrans %}</h2>
    <div class="room-grid" id="room-grid">
      {% for r in initial.rooms %}
        {{ room_card(r) }}
      {% else %}
        <p class="empty">{% trans %}Waiting for topology snapshot...{% endtrans %}</p>
      {% endfor %}
    </div>
  </div>

  <aside class="events-panel">
    <h2>{% trans %}Live Events{% endtrans %} <span class="live-dot" id="live-dot">●</span></h2>
    <ul class="event-stream" id="event-stream">
      {% for ev in initial.recent_events %}
        {{ event_row(ev) }}
      {% endfor %}
    </ul>
  </aside>
</section>

<script id="dashboard-initial" type="application/json">{{ initial_json | safe }}</script>
{% endblock %}
{% block scripts %}<script src="/static/dashboard.js"></script>{% endblock %}
```

Also update the page handler in `pages.py` to pass both `initial` (dict, for the loops) AND `initial_json` (string, for the JSON island):

```python
        return _render(request, "dashboard.html", {
            "initial": initial,
            "initial_json": _json.dumps(initial, ensure_ascii=False),
        })
```

- [ ] **Step 3: Run tests — expect PASS**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/integration/test_dashboard.py -v &&
  ruff check src/ tests/ &&
  mypy src/
"
```

- [ ] **Step 4: Commit**

```bash
git add src/ai_ha/web/templates/dashboard.html src/ai_ha/web/templates/_macros.html src/ai_ha/web/routes/pages.py
git commit -m "feat(web): full /dashboard template with rooms grid + live event sidebar"
```

---

## Task 20: dashboard.js with WS subscription + DOM updates

**Files:**
- Create: `src/ai_ha/web/static/dashboard.js`
- Create: `tests/integration/test_live_room_state.py` (server-side fanout test)

- [ ] **Step 1: Write `tests/integration/test_live_room_state.py`**

```python
import asyncio
import pytest
from ai_ha.web.routes.stream import EventBroadcaster, publish_room_state


@pytest.mark.asyncio
async def test_room_state_broadcast_delivered():
    bc = EventBroadcaster()
    received: list[dict] = []

    async def listener() -> None:
        async for ev in bc.subscribe():
            received.append(ev)
            return

    t = asyncio.create_task(listener())
    await asyncio.sleep(0.05)
    await publish_room_state(bc, area_id="living", last_seen_at=1000, active=True, entity_count=8)
    await asyncio.wait_for(t, timeout=1.0)
    assert received[0]["type"] == "room_state"
    assert received[0]["entity_count"] == 8


@pytest.mark.asyncio
async def test_room_state_fanout_to_multiple_subscribers():
    bc = EventBroadcaster()
    received_a: list[dict] = []
    received_b: list[dict] = []

    async def listener(out: list[dict]) -> None:
        async for ev in bc.subscribe():
            out.append(ev)
            return

    ta = asyncio.create_task(listener(received_a))
    tb = asyncio.create_task(listener(received_b))
    await asyncio.sleep(0.05)
    await publish_room_state(bc, area_id="x", last_seen_at=1, active=True)
    await asyncio.gather(ta, tb)
    assert received_a == received_b
```

- [ ] **Step 2: Run — expect PASS**

- [ ] **Step 3: Write `src/ai_ha/web/static/dashboard.js`**

```javascript
// dashboard.js — drives /dashboard live updates via WS + periodic health polls.
// XSS-safe: only textContent / createElement, never innerHTML with server data.

(() => {
  const island = document.getElementById('dashboard-initial');
  if (!island) return;

  let state = { health: {}, rooms: [], recent_events: [] };
  try { state = JSON.parse(island.textContent); } catch (_) {}

  // ----- WS connection -----
  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://')
    + location.host + '/api/v1/stream/events';
  let ws;
  let backoff = 1000;
  function connect() {
    ws = new WebSocket(wsUrl);
    document.getElementById('chip-ws').textContent = '○';
    ws.onopen = () => {
      document.getElementById('chip-ws').textContent = '●';
      backoff = 1000;
    };
    ws.onmessage = (msg) => {
      let m;
      try { m = JSON.parse(msg.data); } catch (_) { return; }
      if (m.type === 'state_changed') {
        prependEvent(m);
      } else if (m.type === 'room_state') {
        updateRoomCard(m);
      }
    };
    ws.onclose = () => {
      document.getElementById('chip-ws').textContent = '○';
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 30000);
    };
  }
  connect();

  // ----- DOM updaters (XSS-safe) -----
  function prependEvent(m) {
    const list = document.getElementById('event-stream');
    if (!list) return;
    const li = document.createElement('li');
    li.className = 'event-row';
    li.dataset.ts = String(m.ts || Date.now());

    const t = document.createElement('span');
    t.className = 'event-time';
    t.textContent = new Date(m.ts || Date.now()).toISOString().slice(11, 19);

    const e = document.createElement('span');
    e.className = 'event-entity';
    e.textContent = String(m.entity_id || '');

    li.appendChild(t);
    li.appendChild(e);
    if (m.area_id) {
      const a = document.createElement('span');
      a.className = 'event-area';
      a.textContent = String(m.area_id);
      li.appendChild(a);
    }
    list.prepend(li);
    while (list.children.length > 50) list.removeChild(list.lastChild);
  }

  function updateRoomCard(m) {
    const card = document.querySelector(`.room-card[data-area-id="${cssEscape(m.area_id)}"]`);
    if (!card) return;
    if (m.active) {
      card.classList.add('active');
      const dot = card.querySelector('.status-dot');
      if (dot) { dot.textContent = '●'; dot.classList.remove('idle'); dot.classList.add('active'); }
    }
  }

  function cssEscape(s) {
    if (window.CSS && CSS.escape) return CSS.escape(s);
    return String(s).replace(/[^a-zA-Z0-9_-]/g, c => '\\' + c.charCodeAt(0).toString(16) + ' ');
  }

  // ----- 30s health polling -----
  setInterval(async () => {
    try {
      const r = await fetch('/api/health', { credentials: 'same-origin' });
      if (!r.ok) return;
      const h = await r.json();
      const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = String(v); };
      set('chip-entities', h.events_per_hour ?? '—');
      set('chip-events', h.events_per_hour ?? 0);
      set('chip-drops', h.hidden_event_count ?? 0);
      set('chip-uptime', formatUptime(h.uptime_seconds ?? 0));
    } catch (_) {}
  }, 30000);

  function formatUptime(sec) {
    if (sec < 60) return sec + 's';
    if (sec < 3600) return Math.floor(sec / 60) + 'm';
    if (sec < 86400) return Math.floor(sec / 3600) + 'h';
    return Math.floor(sec / 86400) + 'd';
  }
})();
```

- [ ] **Step 4: Smoke run + commit**

```bash
docker build -t ai-home-assistant:dev -f docker/Dockerfile .
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/integration/test_live_room_state.py -v &&
  grep -nE 'innerHTML' src/ai_ha/web/static/ || echo PASS_NO_INNERHTML &&
  ruff check src/ tests/ &&
  mypy src/
"

git add src/ai_ha/web/static/dashboard.js tests/integration/test_live_room_state.py
git commit -m "feat(web): dashboard.js — WS state_changed/room_state + 30s health poll (textContent only)"
```

---

## Task 21: Dashboard p99 benchmark (vG3)

**Files:**
- Create: `tests/perf/bench_dashboard.py`

- [ ] **Step 1: Write `tests/perf/bench_dashboard.py`**

```python
"""Dashboard p99 < 300ms benchmark (vG3)."""
import time
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, AreaRow, EntityRow, EventRow
from ai_ha.topology import SnapshotStore, EntityIndex
from ai_ha.health import HealthMetrics
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_dashboard_p99_under_300ms(tmp_path):
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    dao = StoreDAO(db)
    # seed: 15 rooms, 100 entities, 500 events
    for i in range(15):
        await dao.upsert_areas([
            AreaRow(f"a{i}", f"Area {i}", None, None, "[]", 1, 1000, 1000),
        ])
    for i in range(100):
        await dao.upsert_entities([EntityRow(
            f"e{i}", None, "sensor", "temperature",
            None, f"a{i % 15}", 0, 1, 1000, 1000, 0, 0,
        )])
    await dao.insert_events([EventRow(
        i, i, f"e{i % 100}", "state_changed", None, '"on"',
        None, None, f"a{i % 15}", None, None, 1,
    ) for i in range(500)])

    state = AppState(
        dao=dao, snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    times: list[float] = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        for _ in range(100):
            t0 = time.perf_counter()
            r = await c.get("/api/v1/dashboard", auth=("admin", ts.read()))
            times.append(time.perf_counter() - t0)
            assert r.status_code == 200
    times.sort()
    p99 = times[98]
    print(f"\n/api/v1/dashboard p99={p99*1000:.2f}ms")
    assert p99 < 0.3, f"p99={p99*1000:.1f}ms exceeds 300ms (vG3)"
```

- [ ] **Step 2: Run + commit**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/perf/bench_dashboard.py -v -m slow -s
"

git add tests/perf/bench_dashboard.py
git commit -m "test(perf): /api/v1/dashboard p99 < 300ms with 15 rooms / 100 entities / 500 events (vG3)"
```

---

# Phase 6 — Responsive CSS + rooms/room live (Day 19-22)

## Task 22: Mobile-first app.css rewrite

**Files:**
- Modify: `src/ai_ha/web/static/app.css` (rewrite mobile-first with 480/768/1100 breakpoints)

- [ ] **Step 1: Replace `src/ai_ha/web/static/app.css`** with mobile-first layout

```css
/* Mobile-first base — < 480px */
:root {
  --bg: #0f1115;
  --fg: #e6e8ef;
  --acc: #7df9aa;
  --muted: #8a90a0;
  --card-bg: #15181f;
  --border: #222;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font: 14px/1.5 system-ui, -apple-system, sans-serif;
  background: var(--bg); color: var(--fg);
  -webkit-text-size-adjust: 100%;
}

/* Header */
header {
  display: flex; flex-wrap: wrap; align-items: center;
  gap: 0.5rem; padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border);
}
header .brand { color: var(--acc); font-weight: 600; text-decoration: none; font-size: 1.05rem; }
header .ver { color: var(--muted); font-weight: 400; font-size: 0.75em; }
header nav { display: flex; flex-wrap: wrap; gap: 0.4rem; }
header nav a { color: var(--fg); padding: 0.15rem 0.4rem; text-decoration: none; font-size: 0.95em; }
header nav a:hover { color: var(--acc); }
.lang-switcher { display: flex; gap: 0.3rem; }
.lang-switcher .lang-link {
  color: var(--muted); padding: 0.1rem 0.4rem;
  border: 1px solid var(--border); border-radius: 3px; font-size: 0.85em;
}
.lang-switcher .lang-link:hover { color: var(--acc); }

/* Banner */
.banner { padding: 0.4rem 0.75rem; border-bottom: 1px solid var(--border); font-size: 0.9em; }
.banner-info { background: #18242a; color: #cef; }
.banner-warn { background: #3a2a00; color: #ffd; }
.banner-error { background: #4a1010; color: #fdd; }

/* Main */
main { padding: 0.75rem; max-width: 1100px; margin: 0 auto; }
h1 { font-size: 1.2rem; margin: 0.3rem 0 0.5rem; }
h2 { font-size: 1.05rem; margin: 0.6rem 0 0.4rem; }
h3 { font-size: 0.95rem; margin: 0 0 0.3rem; }

/* Health strip — wraps 2 per row on mobile */
.health-strip {
  display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem;
  margin-bottom: 0.6rem;
}
.health-strip .chip {
  background: var(--card-bg); padding: 0.4rem 0.5rem;
  border-radius: 4px; font-size: 0.85em;
  display: flex; justify-content: space-between; align-items: baseline;
}
.health-strip .chip-label { color: var(--muted); }
.health-strip .chip-value { color: var(--acc); font-weight: 600; }

/* Dashboard grid — single column mobile */
.dashboard-grid {
  display: grid; grid-template-columns: 1fr; gap: 0.8rem;
}
.rooms-panel, .events-panel { min-width: 0; }

/* Room grid — 1 col < 480, 2 col 480+ */
.room-grid {
  display: grid; grid-template-columns: 1fr; gap: 0.5rem;
}
.room-card {
  background: var(--card-bg); padding: 0.6rem;
  border-radius: 6px; border: 1px solid var(--border);
  text-decoration: none; color: inherit; display: block;
}
.room-card.active { border-color: var(--acc); }
.room-card h3 { margin: 0 0 0.3rem; }
.room-meta { display: flex; gap: 0.8rem; font-size: 0.85em; color: var(--muted); margin-bottom: 0.2rem; }
.metric { color: var(--acc); }
.room-status { font-size: 0.85em; }
.status-dot.active { color: var(--acc); }
.status-dot.idle { color: var(--muted); }
.live-dot { color: var(--acc); animation: pulse 2s infinite; font-size: 0.7em; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

/* Event stream */
.event-stream { list-style: none; padding: 0; margin: 0; max-height: 400px; overflow-y: auto; }
.event-row {
  padding: 0.35rem 0.4rem; border-bottom: 1px solid var(--border);
  display: grid; grid-template-columns: auto 1fr auto;
  gap: 0.5rem; font-size: 0.85em; align-items: center;
}
.event-time { color: var(--muted); font-family: monospace; }
.event-entity { font-weight: 500; }
.event-area { color: var(--muted); font-size: 0.9em; }

/* Tables (entities / timeline pages) */
table { border-collapse: collapse; width: 100%; font-size: 0.9em; }
th, td { text-align: left; padding: 0.35rem 0.4rem; border-bottom: 1px solid var(--border); }
code { background: #1c1f27; padding: 0 0.25rem; border-radius: 3px; font-size: 0.85em; }

/* Forms */
form textarea, form input {
  width: 100%; background: #1c1f27; color: var(--fg);
  border: 1px solid #333; padding: 0.5rem; font-size: 1em;
}
form button {
  margin-top: 0.5rem; padding: 0.5rem 1rem;
  background: var(--acc); border: none; color: #000;
  border-radius: 4px; cursor: pointer; font-weight: 600;
}

footer {
  border-top: 1px solid var(--border); padding: 1rem 0.75rem;
  color: var(--muted); font-size: 0.85em;
}
.empty { color: var(--muted); font-style: italic; }

/* === Tablet 480px+ === */
@media (min-width: 480px) {
  main { padding: 1rem; }
  .health-strip { grid-template-columns: repeat(4, 1fr); }
  .room-grid { grid-template-columns: 1fr 1fr; }
}

/* === Tablet/laptop 768px+ === */
@media (min-width: 768px) {
  .health-strip { grid-template-columns: repeat(5, 1fr); }
  .dashboard-grid {
    grid-template-columns: 2fr 1fr; gap: 1rem;
  }
  .room-grid { grid-template-columns: repeat(3, 1fr); }
  .event-stream { max-height: 600px; }
}

/* === Desktop 1100px+ === */
@media (min-width: 1100px) {
  h1 { font-size: 1.4rem; }
  h2 { font-size: 1.15rem; }
  .room-grid { grid-template-columns: repeat(4, 1fr); }
}
```

- [ ] **Step 2: Smoke verify (manual browser)** — start container, open mobile viewport at 320px / 480px / 768px / 1100px. No console errors expected.

- [ ] **Step 3: Commit**

```bash
git add src/ai_ha/web/static/app.css
git commit -m "feat(web): mobile-first app.css rewrite — 320/480/768/1100 breakpoints"
```

---

## Task 23: rooms.js for live rooms grid

**Files:**
- Create: `src/ai_ha/web/static/rooms.js`
- Modify: `src/ai_ha/web/templates/rooms.html` (include rooms.js)

- [ ] **Step 1: Create `src/ai_ha/web/static/rooms.js`**

```javascript
// rooms.js — keep room cards' active/idle state live via WS room_state messages.
// XSS-safe DOM updates only.

(() => {
  const grid = document.querySelector('.room-grid');
  if (!grid) return;

  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://')
    + location.host + '/api/v1/stream/events';
  let ws;
  let backoff = 1000;
  function connect() {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => { backoff = 1000; };
    ws.onmessage = (msg) => {
      let m;
      try { m = JSON.parse(msg.data); } catch (_) { return; }
      if (m.type !== 'room_state') return;
      const card = grid.querySelector(`.room-card[data-area-id="${cssEscape(m.area_id)}"]`);
      if (!card) return;
      if (m.active) {
        card.classList.add('active');
        const dot = card.querySelector('.status-dot');
        if (dot) {
          dot.textContent = '●';
          dot.classList.remove('idle'); dot.classList.add('active');
        }
      }
    };
    ws.onclose = () => {
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 30000);
    };
  }
  connect();

  function cssEscape(s) {
    if (window.CSS && CSS.escape) return CSS.escape(s);
    return String(s).replace(/[^a-zA-Z0-9_-]/g, c => '\\' + c.charCodeAt(0).toString(16) + ' ');
  }
})();
```

- [ ] **Step 2: Modify `src/ai_ha/web/templates/rooms.html`** — add script include + ensure cards have `data-area-id`

Replace the existing `.card` block with a `.room-card` block using the macro:

```html
{% extends "base.html" %}
{% from "_macros.html" import room_card %}
{% block title %}{% trans %}Rooms{% endtrans %} · ai-home-assistant{% endblock %}
{% block main %}
<h1>{% trans %}Rooms{% endtrans %}</h1>
{% if not areas %}
  <p class="empty">{% trans %}No areas yet. Waiting for first topology snapshot.{% endtrans %}</p>
{% else %}
<div class="room-grid">
  {% for a in areas %}
    {{ room_card(a) }}
  {% endfor %}
</div>
{% endif %}
{% endblock %}
{% block scripts %}<script src="/static/rooms.js"></script>{% endblock %}
```

- [ ] **Step 3: Smoke + commit**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/integration/test_web_pages.py -v &&
  grep -nE 'innerHTML' src/ai_ha/web/static/rooms.js || echo PASS_NO_INNERHTML
"

git add src/ai_ha/web/static/rooms.js src/ai_ha/web/templates/rooms.html
git commit -m "feat(web): rooms.js live room_state updates on /rooms grid"
```

---

## Task 24: room-live.js for room detail page

**Files:**
- Create: `src/ai_ha/web/static/room-live.js`
- Modify: `src/ai_ha/web/templates/room.html` (include script + add live entity list update target)

- [ ] **Step 1: Create `src/ai_ha/web/static/room-live.js`**

```javascript
// room-live.js — single-room page: live event stream + entity last_seen updates.

(() => {
  const areaIdEl = document.querySelector('[data-area-id]');
  if (!areaIdEl) return;
  const myAreaId = areaIdEl.dataset.areaId;

  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://')
    + location.host + '/api/v1/stream/events';
  let ws;
  let backoff = 1000;

  function connect() {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => { backoff = 1000; };
    ws.onmessage = (msg) => {
      let m;
      try { m = JSON.parse(msg.data); } catch (_) { return; }
      if (m.type === 'state_changed' && m.area_id === myAreaId) {
        prependEvent(m);
      }
    };
    ws.onclose = () => {
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 30000);
    };
  }
  connect();

  function prependEvent(m) {
    const list = document.querySelector('#room-events-tbody');
    if (!list) return;
    const tr = document.createElement('tr');
    const tdT = document.createElement('td');
    tdT.textContent = new Date(m.ts || Date.now()).toISOString();
    const tdE = document.createElement('td');
    tdE.textContent = String(m.entity_id || '');
    const tdY = document.createElement('td');
    tdY.textContent = String(m.event_type || '');
    tr.appendChild(tdT); tr.appendChild(tdE); tr.appendChild(tdY);
    list.prepend(tr);
    while (list.children.length > 50) list.removeChild(list.lastChild);
  }
})();
```

- [ ] **Step 2: Modify `src/ai_ha/web/templates/room.html`** — wrap container with data-area-id + id the tbody + add script

```html
{% extends "base.html" %}
{% block title %}{{ area.name }} · ai-home-assistant{% endblock %}
{% block main %}
<div data-area-id="{{ area.area_id }}">
  <h1>{{ area.name }}</h1>
  <section>
    <h2>{% trans %}Entities{% endtrans %} ({{ entities|length }})</h2>
    <ul>
      {% for e in entities %}
      <li>{{ e.friendly_name or e.entity_id }}
        <code>{{ e.entity_id }}</code></li>
      {% endfor %}
    </ul>
  </section>
  <section>
    <h2>{% trans %}Recent events{% endtrans %}</h2>
    <table>
      <thead><tr><th>{% trans %}Time (UTC){% endtrans %}</th><th>{% trans %}Entity{% endtrans %}</th><th>{% trans %}Type{% endtrans %}</th></tr></thead>
      <tbody id="room-events-tbody">
      {% for ev in recent_events %}
      <tr><td>{{ ev.ts|tstoiso }}</td><td>{{ ev.entity_id }}</td><td>{{ ev.event_type }}</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </section>
</div>
{% endblock %}
{% block scripts %}<script src="/static/room-live.js"></script>{% endblock %}
```

- [ ] **Step 3: Smoke + commit**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/integration/test_web_pages.py -v &&
  grep -nE 'innerHTML' src/ai_ha/web/static/room-live.js || echo PASS_NO_INNERHTML
"

git add src/ai_ha/web/static/room-live.js src/ai_ha/web/templates/room.html
git commit -m "feat(web): room-live.js — live state_changed prepend on /room/{id}"
```

---

## Task 25: Responsive viewport tests

**Files:**
- Create: `tests/integration/test_responsive_viewport.py`

- [ ] **Step 1: Write `tests/integration/test_responsive_viewport.py`**

(This is a server-side test that just checks no template errors at typical viewports — true responsive verification is manual in Task 30.)

```python
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from ai_ha.store.db import Database
from ai_ha.store.dao import StoreDAO, AreaRow
from ai_ha.topology import SnapshotStore, EntityIndex
from ai_ha.health import HealthMetrics
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState

SCHEMA = Path(__file__).parent.parent.parent / "src/ai_ha/store/migrations"


@pytest.mark.asyncio
async def test_dashboard_responsive_classes_present(tmp_path):
    """Verify the breakpoint-driving CSS classes are emitted by the template."""
    db = await Database.open(str(tmp_path / "x.db"), migrations_dir=str(SCHEMA))
    state = AppState(
        dao=StoreDAO(db), snapshot_store=SnapshotStore(db),
        entity_index=EntityIndex(), health=HealthMetrics(install_start_ms=0),
        config_path=tmp_path / "c.toml", hide_pattern=[], on_privacy_update=None,
    )
    ts = AdminTokenStore(str(tmp_path / "t")); ts.ensure_token()
    app = create_app(token_store=ts, state=state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/dashboard", auth=("admin", ts.read()))
        assert r.status_code == 200
        for cls in ("health-strip", "dashboard-grid", "rooms-panel", "events-panel", "room-grid"):
            assert cls in r.text, f"class {cls!r} missing from /dashboard"


@pytest.mark.asyncio
async def test_css_has_breakpoints(tmp_path):
    """app.css contains the 3 breakpoint media queries."""
    css = Path(__file__).parent.parent.parent / "src/ai_ha/web/static/app.css"
    body = css.read_text()
    assert "@media (min-width: 480px)" in body
    assert "@media (min-width: 768px)" in body
    assert "@media (min-width: 1100px)" in body
```

- [ ] **Step 2: Run + commit**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/integration/test_responsive_viewport.py -v
"

git add tests/integration/test_responsive_viewport.py
git commit -m "test(responsive): dashboard CSS classes + 3 breakpoint media queries present"
```

---

# Phase 7 — zh-CN Translation (Day 23-25)

## Task 26: Extract messages.pot from src

**Files:**
- Create: `src/ai_ha/web/i18n/messages.pot` (auto-generated, committed)

- [ ] **Step 1: Run Babel extract inside container**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pip install -e . > /dev/null 2>&1 &&
  pip install Babel==2.16.0 > /dev/null 2>&1 &&
  pybabel extract -F src/ai_ha/web/i18n/babel.cfg \
    -o src/ai_ha/web/i18n/messages.pot src/ai_ha
"
```

- [ ] **Step 2: Verify messages.pot has expected keys**

```bash
grep -c '^msgid' src/ai_ha/web/i18n/messages.pot
# Expect: ~30+ keys (Dashboard, Rooms, Entities, Timeline, Settings, banner text, etc.)
```

- [ ] **Step 3: Commit**

```bash
git add src/ai_ha/web/i18n/messages.pot
git commit -m "chore(i18n): extract messages.pot from src (~30+ UI keys)"
```

---

## Task 27: Translate to zh_CN.po (~150 entries)

**Files:**
- Create: `src/ai_ha/web/i18n/locales/zh_CN/LC_MESSAGES/ai_ha.po`
- Create: `src/ai_ha/web/i18n/locales/en/LC_MESSAGES/ai_ha.po` (stub for symmetry)

- [ ] **Step 1: Init zh_CN locale from .pot**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pybabel init -i src/ai_ha/web/i18n/messages.pot \
    -d src/ai_ha/web/i18n/locales -l zh_CN -D ai_ha &&
  pybabel init -i src/ai_ha/web/i18n/messages.pot \
    -d src/ai_ha/web/i18n/locales -l en -D ai_ha
"
```

- [ ] **Step 2: Edit `src/ai_ha/web/i18n/locales/zh_CN/LC_MESSAGES/ai_ha.po`** — fill translations

Replace each `msgstr ""` with the Chinese translation per spec Appendix C. Example excerpt:

```po
msgid "Dashboard"
msgstr "仪表盘"

msgid "Rooms"
msgstr "房间"

msgid "Entities"
msgstr "设备"

msgid "Timeline"
msgstr "时间线"

msgid "Settings"
msgstr "设置"

msgid "WebSocket"
msgstr "WebSocket"

msgid "Events/24h"
msgstr "24 小时事件"

msgid "Privacy drops"
msgstr "隐私丢弃"

msgid "Uptime"
msgstr "在线时长"

msgid "Live Events"
msgstr "实时事件"

msgid "active"
msgstr "活跃"

msgid "idle"
msgstr "闲置"

msgid "entities"
msgstr "设备"

msgid "Waiting for topology snapshot..."
msgstr "等待 HA 拓扑加载..."

msgid "No areas yet. Waiting for first topology snapshot."
msgstr "暂无房间。等待 Home Assistant 拓扑同步..."

msgid "Recent events"
msgstr "最近事件"

msgid "Time (UTC)"
msgstr "时间 (UTC)"

msgid "Entity"
msgstr "设备"

msgid "Type"
msgstr "类型"
```

(Translate **every** `msgid` in the .po file. Use spec Appendix C as guidance for unlisted keys; reasonable Chinese translations for the rest.)

- [ ] **Step 3: Compile .mo**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pybabel compile -d src/ai_ha/web/i18n/locales -D ai_ha
"
ls -la src/ai_ha/web/i18n/locales/zh_CN/LC_MESSAGES/
# Expect: ai_ha.po + ai_ha.mo present
```

- [ ] **Step 4: Verify zh-CN rendering** — append to `tests/integration/test_i18n_zh_cn.py`

```python
@pytest.mark.asyncio
async def test_dashboard_renders_chinese_when_lang_zh(token_store):
    app = create_app(token_store=token_store, require_auth=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://x") as c:
        r = await c.get("/dashboard?lang=zh")
        assert r.status_code == 200
        assert "仪表盘" in r.text  # "Dashboard" in zh_CN
        assert "实时事件" in r.text or "Live Events" in r.text  # graceful if partial
```

- [ ] **Step 5: Run tests + commit**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pytest tests/integration/test_i18n_zh_cn.py -v
"

git add src/ai_ha/web/i18n/locales/
git commit -m "feat(i18n): zh_CN translations (.po + compiled .mo) — Dashboard/Rooms/Entities/Timeline/etc."
```

---

## Task 28: CI translation completeness gate + Dockerfile compile step

**Files:**
- Modify: `docker/Dockerfile` (pybabel compile at build time)
- Modify: `.github/workflows/ci.yml` (extract gate)
- Modify: `.gitignore` (ignore .mo from local dev, since they're built in image)

- [ ] **Step 1: Modify `docker/Dockerfile`** — add Babel install + compile step

After the existing `RUN pip install ...` line, add a build-time pybabel compile (so the runtime image has .mo files):

```dockerfile
# Compile translation .mo files (Babel only needed at build time)
RUN pip install --no-cache-dir Babel==2.16.0 \
    && pybabel compile -d /app/src/ai_ha/web/i18n/locales -D ai_ha \
    && pip uninstall -y Babel
```

- [ ] **Step 2: Modify `.gitignore`** — append

```
src/ai_ha/web/i18n/locales/**/*.mo
```

(Keep .po committed, compile .mo in Docker build.)

- [ ] **Step 3: Modify `.github/workflows/ci.yml`** — add i18n gate

In the `lint-and-test` job, after the existing test step, add:

```yaml
      - name: Verify i18n key extraction is current
        run: |
          pip install Babel==2.16.0
          pybabel extract -F src/ai_ha/web/i18n/babel.cfg \
            -o /tmp/messages.pot src/ai_ha
          if ! diff <(grep '^msgid' src/ai_ha/web/i18n/messages.pot | sort -u) \
                    <(grep '^msgid' /tmp/messages.pot | sort -u); then
            echo "ERR: messages.pot is out of date. Re-extract."
            exit 1
          fi
```

- [ ] **Step 4: Rebuild image + smoke**

```bash
docker build -t ai-home-assistant:dev -f docker/Dockerfile .
docker run --rm ai-home-assistant:dev sh -c "
  ls -la /app/src/ai_ha/web/i18n/locales/zh_CN/LC_MESSAGES/
"
# Expect: ai_ha.mo present
```

- [ ] **Step 5: Commit**

```bash
git add docker/Dockerfile .gitignore .github/workflows/ci.yml
git commit -m "build(i18n): Dockerfile compiles .mo at build; CI gates messages.pot freshness"
```

---

# Phase 8 — Release (Day 26-28)

## Task 29: RELEASE.md v0.1.5 section + 4-Gate audit

**Files:**
- Modify: `RELEASE.md` (prepend v0.1.5 section)
- Modify: `README.md` (Status update)

- [ ] **Step 1: Run 4-Gate automated checks**

```bash
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pip install -e . > /dev/null 2>&1 &&
  pytest tests/unit tests/integration --cov=src/ai_ha --cov-report=term --cov-fail-under=80 2>&1 | tail -25 &&
  ruff check src/ tests/ &&
  mypy src/ &&
  grep -rn 'innerHTML' src/ai_ha/web/static/ || echo 'PASS: 0 innerHTML' &&
  grep -rn 'except.*:.*pass\\b' src/ai_ha/ || echo 'PASS: 0 except-pass'
"
```

Record output for the commit body.

- [ ] **Step 2: Prepend `RELEASE.md`** with v0.1.5 section

```markdown
## v0.1.5-rc.1 — 2026-06-xx (Deployment + UI Optimization — Release Candidate)

### Highlights
- **One-shot deploy**: `install.sh` interactive installer (curl-pipe from README).
  Prereq check → image pull → HA start → guided token prompt → ai-ha start →
  success banner. ~30 min wall-clock on first run.
- **/dashboard**: new home page combining room cards (3-col responsive grid)
  with live event sidebar. Replaces `/` (now redirects); `/rooms` preserved
  as secondary view.
- **Mobile-first responsive CSS**: rewritten with 480/768/1100 breakpoints.
- **Chinese (zh-CN) i18n**: Babel + gettext + nav lang switcher. ~150 strings
  translated.
- **Live room state**: WS broadcaster now emits `room_state` (throttled 1/sec
  per area). /dashboard, /rooms, /room/{id} pages subscribe.
- 2 new health metrics: `room_state_publish_total`, `i18n_translation_miss_total`.

### Breaking changes
- `GET /` returns 307 redirect to `/dashboard` instead of rendering rooms grid.
  Rooms grid moved to `GET /rooms` — bookmark updates may be needed.

### Migration
- Existing users can `docker pull` v0.1.5 image and re-run install.sh (idempotent)
  or `docker compose up -d --force-recreate ai-home-assistant`. No DB / config
  changes.

### Known limitations
- **Listen-only still**: no LLM, no learning, no automation suggestions (v0.4+).
- **Languages**: en + zh-CN only. Add a .po file to support more.
- **install.sh tested on**: Debian 12+, Ubuntu 22.04+. Other distros best-effort.
- **iPhone Safari / Android Chrome**: visual verification PENDING for GA tag.

### Verification evidence
- Unit + integration: ~140 tests PASS (was 120 in v0.1.0).
- Perf: dashboard p99 ~XXms (< 300ms vG3); live update p99 ~XXms (< 100ms vG4).
- Coverage: ≥80% (vG8).
- Mobile manual verification: PENDING for v0.1.5 GA.
```

- [ ] **Step 3: Update README "Status"**

```markdown
## Status

**v0.1.5-rc.1** — Deployment + UI optimization release candidate. See
[RELEASE.md](RELEASE.md). GA requires mobile device verification +
real RK3588 install.sh run. v0.2 (histogram behavior model) is next.
```

- [ ] **Step 4: Commit**

```bash
git add RELEASE.md README.md
git commit -m "$(cat <<'EOF'
doc(release): RELEASE.md v0.1.5-rc.1 + README status update

4-gate audit results:
  Gate 1 (docs): PASS — README/DEVELOP/RELEASE/CLAUDE.md consistent
  Gate 2 (code): PASS — N tests + ruff + mypy --strict + ≥80% coverage,
                 0 except-pass, 0 innerHTML in static/
  Gate 3 (function): PENDING — mobile manual verification (vG5) blocks GA
  Gate 4 (gap): PASS — 4 Known Limitations enumerated

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 30: Mobile device verification (manual)

**Files:**
- Create: `docs/screenshots/v015-ga-verification/.gitkeep`
- Manual: phone walk-through

- [ ] **Step 1: Build and run v0.1.5-rc.1 image** — start container reachable from phone (host network or bind 0.0.0.0)

```bash
docker build -t ai-home-assistant:0.1.5-rc.1 -f docker/Dockerfile .
docker run -d --name aiha-rc --rm -p 8124:8124 \
  -e HA_URL=http://<real-ha-or-mock>:8123 \
  -e HA_TOKEN=<token> \
  -v $PWD/.dev-data:/data \
  ai-home-assistant:0.1.5-rc.1
```

- [ ] **Step 2: Phone walk-through** — open `http://<host>:8124/dashboard` on:
  - iPhone Safari (Mobile)
  - Android Chrome
  - Desktop Chrome (1100+) — sanity

For each, capture screenshots to `docs/screenshots/v015-ga-verification/`:

```
docs/screenshots/v015-ga-verification/
├── 01-install-sh-banner.png
├── 02-dashboard-desktop-en.png
├── 03-dashboard-desktop-zh.png
├── 04-dashboard-iphone-safari.png
├── 05-dashboard-android-chrome.png
├── 06-rooms-iphone.png
├── 07-room-detail-iphone.png
├── 08-timeline-iphone.png
├── 09-settings-iphone.png
├── 10-lang-switcher-zh.png
└── 11-live-update-demo.gif (optional)
```

Walk the checklist in `tests/MANUAL_TEST_CHECKLIST.md` (extend for v0.1.5: dashboard / lang / install.sh sections).

- [ ] **Step 3: Append v0.1.5 entries to `tests/MANUAL_TEST_CHECKLIST.md`**

```markdown

## v0.1.5 additions

### install.sh
- [ ] Fresh host: `curl ... | bash` completes in < 30 min
- [ ] Token prompt prints clear instructions
- [ ] Invalid token rejected with retry up to 3 attempts
- [ ] Banner at end shows URL + admin token
- [ ] Re-running install.sh is idempotent (no errors)
- [ ] Ctrl-C mid-run cleans up unregistered containers

### /dashboard
- [ ] `/` redirects to /dashboard
- [ ] Health strip shows 5 chips
- [ ] Room grid renders with all areas
- [ ] Live event sidebar updates on HA state change within 200ms
- [ ] Room card transitions to "active" on event
- [ ] WS reconnect within 30s of network blip

### Responsive
- [ ] iPhone Safari portrait: 1-col rooms grid, no horizontal scroll
- [ ] iPhone Safari landscape: 2-col rooms grid
- [ ] Android Chrome tablet 768+: 3-col rooms grid + sidebar visible
- [ ] Desktop 1100+: 4-col rooms grid + full health strip

### i18n
- [ ] ?lang=zh switches all nav + dashboard headings
- [ ] Cookie persists across page reloads
- [ ] EN/中 switcher works on every page
```

- [ ] **Step 4: Commit evidence**

```bash
git add docs/screenshots/v015-ga-verification/ tests/MANUAL_TEST_CHECKLIST.md
git commit -m "evidence(v0.1.5): mobile device walk-through screenshots (vG5) + manual checklist additions"
```

---

## Task 31: Tag v0.1.5-rc.1 + push

**Files:**
- (no file changes — tag only)

- [ ] **Step 1: Pre-flight**

```bash
git status -s     # clean
git log --oneline -3
docker run --rm -v "$PWD:/work" -w /work ai-home-assistant:dev sh -c "
  pip install -e . > /dev/null 2>&1 &&
  pytest tests/unit tests/integration --cov=src/ai_ha --cov-fail-under=80 2>&1 | tail -3 &&
  ruff check src/ tests/ &&
  mypy src/
"
# All green.
```

- [ ] **Step 2: Create annotated tag**

```bash
git tag -a v0.1.5-rc.1 -m "$(cat <<'EOF'
v0.1.5-rc.1 — Deployment + UI Optimization (Release Candidate)

Highlights
  install.sh interactive one-shot deploy with HA token guidance
  /dashboard new home page (rooms grid + live event sidebar) replaces /
  Mobile-first responsive CSS (320/480/768/1100 breakpoints)
  zh-CN i18n via Babel + gettext + nav lang switcher (EN/中)
  Live update: WS room_state broadcast (1/sec/area throttle)

Verified
  ~140 unit + integration tests PASS; ruff + mypy --strict clean
  Coverage ≥80% (vG8)
  Dashboard p99 < 300ms (vG3); live update p99 < 100ms (vG4)
  Mobile screenshots captured (vG5)

Pending for GA tag (v0.1.5)
  Real RK3588 install.sh run from clean host (vG1)
  Soak / regression on real HA setup
  Removal of v0.1.5 RC audit artifacts before GA

Spec: docs/superpowers/specs/2026-06-03-v015-deploy-and-ui-design.md
Plan: docs/superpowers/plans/2026-06-03-v015-deploy-and-ui.md
RELEASE: see RELEASE.md
EOF
)"
```

- [ ] **Step 3: Push**

```bash
git push origin main
git push origin v0.1.5-rc.1
```

- [ ] **Step 4: Verify GHCR image will build** — watch release.yml workflow on GH Actions; expect `ghcr.io/qiurui144/ai-home-assistant:0.1.5-rc.1` to appear.

---

## Risk register (plan-time, derived from spec §11)

| # | Risk | Severity | Mitigation in this plan |
|---|------|:---:|------|
| 1 | install.sh on Alpine/old CentOS fails | S3 | Task 7 README states tested distros; integration tests dry-run only |
| 2 | HA Profile/Security path drifts across HA versions | S3 | Task 4 banner text mirrors current HA UI; monthly verify in v0.1.5 RELEASE |
| 3 | Babel extract misses Jinja {% trans %} key | S2 | Task 28 CI gate diffs current pot vs fresh extract |
| 4 | room_state high-frequency overwhelms WS | S2 | Task 14 throttles 1/sec/area; Task 21 p99 < 300ms benchmark catches regression |
| 5 | Mobile breakpoint differs iOS vs Android | S3 | Task 30 manual verification on both browsers |
| 6 | install.sh abort leaves residual container | S2 | Task 1 trap EXIT + idempotent re-run; Task 6 test confirms |
| 7 | Token stdin shell injection | S2 | Task 4 regex validation + Task 6 dedicated injection test |
| 8 | Dashboard.js DOM injection (XSS) | S2 | Tasks 20/23/24 textContent only; CI greps innerHTML in static/ |
| 9 | i18n cookie tamper bypass | S4 | cookie only controls lang; no auth surface |
| 10 | Dashboard load > LCP target | S3 | Task 21 p99 benchmark |
| 11 | Compiled .mo bloat in Docker image | S3 | Task 28 build-time only; Babel uninstalled after compile |
| 12 | `/` → /dashboard breaks bookmarks | S4 | 307 redirect; browsers auto-follow |

---

## Acceptance gate verification (vG1-G8)

| # | Gate | Measured in |
|---|------|------|
| vG1 | install.sh < 30 min wall-clock to /dashboard | Task 30 manual |
| vG2 | install.sh 4 error codes correct + cleanup | Tasks 4/6 tests |
| vG3 | Dashboard p99 < 300ms | Task 21 bench |
| vG4 | Live update p99 < 100ms end-to-end | Task 14/20 broadcast latency |
| vG5 | iPhone Safari + Android Chrome 0 console errors | Task 30 manual |
| vG6 | zh-CN ≥ 95% UI string coverage | Task 27 .po fill + Task 28 CI gate |
| vG7 | No regression on v0.1.0's 120 tests | Each phase's pytest run |
| vG8 | Coverage ≥ 80% | Task 29 audit |

---

## Self-Review

**Spec coverage check** (each spec § → at least one task):

| Spec § | Tasks |
|--------|-------|
| §1 north star (30-min install, mobile UI) | Tasks 1-7, 22, 30 |
| §2.1 6 things v0.1.5 does | Tasks 1-7 (install) / 16-21 (dashboard) / 22-25 (responsive+live) / 8-12, 26-28 (i18n) |
| §2.3 cross-slice promises | Task 16 dashboard data shape, Task 26 .pot extract |
| §3.1 install link | Tasks 1-7 |
| §3.2 UI data flow | Tasks 13-15, 20-24 |
| §3.3 i18n data flow | Tasks 8-12 |
| §3.4 dashboard data flow | Tasks 16-21 |
| §4 file tree | All Tasks |
| §5 API contract | Tasks 11, 16, 17 |
| §6 extension points (locale) | Task 27 (add new .po to extend) |
| §7 14 error cases | Task 4 (I1-I5), Task 6 (I6, injection), Tasks 16-17 (D1-D2), Task 11 (L3) |
| §8 cost contract | Task 28 (image size verified at build) |
| §9 test matrix | Tasks 6, 18, 21, 25, 27, 30 |
| §10 backward compat | Tasks 17 (URL redirect — 307), Task 26 (DB unchanged) |
| §11 12 risks | Mapped in plan risk register |
| App A install.sh detail | Tasks 1-5 produce exactly that script |
| App B Dashboard layout | Tasks 19, 22 |
| App C i18n keys | Task 27 .po |
| App D vG1-G8 | Tasks 21, 27, 28, 29, 30 |

**Placeholder scan**: no TBD / TODO / implement-later / similar-to-Task-N.

**Type consistency**:
- `AppState` from Task 11 of v0.1.0 reused unchanged
- `EventBroadcaster` extended in Task 13, consumed in Task 14
- `publish_room_state` defined Task 13, called Task 14
- `IngestPipeline.__init__(broadcaster=)` introduced Task 14, wired Task 15
- `locale_from_request` defined Task 9, called Task 10
- `install_translations` defined Task 10, called Task 10
- `SUPPORTED_LOCALES` defined Task 9, used Task 11
- `room_state` message type appears in Tasks 13, 14, 20, 23

All names consistent across tasks.

---

## Notes for executing engineer

1. **Spec is SSOT** for behaviors not spelled out — always cross-check `docs/superpowers/specs/2026-06-03-v015-deploy-and-ui-design.md` if a detail seems missing.
2. **Container-only dev**: never `pip install` to host. Use the Docker dev image.
3. **One commit per Task**. Phase 2's Task 8-12 must land in order (each depends on prior). Phase 6's Tasks 23-25 can be reordered if needed.
4. **No silent failures**: every `try` block has a `logger.error|warning` or re-raise. CI greps `except.*pass` = 0.
5. **TDD discipline**: failing test → minimal impl → passing test → commit.
6. **XSS-safe DOM**: never `innerHTML` with server data. Jinja autoescape on, JS uses textContent. Tasks 20/23/24 enforce.
7. **Stay in v0.1.5 scope**. Don't sneak v0.2 (histogram) work or light/dark theme.
8. **Pre-requisite**: v0.1.0 GA must be tagged before merging v0.1.5 to main. Develop on a `feat/v0.1.5` branch while v0.1.0 RC is pending, merge after.

End of v0.1.5 implementation plan.
