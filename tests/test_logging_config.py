"""Rotating file logging setup."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

import patreon_notifier.cli as cli


def test_configure_logging_writes_rotating_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    log_path = tmp_path / "subdir" / "app.log"
    minimal_config_ns.LOG_FILE = str(log_path)
    minimal_config_ns.LOG_MAX_BYTES = 2048
    minimal_config_ns.LOG_BACKUP_COUNT = 3
    minimal_config_ns.VERBOSE = False
    monkeypatch.setattr(cli, "config", minimal_config_ns)

    cli.configure_logging(quiet=False)
    logging.getLogger("patreon_test").info("hello from file")

    assert log_path.is_file()
    assert b"hello from file" in log_path.read_bytes()


def test_validate_config_rejects_bad_log_max_bytes(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    minimal_config_ns.LOG_MAX_BYTES = 0
    monkeypatch.setattr(cli, "config", minimal_config_ns)
    assert cli.validate_config() is False


def test_validate_config_rejects_non_string_log_file(
    monkeypatch: pytest.MonkeyPatch, minimal_config_ns: SimpleNamespace
) -> None:
    minimal_config_ns.LOG_FILE = ["/tmp/x.log"]  # type: ignore[assignment]
    monkeypatch.setattr(cli, "config", minimal_config_ns)
    assert cli.validate_config() is False
