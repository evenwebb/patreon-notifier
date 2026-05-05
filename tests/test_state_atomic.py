import json

from patreon_notifier.state import StateManager


def test_state_save_is_valid_json(tmp_path) -> None:
    state_path = tmp_path / "state.json"
    sm = StateManager(state_file=str(state_path))
    sm.mark_seen("abc-123")
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert "abc-123" in data["seen_ids"]
