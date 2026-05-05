"""Shared pytest fixtures."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture
def minimal_config_ns() -> SimpleNamespace:
    """Minimal valid config object for unit tests (no Patreon network)."""
    return SimpleNamespace(
        COOKIES_DIR="cookies",
        COOKIES_FILE="cookies.json",
        CHECK_INTERVAL=300,
        ONLY_NEW_POSTS=True,
        APPRISE_URLS=[],
        ENABLED_CREATORS=[],
        CREATOR_SETTINGS={},
        GLOBAL_KEYWORDS=[],
        CONTENT_TYPE_FILTERS={
            "video_only": False,
            "image_only": False,
            "text_only": False,
            "audio_only": False,
            "exclude_text": False,
        },
        HEALTH_MONITORING={
            "enabled": True,
            "alert_on_auth_failure": True,
            "alert_on_api_errors": True,
            "alert_on_notification_errors": True,
            "max_consecutive_failures": 3,
        },
        HEALTH_APPRISE_URLS=[],
        STATE_FILE="notification_state.json",
        STATE_RETENTION_DAYS=30,
        REQUEST_TIMEOUT=30,
        FETCH_MAX_RETRIES=3,
        FETCH_RETRY_BACKOFF_SECONDS=2.0,
        FETCH_MAX_STREAM_PAGES=10,
        VERBOSE=False,
        SHOW_FULL_ERRORS=False,
        LOG_FILE="",
        LOG_MAX_BYTES=10 * 1024 * 1024,
        LOG_BACKUP_COUNT=5,
        USER_AGENT="Mozilla/5.0 (test)",
        ACCEPT_LANGUAGE="en-GB,en;q=0.9",
    )
