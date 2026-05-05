"""Notification processing: filters and dry-run (no Apprise)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from patreon_notifier.monitor import PatreonNotificationMonitor


def _minimal_post(
    post_id: str,
    *,
    user_id: str = "u1",
    title: str = "Hi",
    content: str = "Body",
) -> dict:
    return {
        "id": post_id,
        "type": "post",
        "attributes": {
            "title": title,
            "content": content,
            "post_type": "text_only",
            "published_at": "2026-01-01T00:00:00Z",
            "url": "https://www.patreon.com/posts/x",
        },
        "relationships": {"user": {"data": {"id": user_id, "type": "user"}}},
    }


def test_creator_whitelist_skips_unknown_creator(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace, tmp_path
) -> None:
    minimal_config_ns.ENABLED_CREATORS = ["Alice"]
    minimal_config_ns.STATE_FILE = str(tmp_path / "st.json")
    monkeypatch.setattr("patreon_notifier.monitor.config", minimal_config_ns)
    monkeypatch.setattr("patreon_notifier.state.config", minimal_config_ns)

    m = PatreonNotificationMonitor(dry_run=False, quiet=True)
    m.notification_manager.send_notification = MagicMock()
    m._build_included_maps(
        [{"id": "u1", "type": "user", "attributes": {"full_name": "Bob"}}]
    )

    n = m.process_notifications([_minimal_post("p1")])
    assert n == 0
    m.notification_manager.send_notification.assert_not_called()
    assert m.state_manager.is_seen("p1")


def test_dry_run_does_not_call_notification_manager(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace, tmp_path
) -> None:
    minimal_config_ns.STATE_FILE = str(tmp_path / "st.json")
    monkeypatch.setattr("patreon_notifier.monitor.config", minimal_config_ns)
    monkeypatch.setattr("patreon_notifier.state.config", minimal_config_ns)

    m = PatreonNotificationMonitor(dry_run=True, quiet=True)
    m.notification_manager.send_notification = MagicMock()
    m._build_included_maps(
        [{"id": "u1", "type": "user", "attributes": {"full_name": "Alice"}}]
    )

    n = m.process_notifications([_minimal_post("p2")])
    assert n == 1
    m.notification_manager.send_notification.assert_not_called()


def test_global_keyword_filter_marks_filtered(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace, tmp_path
) -> None:
    minimal_config_ns.GLOBAL_KEYWORDS = ["announcement"]
    minimal_config_ns.STATE_FILE = str(tmp_path / "st.json")
    monkeypatch.setattr("patreon_notifier.monitor.config", minimal_config_ns)
    monkeypatch.setattr("patreon_notifier.state.config", minimal_config_ns)

    m = PatreonNotificationMonitor(dry_run=True, quiet=True)
    m._build_included_maps(
        [{"id": "u1", "type": "user", "attributes": {"full_name": "Alice"}}]
    )

    n = m.process_notifications([_minimal_post("p3", title="Hello", content="nothing special")])
    assert n == 0
    assert m.state_manager.is_seen("p3")
