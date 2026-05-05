"""CLI config validation (no live Patreon)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import patreon_notifier.cli as cli


def test_validate_config_passes_with_complete_config(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    monkeypatch.setattr(cli, "config", minimal_config_ns)
    assert cli.validate_config() is True


def test_validate_config_fails_on_bad_check_interval(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    minimal_config_ns.CHECK_INTERVAL = -1
    monkeypatch.setattr(cli, "config", minimal_config_ns)
    assert cli.validate_config() is False


def test_validate_config_fails_on_wrong_apprise_type(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    minimal_config_ns.APPRISE_URLS = "not-a-list"  # type: ignore[assignment]
    monkeypatch.setattr(cli, "config", minimal_config_ns)
    assert cli.validate_config() is False


def test_validate_config_fails_on_missing_key(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    del minimal_config_ns.COOKIES_DIR
    monkeypatch.setattr(cli, "config", minimal_config_ns)
    assert cli.validate_config() is False


def test_validate_config_rejects_non_string_notification_template(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    minimal_config_ns.NOTIFICATION_TITLE_TEMPLATE = 123  # type: ignore[attr-defined]
    monkeypatch.setattr(cli, "config", minimal_config_ns)
    assert cli.validate_config() is False


def test_validate_config_rejects_non_bool_append_url(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    minimal_config_ns.NOTIFICATION_APPEND_URL_TO_BODY = "yes"  # type: ignore[attr-defined]
    monkeypatch.setattr(cli, "config", minimal_config_ns)
    assert cli.validate_config() is False


def test_validate_config_rejects_bad_creator_settings_entry(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    minimal_config_ns.CREATOR_SETTINGS = {"X": "not-a-dict"}  # type: ignore[assignment]
    monkeypatch.setattr(cli, "config", minimal_config_ns)
    assert cli.validate_config() is False


def test_validate_config_rejects_bad_per_creator_template(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    minimal_config_ns.CREATOR_SETTINGS = {
        "Ada": {"notification_title_template": 1}  # type: ignore[dict-item]
    }
    monkeypatch.setattr(cli, "config", minimal_config_ns)
    assert cli.validate_config() is False


def test_test_templates_exits_zero(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    minimal_config_ns.NOTIFICATION_TITLE_TEMPLATE = "{creator}: {subject}"
    minimal_config_ns.NOTIFICATION_BODY_TEMPLATE = "{url}"
    minimal_config_ns.NOTIFICATION_APPEND_URL_TO_BODY = False
    monkeypatch.setattr(cli, "config", minimal_config_ns)
    assert cli.main(["--test-templates"]) == 0


def test_test_templates_invalid_format_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    minimal_config_ns.NOTIFICATION_BODY_TEMPLATE = "{unclosed"
    monkeypatch.setattr(cli, "config", minimal_config_ns)
    assert cli.main(["--test-templates"]) == 1
