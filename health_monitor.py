"""
Health Monitor for Patreon Notification Monitor

Tracks script health and sends alerts when failures occur.
"""

import logging
from datetime import datetime
from typing import Optional

try:
    import apprise
    APPRISE_AVAILABLE = True
except ImportError:
    APPRISE_AVAILABLE = False

import config

logger = logging.getLogger(__name__)

# Constants
ALERT_COOLDOWN_SECONDS = 3600  # 1 hour
COOKIE_EXPIRATION_COOLDOWN_SECONDS = 21600  # 6 hours


class HealthMonitor:
    """Monitors script health and sends alerts on failures."""

    def __init__(self):
        """Initialize health monitor."""
        self.enabled = config.HEALTH_MONITORING.get('enabled', True)
        self.alert_on_auth_failure = config.HEALTH_MONITORING.get('alert_on_auth_failure', True)
        self.alert_on_api_errors = config.HEALTH_MONITORING.get('alert_on_api_errors', True)
        self.alert_on_notification_errors = config.HEALTH_MONITORING.get('alert_on_notification_errors', True)
        self.max_consecutive_failures = config.HEALTH_MONITORING.get('max_consecutive_failures', 3)

        # Failure counters
        self.auth_failures = 0
        self.api_failures = 0
        self.notification_failures = 0

        # Last alert timestamps (to avoid spam)
        self.last_auth_alert = None
        self.last_api_alert = None
        self.last_notification_alert = None
        self.last_cookie_expiration_alert = None

        # Initialize Apprise for health alerts
        self.apobj = None
        if self.enabled and APPRISE_AVAILABLE:
            self._init_apprise()

    def _init_apprise(self) -> None:
        """Initialize Apprise with health alert URLs."""
        self.apobj = apprise.Apprise()

        # Use dedicated health URLs if configured, otherwise use main URLs
        health_urls = config.HEALTH_APPRISE_URLS if config.HEALTH_APPRISE_URLS else config.APPRISE_URLS

        if health_urls:
            for url in health_urls:
                if url and url.strip():
                    self.apobj.add(url)

            if len(self.apobj) > 0:
                logger.info(f"Health monitoring enabled ({len(self.apobj)} alert service(s))")

    def record_auth_success(self) -> None:
        """Record successful authentication."""
        self.auth_failures = 0

    def record_auth_failure(self, error: Exception) -> None:
        """Record authentication failure."""
        if not self.enabled or not self.alert_on_auth_failure:
            return

        self.auth_failures += 1

        if self.auth_failures >= self.max_consecutive_failures:
            self._send_alert(
                "Authentication Failure",
                f"Failed to authenticate with Patreon after {self.auth_failures} attempts.\n\n"
                f"Error: {str(error)}\n\n"
                f"Action required: Check your cookie file and ensure it's up to date.",
                'auth'
            )

    def record_cookie_expiration(self, error: Exception) -> None:
        """
        Record cookie expiration and send immediate alert.

        Unlike other failures, cookie expiration triggers an immediate alert
        (not waiting for consecutive failures) since it requires user action.

        Args:
            error: The CookieExpiredError exception
        """
        if not self.enabled or not self.alert_on_auth_failure:
            return

        # Send immediate alert for cookie expiration
        self._send_alert(
            "Cookies Expired",
            f"Your Patreon cookies have expired and need to be refreshed.\n\n"
            f"Error: {str(error)}\n\n"
            f"Action required:\n"
            f"1. Open your browser and log into Patreon\n"
            f"2. Use a cookie export extension (Cookie-Editor or EditThisCookie)\n"
            f"3. Export cookies as JSON\n"
            f"4. Save to your cookies file (cookies/cookies.json)\n"
            f"5. Restart the Patreon monitor\n\n"
            f"The monitor will not work until cookies are updated.",
            'cookie_expiration'
        )

    def record_api_success(self) -> None:
        """Record successful API request."""
        self.api_failures = 0

    def record_api_failure(self, error: Exception) -> None:
        """Record API request failure."""
        if not self.enabled or not self.alert_on_api_errors:
            return

        self.api_failures += 1

        if self.api_failures >= self.max_consecutive_failures:
            self._send_alert(
                "API Error",
                f"Failed to fetch notifications from Patreon after {self.api_failures} attempts.\n\n"
                f"Error: {str(error)}\n\n"
                f"This may be a temporary issue. If it persists, check Patreon's status.",
                'api'
            )

    def record_notification_success(self) -> None:
        """Record successful notification delivery."""
        self.notification_failures = 0

    def record_notification_failure(self, error: Exception) -> None:
        """Record notification delivery failure."""
        if not self.enabled or not self.alert_on_notification_errors:
            return

        self.notification_failures += 1

        if self.notification_failures >= self.max_consecutive_failures:
            self._send_alert(
                "Notification Delivery Failure",
                f"Failed to send notifications after {self.notification_failures} attempts.\n\n"
                f"Error: {str(error)}\n\n"
                f"Check your notification service configuration in config.py.",
                'notification'
            )

    def _send_alert(self, title: str, message: str, alert_type: str) -> None:
        """
        Send health alert notification.

        Args:
            title: Alert title
            message: Alert message
            alert_type: Type of alert ('auth', 'api', 'notification', 'cookie_expiration')
        """
        # Check if we've recently sent this type of alert (avoid spam)
        now = datetime.now()

        if alert_type == 'auth' and self.last_auth_alert:
            if (now - self.last_auth_alert).total_seconds() < ALERT_COOLDOWN_SECONDS:
                return
        elif alert_type == 'api' and self.last_api_alert:
            if (now - self.last_api_alert).total_seconds() < ALERT_COOLDOWN_SECONDS:
                return
        elif alert_type == 'notification' and self.last_notification_alert:
            if (now - self.last_notification_alert).total_seconds() < ALERT_COOLDOWN_SECONDS:
                return
        elif alert_type == 'cookie_expiration' and self.last_cookie_expiration_alert:
            if (now - self.last_cookie_expiration_alert).total_seconds() < COOKIE_EXPIRATION_COOLDOWN_SECONDS:
                return

        # Send alert via Apprise
        if self.apobj and len(self.apobj) > 0:
            try:
                self.apobj.notify(
                    title=f"🚨 Patreon Monitor: {title}",
                    body=message,
                )

                # Update last alert timestamp
                if alert_type == 'auth':
                    self.last_auth_alert = now
                elif alert_type == 'api':
                    self.last_api_alert = now
                elif alert_type == 'notification':
                    self.last_notification_alert = now
                elif alert_type == 'cookie_expiration':
                    self.last_cookie_expiration_alert = now

                logger.warning(f"Health alert sent: {title}")

            except Exception as e:
                logger.error(f"Failed to send health alert: {e}")
        else:
            # No alert services configured, just log
            logger.warning(f"HEALTH ALERT: {title} - {message}")
