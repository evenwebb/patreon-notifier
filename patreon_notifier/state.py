"""Persistent seen-notification state (JSON, atomic replace on save)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from patreon_notifier.config_loader import config

logger = logging.getLogger(__name__)


class StateManager:
    """Tracks notification IDs already handled."""

    def __init__(self, state_file: Optional[str] = None) -> None:
        self.state_file = state_file or config.STATE_FILE
        self.seen_ids: Set[str] = set()
        self.seen_timestamps: Dict[str, str] = {}
        self._dirty = False
        self._load_state()

    def _load_state(self) -> None:
        if not os.path.exists(self.state_file):
            return

        try:
            with open(self.state_file, encoding="utf-8") as f:
                data = json.load(f)
                self.seen_ids = set(data.get("seen_ids", []))
                self.seen_timestamps = data.get("timestamps", {})

            self._prune_old_entries()

        except Exception as e:
            logger.warning("Could not load state file: %s", e)
            self.seen_ids = set()
            self.seen_timestamps = {}

    def _save_state(self) -> None:
        try:
            data = {
                "seen_ids": list(self.seen_ids),
                "timestamps": self.seen_timestamps,
                "last_updated": datetime.now().isoformat(),
            }

            target_dir = os.path.dirname(os.path.abspath(self.state_file)) or "."
            fd, tmp_path = tempfile.mkstemp(
                prefix=".notification_state_",
                suffix=".tmp",
                dir=target_dir,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                os.replace(tmp_path, self.state_file)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

        except Exception as e:
            logger.warning("Could not save state file: %s", e)

    def _prune_old_entries(self) -> None:
        cutoff = datetime.now() - timedelta(days=config.STATE_RETENTION_DAYS)
        cutoff_iso = cutoff.isoformat()

        ids_to_remove = [nid for nid, ts in self.seen_timestamps.items() if ts < cutoff_iso]

        for notification_id in ids_to_remove:
            self.seen_ids.discard(notification_id)
            del self.seen_timestamps[notification_id]

        if ids_to_remove:
            logger.debug("Pruned %s old notification(s) from state", len(ids_to_remove))
            self._save_state()

    def is_seen(self, notification_id: str) -> bool:
        return notification_id in self.seen_ids

    def mark_seen(self, notification_id: str, *, persist: bool = True) -> None:
        self.seen_ids.add(notification_id)
        self.seen_timestamps[notification_id] = datetime.now().isoformat()
        if persist:
            self._save_state()
            self._dirty = False
        else:
            self._dirty = True

    def flush(self) -> None:
        """Write pending ``mark_seen(..., persist=False)`` updates."""
        if self._dirty:
            self._save_state()
            self._dirty = False

    def mark_multiple_seen(self, notification_ids: List[str]) -> None:
        timestamp = datetime.now().isoformat()
        for notification_id in notification_ids:
            self.seen_ids.add(notification_id)
            self.seen_timestamps[notification_id] = timestamp
        self._save_state()
        self._dirty = False

    def clear_state(self) -> None:
        self.seen_ids = set()
        self.seen_timestamps = {}
        self._save_state()
        self._dirty = False
