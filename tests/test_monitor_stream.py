"""Stream fetch behaviour (mocked HTTP)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from patreon_notifier.monitor import PatreonNotificationMonitor


def _ok_response(payload: dict) -> MagicMock:
    r = MagicMock()
    r.json.return_value = payload
    r.raise_for_status = MagicMock()
    return r


def test_fetch_notifications_follows_links_next(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    monkeypatch.setattr("patreon_notifier.monitor.config", minimal_config_ns)

    post_a = {
        "id": "a",
        "type": "post",
        "attributes": {
            "title": "A",
            "content": "",
            "post_type": "text_only",
            "published_at": "",
            "url": "",
        },
        "relationships": {"user": {"data": {"id": "u1", "type": "user"}}},
    }
    post_b = {
        "id": "b",
        "type": "post",
        "attributes": {
            "title": "B",
            "content": "",
            "post_type": "text_only",
            "published_at": "",
            "url": "",
        },
        "relationships": {"user": {"data": {"id": "u1", "type": "user"}}},
    }
    user_inc = {
        "id": "u1",
        "type": "user",
        "attributes": {"full_name": "Creator One"},
    }

    page1 = {
        "data": [post_a],
        "included": [user_inc],
        "links": {"next": "https://www.patreon.com/api/stream?page=2"},
    }
    page2 = {"data": [post_b], "included": [], "links": {}}

    m = PatreonNotificationMonitor(dry_run=True, quiet=True)
    m.csrf_token = "csrf-test"
    m.session = MagicMock()
    m.session.get.side_effect = [_ok_response(page1), _ok_response(page2)]

    out = m.fetch_notifications()

    assert len(out) == 2
    assert {item["id"] for item in out} == {"a", "b"}
    assert m.session.get.call_count == 2
    second_url = m.session.get.call_args_list[1][0][0]
    assert "page=2" in second_url
