from __future__ import annotations

import json
import logging
from pathlib import Path

from src.config import settings
from src.models import Snapshot

logger = logging.getLogger(__name__)


def load_snapshot() -> Snapshot:
    path = Path(settings.snapshot_path)
    if not path.exists():
        logger.info("No snapshot found at %s, starting fresh", path)
        return Snapshot()
    try:
        data = json.loads(path.read_text())
        return Snapshot(
            assignment_ids={int(k): v for k, v in data.get("assignment_ids", {}).items()},
            quiz_ids={int(k): v for k, v in data.get("quiz_ids", {}).items()},
            announcement_ids={int(k): v for k, v in data.get("announcement_ids", {}).items()},
            module_ids={int(k): v for k, v in data.get("module_ids", {}).items()},
        )
    except Exception as e:
        logger.warning("Failed to load snapshot: %s, starting fresh", e)
        return Snapshot()


def save_snapshot(snapshot: Snapshot) -> None:
    path = Path(settings.snapshot_path)
    data = {
        "assignment_ids": {str(k): v for k, v in snapshot.assignment_ids.items()},
        "quiz_ids": {str(k): v for k, v in snapshot.quiz_ids.items()},
        "announcement_ids": {str(k): v for k, v in snapshot.announcement_ids.items()},
        "module_ids": {str(k): v for k, v in snapshot.module_ids.items()},
    }
    path.write_text(json.dumps(data, indent=2))
    logger.info("Snapshot saved to %s", path)
