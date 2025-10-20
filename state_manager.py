"""
State Manager for Patreon Notification Monitor

Tracks which notifications have been seen to avoid duplicate notifications.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Set, List
from pathlib import Path

import config


class StateManager:
    """Manages the state of seen notifications."""

    def __init__(self, state_file: str = None):
        """
        Initialize state manager.

        Args:
            state_file: Path to state file (uses config.STATE_FILE if None)
        """
        self.state_file = state_file or config.STATE_FILE
        self.seen_ids: Set[str] = set()
        self.seen_timestamps: dict = {}
        self._load_state()

    def _load_state(self):
        """Load state from file."""
        if not os.path.exists(self.state_file):
            return

        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                self.seen_ids = set(data.get('seen_ids', []))
                self.seen_timestamps = data.get('timestamps', {})

            # Prune old entries
            self._prune_old_entries()

        except Exception as e:
            print(f"Warning: Could not load state file: {e}")
            self.seen_ids = set()
            self.seen_timestamps = {}

    def _save_state(self):
        """Save state to file."""
        try:
            data = {
                'seen_ids': list(self.seen_ids),
                'timestamps': self.seen_timestamps,
                'last_updated': datetime.now().isoformat()
            }

            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            print(f"Warning: Could not save state file: {e}")

    def _prune_old_entries(self):
        """Remove entries older than STATE_RETENTION_DAYS."""
        cutoff = datetime.now() - timedelta(days=config.STATE_RETENTION_DAYS)
        cutoff_iso = cutoff.isoformat()

        # Find IDs to remove
        ids_to_remove = []
        for notification_id, timestamp in self.seen_timestamps.items():
            if timestamp < cutoff_iso:
                ids_to_remove.append(notification_id)

        # Remove old entries
        for notification_id in ids_to_remove:
            self.seen_ids.discard(notification_id)
            del self.seen_timestamps[notification_id]

        if ids_to_remove and config.VERBOSE:
            print(f"Pruned {len(ids_to_remove)} old notification(s) from state")

    def is_seen(self, notification_id: str) -> bool:
        """
        Check if a notification has been seen.

        Args:
            notification_id: Notification ID to check

        Returns:
            True if seen, False otherwise
        """
        return notification_id in self.seen_ids

    def mark_seen(self, notification_id: str):
        """
        Mark a notification as seen.

        Args:
            notification_id: Notification ID to mark as seen
        """
        self.seen_ids.add(notification_id)
        self.seen_timestamps[notification_id] = datetime.now().isoformat()
        self._save_state()

    def mark_multiple_seen(self, notification_ids: List[str]):
        """
        Mark multiple notifications as seen.

        Args:
            notification_ids: List of notification IDs to mark as seen
        """
        timestamp = datetime.now().isoformat()
        for notification_id in notification_ids:
            self.seen_ids.add(notification_id)
            self.seen_timestamps[notification_id] = timestamp
        self._save_state()

    def get_unseen_count(self) -> int:
        """Get the number of seen notifications."""
        return len(self.seen_ids)

    def clear_state(self):
        """Clear all state (for testing or reset)."""
        self.seen_ids = set()
        self.seen_timestamps = {}
        self._save_state()
