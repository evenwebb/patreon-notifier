"""Command-line entry: argument parsing, logging, config validation, run loop."""

from __future__ import annotations

import argparse
import logging
import sys
from importlib.metadata import version
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional, cast

from patreon_notifier.config_loader import config
from patreon_notifier.constants import KEYBOARD_INTERRUPT_EXIT_CODE
from patreon_notifier.monitor import PatreonNotificationMonitor
from patreon_notifier.notification_format import (
    build_format_context,
    format_notification_text,
    resolve_templates_for_creator,
    template_test_sample_parsed,
)
from patreon_notifier.types import ParsedNotification

logger = logging.getLogger(__name__)


def print_banner() -> None:
    print()
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║         Patreon Notification Monitor                              ║")
    print("║         Monitor new posts from your favorite creators             ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print()


def validate_config() -> bool:
    errors: List[str] = []
    warnings: List[str] = []

    required_attrs = [
        "COOKIES_DIR",
        "COOKIES_FILE",
        "CHECK_INTERVAL",
        "APPRISE_URLS",
        "STATE_FILE",
        "STATE_RETENTION_DAYS",
        "REQUEST_TIMEOUT",
        "VERBOSE",
        "SHOW_FULL_ERRORS",
        "USER_AGENT",
        "ACCEPT_LANGUAGE",
        "HEALTH_MONITORING",
        "ENABLED_CREATORS",
        "CREATOR_SETTINGS",
        "GLOBAL_KEYWORDS",
        "CONTENT_TYPE_FILTERS",
        "ONLY_NEW_POSTS",
    ]

    for attr in required_attrs:
        if not hasattr(config, attr):
            errors.append(f"Missing required configuration: {attr}")

    if hasattr(config, "APPRISE_URLS"):
        if not isinstance(config.APPRISE_URLS, list):
            errors.append("APPRISE_URLS must be a list")
        elif len(config.APPRISE_URLS) == 0:
            warnings.append("APPRISE_URLS is empty - no notifications will be sent")

    if hasattr(config, "CHECK_INTERVAL"):
        if not isinstance(config.CHECK_INTERVAL, (int, float)):
            errors.append("CHECK_INTERVAL must be a number")
        elif config.CHECK_INTERVAL < 0:
            errors.append("CHECK_INTERVAL must be >= 0")

    if hasattr(config, "STATE_RETENTION_DAYS"):
        if not isinstance(config.STATE_RETENTION_DAYS, (int, float)):
            errors.append("STATE_RETENTION_DAYS must be a number")
        elif config.STATE_RETENTION_DAYS <= 0:
            errors.append("STATE_RETENTION_DAYS must be > 0")

    if hasattr(config, "REQUEST_TIMEOUT"):
        if not isinstance(config.REQUEST_TIMEOUT, (int, float)):
            errors.append("REQUEST_TIMEOUT must be a number")
        elif config.REQUEST_TIMEOUT <= 0:
            errors.append("REQUEST_TIMEOUT must be > 0")

    if hasattr(config, "HEALTH_MONITORING"):
        if not isinstance(config.HEALTH_MONITORING, dict):
            errors.append("HEALTH_MONITORING must be a dictionary")

    if hasattr(config, "ENABLED_CREATORS"):
        if not isinstance(config.ENABLED_CREATORS, list):
            errors.append("ENABLED_CREATORS must be a list")

    if hasattr(config, "CREATOR_SETTINGS"):
        if not isinstance(config.CREATOR_SETTINGS, dict):
            errors.append("CREATOR_SETTINGS must be a dictionary")
        else:
            for cname, cset in config.CREATOR_SETTINGS.items():
                if not isinstance(cset, dict):
                    errors.append(f"CREATOR_SETTINGS[{cname!r}] must be a dictionary")
                    continue
                for key in ("notification_title_template", "notification_body_template"):
                    if key in cset and not isinstance(cset[key], str):
                        errors.append(
                            f"CREATOR_SETTINGS[{cname!r}][{key!r}] must be a string"
                        )
                if "notification_append_url_to_body" in cset and not isinstance(
                    cset["notification_append_url_to_body"], bool
                ):
                    errors.append(
                        f"CREATOR_SETTINGS[{cname!r}]['notification_append_url_to_body'] "
                        "must be a boolean"
                    )

    if hasattr(config, "LOG_FILE"):
        lf = config.LOG_FILE
        if lf is not None and not isinstance(lf, str):
            errors.append("LOG_FILE must be a string (path or empty for stderr-only)")
    if hasattr(config, "LOG_MAX_BYTES"):
        if not isinstance(config.LOG_MAX_BYTES, (int, float)):
            errors.append("LOG_MAX_BYTES must be a number")
        elif config.LOG_MAX_BYTES <= 0:
            errors.append("LOG_MAX_BYTES must be > 0")
    if hasattr(config, "LOG_BACKUP_COUNT"):
        if not isinstance(config.LOG_BACKUP_COUNT, int):
            errors.append("LOG_BACKUP_COUNT must be an integer")
        elif config.LOG_BACKUP_COUNT < 0:
            errors.append("LOG_BACKUP_COUNT must be >= 0")

    for tmpl_name in ("NOTIFICATION_TITLE_TEMPLATE", "NOTIFICATION_BODY_TEMPLATE"):
        if hasattr(config, tmpl_name):
            val = getattr(config, tmpl_name)
            if not isinstance(val, str):
                errors.append(f"{tmpl_name} must be a string (Python format with {{placeholders}})")
    if hasattr(config, "NOTIFICATION_APPEND_URL_TO_BODY"):
        if not isinstance(config.NOTIFICATION_APPEND_URL_TO_BODY, bool):
            errors.append("NOTIFICATION_APPEND_URL_TO_BODY must be a boolean")

    if errors:
        print("\n✗ Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        return False

    if warnings:
        print("\n⚠️  Configuration warnings:")
        for warning in warnings:
            print(f"  - {warning}")

    return True


def run_test_templates() -> int:
    """Print sample placeholder values and formatted title/body (no Patreon request)."""
    sample = template_test_sample_parsed()
    title_default = getattr(config, "NOTIFICATION_TITLE_TEMPLATE", "New Patreon Post: {creator}")
    body_default = getattr(config, "NOTIFICATION_BODY_TEMPLATE", "{subject_or_body}")
    append_default = getattr(config, "NOTIFICATION_APPEND_URL_TO_BODY", True)

    print("Template test (--test-templates)\n")
    print("Sample fields (placeholders):")
    for key, val in sorted(build_format_context(sample).items()):
        print(f"  {key}: {val}")
    print()

    try:
        title, body = format_notification_text(
            sample,
            title_template=title_default,
            body_template=body_default,
            append_url_if_missing=append_default,
        )
    except ValueError as e:
        print(f"✗ Invalid template: {e}")
        return 1

    print("Global templates (formatted):")
    print(f"  Title: {title}")
    print(f"  Body:  {body}")
    print()

    creator_settings = getattr(config, "CREATOR_SETTINGS", {}) or {}
    overrides = [
        (name, s)
        for name, s in creator_settings.items()
        if isinstance(s, dict)
        and any(
            k in s
            for k in (
                "notification_title_template",
                "notification_body_template",
                "notification_append_url_to_body",
            )
        )
    ]
    if overrides:
        print("Per-creator overrides (sample creator name swapped to match each key):")
        for cname, _ in sorted(overrides):
            tt, bt, ap = resolve_templates_for_creator(
                cname,
                title_template=title_default,
                body_template=body_default,
                append_url=append_default,
                creator_settings=creator_settings,
            )
            sample_c = dict(sample)
            sample_c["creator"] = cname
            try:
                t2, b2 = format_notification_text(
                    cast(ParsedNotification, sample_c),
                    title_template=tt,
                    body_template=bt,
                    append_url_if_missing=ap,
                )
            except ValueError as e:
                print(f"  ✗ {cname!r}: {e}")
                return 1
            print(f"  [{cname}] Title: {t2}")
            print(f"  [{cname}] Body:  {b2}")
        print()

    print("✓ Templates parsed successfully.")
    return 0


def configure_logging(*, quiet: bool = False) -> None:
    if quiet:
        log_level = logging.WARNING
    elif config.VERBOSE:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(log_level)

    stderr_h = logging.StreamHandler(sys.stderr)
    stderr_h.setFormatter(formatter)
    stderr_h.setLevel(log_level)
    root.addHandler(stderr_h)

    log_file = (getattr(config, "LOG_FILE", None) or "").strip()
    if log_file:
        max_bytes = int(getattr(config, "LOG_MAX_BYTES", 10 * 1024 * 1024))
        backup_count = int(getattr(config, "LOG_BACKUP_COUNT", 5))
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_h = RotatingFileHandler(
            path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_h.setFormatter(formatter)
        file_h.setLevel(log_level)
        root.addHandler(file_h)


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor Patreon and send notifications via Apprise.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (overrides config.VERBOSE).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single check then exit (overrides config.CHECK_INTERVAL).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not send notifications or health alerts via Apprise.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Less console output; log warnings and errors only (unless --verbose).",
    )
    parser.add_argument(
        "--test-templates",
        action="store_true",
        help="Validate notification templates with sample data and exit (no Patreon).",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show notification statistics and exit.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)

    if getattr(args, "verbose", False):
        config.VERBOSE = True
    if getattr(args, "once", False):
        config.CHECK_INTERVAL = 0
    if getattr(args, "quiet", False) and getattr(args, "verbose", False):
        quiet_log = False
    else:
        quiet_log = getattr(args, "quiet", False)

    if not validate_config():
        print("\nPlease fix the configuration errors in config.py and try again.")
        return 1

    if getattr(args, "version", False):
        try:
            print(f"patreon-notifier {version('patreon-notifier')}")
        except Exception:
            print("patreon-notifier (unknown version)")
        return 0

    if getattr(args, "stats", False):
        from patreon_notifier.state import StateManager
        sm = StateManager()
        print(f"\n=== Patreon Notifier Statistics ===")
        print(f"Seen notifications: {len(sm.seen_ids)}")
        print(f"Tracked timestamps: {len(sm.seen_timestamps)}")
        return 0

    if getattr(args, "test_templates", False):
        configure_logging(quiet=True)
        return run_test_templates()

    configure_logging(quiet=quiet_log)
    if not getattr(args, "quiet", False):
        print_banner()

    monitor = PatreonNotificationMonitor(
        dry_run=getattr(args, "dry_run", False),
        quiet=getattr(args, "quiet", False),
    )

    if not monitor.authenticate():
        return 1

    if not getattr(args, "quiet", False):
        print()

    if config.CHECK_INTERVAL > 0:
        monitor.run_continuous()
    else:
        monitor.run_once()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
        sys.exit(KEYBOARD_INTERRUPT_EXIT_CODE)
    except Exception as e:
        logger.critical("Unexpected error: %s", e, exc_info=config.SHOW_FULL_ERRORS)
        print(f"\n\n✗ Unexpected error: {e}")
        sys.exit(1)
