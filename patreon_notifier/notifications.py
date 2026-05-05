"""Apprise-backed notification delivery."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    import apprise

    APPRISE_AVAILABLE = True
except ImportError:
    APPRISE_AVAILABLE = False

from patreon_notifier.config_loader import config

logger = logging.getLogger(__name__)


class NotificationService:
    def send(self, title: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        raise NotImplementedError


class AppriseNotificationService(NotificationService):
    """Send via all configured Apprise URLs."""

    def __init__(self) -> None:
        if not APPRISE_AVAILABLE:
            logger.warning("Apprise not installed. Install with: pip install apprise")
            self.apobj = None
            return

        self.apobj = apprise.Apprise()

        if getattr(config, "APPRISE_URLS", None):
            for url in config.APPRISE_URLS:
                if url and url.strip():
                    self.apobj.add(url)

            logger.info("Loaded %s Apprise service(s)", len(self.apobj))
        else:
            logger.info("No Apprise services configured (APPRISE_URLS is empty)")

    def send(self, title: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        if not self.apobj or len(self.apobj) == 0:
            return

        try:
            attach = metadata.get("thumbnail") if metadata else None

            success = self.apobj.notify(title=title, body=message, attach=attach)

            if success:
                logger.info("Apprise notification sent to %s service(s)", len(self.apobj))
            else:
                logger.warning("Some Apprise notifications may have failed")

        except Exception as e:
            logger.error("Failed to send Apprise notification: %s", e)


class NotificationManager:
    """Dispatches to all enabled backends."""

    def __init__(self) -> None:
        self.services: List[NotificationService] = []
        self._init_services()

    def _init_services(self) -> None:
        if APPRISE_AVAILABLE and getattr(config, "APPRISE_URLS", None):
            apprise_service = AppriseNotificationService()
            if apprise_service.apobj and len(apprise_service.apobj) > 0:
                self.services.append(apprise_service)
        elif not APPRISE_AVAILABLE:
            logger.error("Apprise not installed. Install with: pip install apprise")
        elif not getattr(config, "APPRISE_URLS", None):
            logger.error("No notification services configured (APPRISE_URLS is empty)")

        if not self.services:
            logger.warning(
                "No notification services enabled! Add service URLs to APPRISE_URLS in config.py"
            )

    def send_notification(
        self, title: str, message: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        for service in self.services:
            try:
                service.send(title, message, metadata)
            except Exception as e:
                logger.error("Error sending notification via %s: %s", type(service).__name__, e)
