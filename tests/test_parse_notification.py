import json
from pathlib import Path

from patreon_notifier.monitor import PatreonNotificationMonitor


def test_parse_post_uses_patreon_url_and_maps_creator() -> None:
    fixture = Path(__file__).parent / "fixtures" / "stream_one_page.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))

    mon = PatreonNotificationMonitor(dry_run=True, quiet=True)
    mon._build_included_maps(payload.get("included", []))

    raw = payload["data"][0]
    parsed = mon.parse_notification(raw)

    assert parsed["creator"] == "Fixture Creator"
    assert parsed["campaign"] == "Fixture Campaign"
    assert "patreon.com/posts/post-1-only-patreon-url" in parsed["url"]
    assert parsed["subject"] == "Hello"
    assert "Teaser" in parsed["body"] or "body" in parsed["body"].lower()
