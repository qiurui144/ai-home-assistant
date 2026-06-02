from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_ha.health import HealthMetrics
from ai_ha.store.dao import StoreDAO
from ai_ha.topology import EntityIndex, SnapshotStore


@dataclass
class AppState:
    dao: StoreDAO
    snapshot_store: SnapshotStore
    entity_index: EntityIndex
    health: HealthMetrics
    config_path: Path
    hide_pattern: list[str]
    on_privacy_update: Any  # async callable
    broadcaster: Any | None = None  # set by main.py / Task 21
