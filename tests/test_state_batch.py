"""State persistence batching."""

from __future__ import annotations

import json

from patreon_notifier.state import StateManager


def test_mark_seen_deferred_then_flush_writes_once(tmp_path) -> None:
    path = tmp_path / "state.json"
    sm = StateManager(state_file=str(path))

    sm.mark_seen("a", persist=False)
    sm.mark_seen("b", persist=False)
    assert not path.exists()
    sm.flush()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data["seen_ids"]) == {"a", "b"}
