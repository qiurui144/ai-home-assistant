"""ai-home-assistant entry — wires all components and runs FastAPI under uvicorn.

Order matches spec §7.1 startup self-check:
  1 load config
  2 compile privacy regex
  3 open DB + migrations
  4 integrity check (in Database.open)
  5 health metrics collector
  6 ha_adapter (REST snapshot once; background retry on failure)
  7 topology fetcher (initial pull; background retry)
  8 ingest pipeline
  9 jsonl writer
 10 config watchfiles
 11 FastAPI / uvicorn
 12 log "ai-ha started"
Steps 1-3 failure → exit non-zero (docker restart). Step 4+ failure → degraded.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

import uvicorn

from ai_ha.archive import JsonlWriter
from ai_ha.config import AppConfig, ConfigError, load_config
from ai_ha.config.watcher import ConfigWatcher
from ai_ha.ha_adapter.topology_fetcher import TopologyFetcher
from ai_ha.ha_adapter.ws_client import HAWSClient
from ai_ha.health import HealthMetrics
from ai_ha.ingest import HAEvent, IngestPipeline
from ai_ha.privacy import HideMatcher, PatternComplexityError
from ai_ha.store.dao import StoreDAO
from ai_ha.store.db import Database
from ai_ha.topology import EntityIndex, SnapshotStore, TopologyOrchestrator
from ai_ha.web.app import create_app
from ai_ha.web.auth import AdminTokenStore
from ai_ha.web.routes import AppState
from ai_ha.web.routes.stream import EventBroadcaster

logger = logging.getLogger("ai_ha")

EXIT_OK = 0
EXIT_DB_UNRECOVERABLE = 70
EXIT_CONFIG = 78


def _bootstrap_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def _print_first_run_banner(token: str) -> None:
    bar = "═" * 60
    print(f"\n{bar}", flush=True)
    print("║ ai-home-assistant FIRST RUN", flush=True)
    print(f"║ admin token: {token}", flush=True)
    print("║ Saved to /data/.admin-token (chmod 0600).", flush=True)
    print("║ Username 'admin', password the token above. v0.1.0.", flush=True)
    print(f"{bar}\n", flush=True)


def _ws_url(http_url: str) -> str:
    if http_url.startswith("https://"):
        return "wss://" + http_url[len("https://"):] + "/api/websocket"
    if http_url.startswith("http://"):
        return "ws://" + http_url[len("http://"):] + "/api/websocket"
    return http_url + "/api/websocket"


async def _run(config_path: str, data_dir: str) -> int:
    _bootstrap_logging()

    try:
        cfg = load_config(config_path)
    except ConfigError as exc:
        print(f"[ai-ha] config error: {exc}", file=sys.stderr, flush=True)
        return EXIT_CONFIG

    try:
        hide_matcher = HideMatcher(cfg.privacy.hide_entities_pattern)
    except (PatternComplexityError, Exception) as exc:
        print(f"[ai-ha] privacy pattern invalid: {exc}",
              file=sys.stderr, flush=True)
        return EXIT_CONFIG

    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)

    db_path = data_path / "ai-ha.db"
    migrations = Path(__file__).parent / "store" / "migrations"
    try:
        db = await Database.open(str(db_path), migrations_dir=str(migrations))
    except Exception as exc:
        logger.critical("DB open failed: %s", exc)
        return EXIT_DB_UNRECOVERABLE

    dao = StoreDAO(db)
    health = HealthMetrics(install_start_ms=int(time.time() * 1000))
    snapshot_store = SnapshotStore(db)
    entity_index = EntityIndex()
    orchestrator = TopologyOrchestrator(
        snapshot_store=snapshot_store, entity_index=entity_index, dao=dao,
    )
    broadcaster = EventBroadcaster()
    pipeline = IngestPipeline(
        dao=dao, entity_index=entity_index, hide_matcher=hide_matcher,
        broadcaster=broadcaster,
    )
    await pipeline.start()
    jsonl = JsonlWriter(str(data_path / "events"), compress=cfg.archive.compress)

    ws_url = _ws_url(cfg.ha.url)

    async def on_ws_event(msg: dict[str, Any]) -> None:
        ev = msg.get("event", {})
        ev_type = ev.get("event_type", "")
        if ev_type == "state_changed":
            d = ev.get("data", {})
            new = d.get("new_state") or {}
            old = d.get("old_state") or {}
            ha_ev = HAEvent(
                ts_ms=int(time.time() * 1000),
                entity_id=d.get("entity_id", ""),
                event_type="state_changed",
                old_state=str(old.get("state")) if old else None,
                new_state=str(new.get("state")) if new else None,
                context_user_id=(new.get("context") or {}).get("user_id"),
                context_parent_id=(new.get("context") or {}).get("parent_id"),
            )
            await pipeline.submit(ha_ev)
            await jsonl.append({
                "ts_ms": ha_ev.ts_ms, "entity_id": ha_ev.entity_id,
                "event_type": ha_ev.event_type,
                "old_state": ha_ev.old_state, "new_state": ha_ev.new_state,
            }, ts_ms=ha_ev.ts_ms)
            await broadcaster.publish({
                "ts": ha_ev.ts_ms, "entity_id": ha_ev.entity_id,
                "event_type": ha_ev.event_type,
            })
            health.record_event(ts_ms=ha_ev.ts_ms)
        elif ev_type.endswith("_registry_updated"):
            try:
                tf = TopologyFetcher(url=ws_url, token=cfg.ha.token)
                payload = await tf.fetch_once()
                sid, _ = await orchestrator.apply(
                    payload, ts_ms=int(time.time() * 1000),
                )
                health.set_topology_snapshot_id(sid)
            except Exception:
                logger.exception("registry refetch failed")

    ws_client = HAWSClient(url=ws_url, token=cfg.ha.token, on_event=on_ws_event)
    ws_task = asyncio.create_task(ws_client.run())

    async def initial_sync() -> None:
        try:
            tf = TopologyFetcher(url=ws_url, token=cfg.ha.token)
            payload = await tf.fetch_once()
            sid, _ = await orchestrator.apply(payload, ts_ms=int(time.time() * 1000))
            health.set_topology_snapshot_id(sid)
            health.set_ws_connected(True)
        except Exception:
            logger.exception("initial topology sync failed")

    initial_sync_task = asyncio.create_task(initial_sync())

    token_store = AdminTokenStore(str(data_path / ".admin-token"))
    is_first_run = not (data_path / ".admin-token").exists()
    token = token_store.ensure_token()
    if is_first_run:
        _print_first_run_banner(token)

    state = AppState(
        dao=dao, snapshot_store=snapshot_store, entity_index=entity_index,
        health=health, config_path=Path(config_path),
        hide_pattern=cfg.privacy.hide_entities_pattern,
        on_privacy_update=None,
    )
    state.broadcaster = broadcaster

    async def on_cfg_change(new_cfg: AppConfig) -> None:
        try:
            new_matcher = HideMatcher(new_cfg.privacy.hide_entities_pattern)
        except (PatternComplexityError, Exception) as exc:
            health.inc_config_reload_fail()
            logger.warning("privacy pattern reload failed: %s", exc)
            return
        pipeline._hide = new_matcher
        state.hide_pattern = new_cfg.privacy.hide_entities_pattern
        logger.info("privacy pattern reloaded: %d rules",
                    len(new_cfg.privacy.hide_entities_pattern))

    state.on_privacy_update = on_cfg_change
    watcher = ConfigWatcher(config_path, on_cfg_change)
    watcher_task = asyncio.create_task(watcher.run())

    app = create_app(
        token_store=token_store, require_auth=cfg.web.require_auth, state=state,
    )

    logger.info("ai-ha started, schema_version=1, topology=<pending>")

    cfg_uv = uvicorn.Config(
        app=app, host=cfg.web.host, port=cfg.web.port,
        log_level="info", lifespan="on",
    )
    server = uvicorn.Server(cfg_uv)

    def _handle_sig(*_a: object) -> None:
        server.should_exit = True

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_sig)

    try:
        await server.serve()
    finally:
        ws_client.stop()
        watcher.stop()
        await pipeline.stop()
        await jsonl.close()
        try:
            async with asyncio.timeout(15):
                await asyncio.gather(
                    ws_task, watcher_task, initial_sync_task,
                    return_exceptions=True,
                )
        except TimeoutError:
            logger.warning("shutdown timeout — some background tasks killed")

    return EXIT_OK


def main() -> int:
    config_path = os.environ.get("AI_HA_CONFIG", "/data/config.toml")
    data_dir = os.environ.get("AI_HA_DATA_DIR", "/data")
    return asyncio.run(_run(config_path, data_dir))


if __name__ == "__main__":
    sys.exit(main())
