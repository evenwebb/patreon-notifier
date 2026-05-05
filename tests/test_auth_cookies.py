"""Cookie file discovery and JSON formats."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import patreon_notifier.auth as auth


def test_load_cookies_list_format(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    path.write_text(
        '[{"name": "session_id", "value": "abc"}, {"name": "x", "value": "y"}]',
        encoding="utf-8",
    )
    cookies = auth.load_cookies_from_file(str(path))
    assert cookies["session_id"] == "abc"
    assert cookies["x"] == "y"


def test_load_cookies_nested_dict_format(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    path.write_text(
        '{"url": "https://www.patreon.com", '
        '"cookies": [{"name": "session_id", "value": "zzz"}]}',
        encoding="utf-8",
    )
    cookies = auth.load_cookies_from_file(str(path))
    assert cookies["session_id"] == "zzz"


def test_find_cookie_file_prefers_cookies_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    cookies_dir = tmp_path / "cookies"
    cookies_dir.mkdir()
    (cookies_dir / "cookies.json").write_text(
        '[{"name":"session_id","value":"1"}]', encoding="utf-8"
    )
    (cookies_dir / "other.json").write_text("[]", encoding="utf-8")

    minimal_config_ns.COOKIES_DIR = str(cookies_dir)
    minimal_config_ns.COOKIES_FILE = "cookies.json"
    monkeypatch.setattr(auth, "config", minimal_config_ns)

    found = auth.find_cookie_file()
    assert found.endswith("cookies.json")
