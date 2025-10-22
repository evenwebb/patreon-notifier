"""
Notification Services for Patreon Notification Monitor

Handles sending notifications via Apprise - supporting 90+ services:
(Telegram, Discord, Email, Slack, Pushover, Pushbullet, SMS, and more!)
"""

import logging
from typing import Dict, Any, List, Optional

try:
    import apprise
    APPRISE_AVAILABLE = True
except ImportError:
    APPRISE_AVAILABLE = False

import config

logger = logging.getLogger(__name__)


class NotificationService:
    """Base class for notification services."""

    def send(self, title: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Send a notification.

        Args:
            title: Notification title
            message: Notification message
            metadata: Additional metadata about the notification
        """
        raise NotImplementedError


class AppriseNotificationService(NotificationService):
    """
    Apprise notification service - supports 90+ platforms!

    Supported services include:
    - Telegram, Discord, Slack, Microsoft Teams
    - Email (SMTP), Pushover, Pushbullet
    - SMS (Twilio, MessageBird, etc.)
    - And 85+ more!

    Configure services using URLs in config.APPRISE_URLS.
    See: https://github.com/caronc/apprise/wiki
    """

    def __init__(self):
        """Initialize Apprise notification service."""
        if not APPRISE_AVAILABLE:
            logger.warning("Apprise not installed. Install with: pip install apprise")
            self.apobj = None
            return

        self.apobj = apprise.Apprise()

        # Add all configured service URLs
        if hasattr(config, 'APPRISE_URLS') and config.APPRISE_URLS:
            for url in config.APPRISE_URLS:
                if url and url.strip():  # Skip empty URLs
                    self.apobj.add(url)

            logger.info(f"Loaded {len(self.apobj)} Apprise service(s)")
        else:
            logger.info("No Apprise services configured (APPRISE_URLS is empty)")

    def send(self, title: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Send notification via all configured Apprise services."""
        if not self.apobj or len(self.apobj) == 0:
            return  # No services configured

        try:
            # Build the notification body with URL if available
            body = message
            if metadata and metadata.get('url'):
                url = metadata['url']
                body = f"{message}\n\n{url}"

            # Get thumbnail URL if available
            attach = None
            if metadata and metadata.get('thumbnail'):
                attach = metadata['thumbnail']

            # Send to all services
            success = self.apobj.notify(
                title=title,
                body=body,
                attach=attach,
            )

            if success:
                logger.info(f"Apprise notification sent to {len(self.apobj)} service(s)")
            else:
                logger.warning("Some Apprise notifications may have failed")

        except Exception as e:
            logger.error(f"Failed to send Apprise notification: {e}")


class NotificationManager:
    """Manages multiple notification services."""

    def __init__(self):
        """Initialize notification manager with configured services."""
        self.services: List[NotificationService] = []
        self._init_services()

    def _init_services(self) -> None:
        """Initialize enabled notification services."""
        # Apprise (handles all notification services)
        if APPRISE_AVAILABLE and hasattr(config, 'APPRISE_URLS') and config.APPRISE_URLS:
            apprise_service = AppriseNotificationService()
            if apprise_service.apobj and len(apprise_service.apobj) > 0:
                self.services.append(apprise_service)
        elif not APPRISE_AVAILABLE:
            logger.error("Apprise not installed. Install with: pip install apprise")
        elif not hasattr(config, 'APPRISE_URLS') or not config.APPRISE_URLS:
            logger.error("No notification services configured (APPRISE_URLS is empty)")

        if not self.services:
            logger.warning("No notification services enabled! Add service URLs to APPRISE_URLS in config.py")

    def send_notification(self, title: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Send notification via all enabled services.

        Args:
            title: Notification title
            message: Notification message
            metadata: Additional metadata about the notification
        """
        for service in self.services:
            try:
                service.send(title, message, metadata)
            except Exception as e:
                logger.error(f"Error sending notification via {service.__class__.__name__}: {e}")
