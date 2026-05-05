"""Health / failure alerting via Apprise (optional, respects dry-run)."""

from __future__ import annotations

import logging
from datetime import datetime

try:
    import apprise

    APPRISE_AVAILABLE = True
except ImportError:
    APPRISE_AVAILABLE = False

from patreon_notifier.config_loader import config

logger = logging.getLogger(__name__)

ALERT_COOLDOWN_SECONDS = 3600
COOKIE_EXPIRATION_COOLDOWN_SECONDS = 21600


class HealthMonitor:
    """Tracks consecutive failures and sends Apprise alerts with cooldowns."""

    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.enabled = config.HEALTH_MONITORING.get("enabled", True)
        self.alert_on_auth_failure = config.HEALTH_MONITORING.get("alert_on_auth_failure", True)
        self.alert_on_api_errors = config.HEALTH_MONITORING.get("alert_on_api_errors", True)
        self.alert_on_notification_errors = config.HEALTH_MONITORING.get(
            "alert_on_notification_errors", True
        )
        self.max_consecutive_failures = config.HEALTH_MONITORING.get("max_consecutive_failures", 3)

        self.auth_failures = 0
        self.api_failures = 0
        self.notification_failures = 0

        self.last_auth_alert = None
        self.last_api_alert = None
        self.last_notification_alert = None
        self.last_cookie_expiration_alert = None

        self.apobj = None
        if not self.dry_run and self.enabled and APPRISE_AVAILABLE:
            self._init_apprise()

        self._notify_capable = bool(self.apobj and len(self.apobj) > 0)

    def _init_apprise(self) -> None:
        self.apobj = apprise.Apprise()

        health_urls = config.HEALTH_APPRISE_URLS if config.HEALTH_APPRISE_URLS else config.APPRISE_URLS

        if health_urls:
            for url in health_urls:
                if url and url.strip():
                    self.apobj.add(url)

            if len(self.apobj) > 0:
                logger.info("Health monitoring enabled (%s alert service(s))", len(self.apobj))

    def record_auth_success(self) -> None:
        self.auth_failures = 0

    def record_auth_failure(self, error: Exception) -> None:
        if not self.enabled or not self.alert_on_auth_failure:
            return

        self.auth_failures += 1

        if self.auth_failures >= self.max_consecutive_failures:
            self._send_alert(
                "Authentication Failure",
                f"Failed to authenticate with Patreon after {self.auth_failures} attempts.\n\n"
                f"Error: {error!s}\n\n"
                f"Action required: Check your cookie file and ensure it's up to date.",
                "auth",
            )

    def record_cookie_expiration(self, error: Exception) -> None:
        if not self.enabled or not self.alert_on_auth_failure:
            return

        self._send_alert(
            "Cookies Expired",
            f"Your Patreon cookies have expired and need to be refreshed.\n\n"
            f"Error: {error!s}\n\n"
            f"Action required:\n"
            f"1. Open your browser and log into Patreon\n"
            f"2. Use a cookie export extension (Cookie-Editor or EditThisCookie)\n"
            f"3. Export cookies as JSON\n"
            f"4. Save to your cookies file (cookies/cookies.json)\n"
            f"5. Restart the Patreon monitor\n\n"
            f"The monitor will not work until cookies are updated.",
            "cookie_expiration",
        )

    def record_api_success(self) -> None:
        self.api_failures = 0

    def record_api_failure(self, error: Exception) -> None:
        if not self.enabled or not self.alert_on_api_errors:
            return

        self.api_failures += 1

        if self.api_failures >= self.max_consecutive_failures:
            self._send_alert(
                "API Error",
                f"Failed to fetch notifications from Patreon after {self.api_failures} attempts.\n\n"
                f"Error: {error!s}\n\n"
                f"This may be a temporary issue. If it persists, check Patreon's status.",
                "api",
            )

    def record_notification_success(self) -> None:
        self.notification_failures = 0

    def record_notification_failure(self, error: Exception) -> None:
        if not self.enabled or not self.alert_on_notification_errors:
            return

        self.notification_failures += 1

        if self.notification_failures >= self.max_consecutive_failures:
            self._send_alert(
                "Notification Delivery Failure",
                f"Failed to send notifications after {self.notification_failures} attempts.\n\n"
                f"Error: {error!s}\n\n"
                f"Check your notification service configuration in config.py.",
                "notification",
            )

    def _send_alert(self, title: str, message: str, alert_type: str) -> None:
        if self.dry_run:
            logger.debug("dry-run: suppressed health alert %s", title)
            return

        if not self._notify_capable:
            logger.debug("Health alert (no Apprise URLs configured): %s", title)
            return

        now = datetime.now()

        if alert_type == "auth" and self.last_auth_alert:
            if (now - self.last_auth_alert).total_seconds() < ALERT_COOLDOWN_SECONDS:
                return
        elif alert_type == "api" and self.last_api_alert:
            if (now - self.last_api_alert).total_seconds() < ALERT_COOLDOWN_SECONDS:
                return
        elif alert_type == "notification" and self.last_notification_alert:
            if (now - self.last_notification_alert).total_seconds() < ALERT_COOLDOWN_SECONDS:
                return
        elif alert_type == "cookie_expiration" and self.last_cookie_expiration_alert:
            if (now - self.last_cookie_expiration_alert).total_seconds() < COOKIE_EXPIRATION_COOLDOWN_SECONDS:
                return

        try:
            self.apobj.notify(
                title=f"🚨 Patreon Monitor: {title}",
                body=message,
            )

            if alert_type == "auth":
                self.last_auth_alert = now
            elif alert_type == "api":
                self.last_api_alert = now
            elif alert_type == "notification":
                self.last_notification_alert = now
            elif alert_type == "cookie_expiration":
                self.last_cookie_expiration_alert = now

            logger.warning("Health alert sent: %s", title)

        except Exception as e:
            logger.error("Failed to send health alert: %s", e)
