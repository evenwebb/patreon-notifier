"""
Health Monitor for Patreon Notification Monitor

Tracks script health and sends alerts when failures occur.
"""

from datetime import datetime
from typing import Optional

try:
    import apprise
    APPRISE_AVAILABLE = True
except ImportError:
    APPRISE_AVAILABLE = False

import config


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

        # Initialize Apprise for health alerts
        self.apobj = None
        if self.enabled and APPRISE_AVAILABLE:
            self._init_apprise()

    def _init_apprise(self):
        """Initialize Apprise with health alert URLs."""
        self.apobj = apprise.Apprise()

        # Use dedicated health URLs if configured, otherwise use main URLs
        health_urls = config.HEALTH_APPRISE_URLS if config.HEALTH_APPRISE_URLS else config.APPRISE_URLS

        if health_urls:
            for url in health_urls:
                if url and url.strip():
                    self.apobj.add(url)

            if config.VERBOSE and len(self.apobj) > 0:
                print(f"✓ Health monitoring enabled ({len(self.apobj)} alert service(s))")

    def record_auth_success(self):
        """Record successful authentication."""
        self.auth_failures = 0

    def record_auth_failure(self, error: Exception):
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

    def record_api_success(self):
        """Record successful API request."""
        self.api_failures = 0

    def record_api_failure(self, error: Exception):
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

    def record_notification_success(self):
        """Record successful notification delivery."""
        self.notification_failures = 0

    def record_notification_failure(self, error: Exception):
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

    def _send_alert(self, title: str, message: str, alert_type: str):
        """
        Send health alert notification.

        Args:
            title: Alert title
            message: Alert message
            alert_type: Type of alert ('auth', 'api', 'notification')
        """
        # Check if we've recently sent this type of alert (avoid spam)
        now = datetime.now()

        if alert_type == 'auth' and self.last_auth_alert:
            if (now - self.last_auth_alert).total_seconds() < 3600:  # 1 hour cooldown
                return
        elif alert_type == 'api' and self.last_api_alert:
            if (now - self.last_api_alert).total_seconds() < 3600:
                return
        elif alert_type == 'notification' and self.last_notification_alert:
            if (now - self.last_notification_alert).total_seconds() < 3600:
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

                if config.VERBOSE:
                    print(f"⚠️  Health alert sent: {title}")

            except Exception as e:
                print(f"Failed to send health alert: {e}")
        else:
            # No alert services configured, just log
            print(f"⚠️  HEALTH ALERT: {title}")
            print(f"    {message}")
