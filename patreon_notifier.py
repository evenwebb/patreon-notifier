#!/usr/bin/env python3
"""
Patreon Notification Monitor

Monitors Patreon for new posts from subscribed creators and sends notifications.
"""

import sys
import os
import time
import json
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests

import config
import auth
from state_manager import StateManager
from notification_services import NotificationManager
from health_monitor import HealthMonitor

# Configure logging
logger = logging.getLogger(__name__)

# Constants
UNKNOWN_CREATOR = "Unknown Creator"
MESSAGE_MAX_LENGTH = 200
MESSAGE_TRUNCATE_SUFFIX = "..."
BANNER_WIDTH = 70
KEYBOARD_INTERRUPT_EXIT_CODE = 130
PATREON_API_STREAM_URL = "https://www.patreon.com/api/stream"
PATREON_API_VERSION = "1.0"


class PatreonNotificationMonitor:
    """Monitors Patreon notifications and sends alerts for new posts."""

    def __init__(self):
        """Initialize the notification monitor."""
        self.session: Optional[requests.Session] = None
        self.csrf_token: Optional[str] = None
        self.user_info: Optional[Dict[str, Any]] = None
        self.state_manager = StateManager()
        self.notification_manager = NotificationManager()
        self.health_monitor = HealthMonitor()
        self.user_map: Dict[str, str] = {}  # Map user IDs to names
        self.campaign_map: Dict[str, str] = {}  # Map campaign IDs to names

    def _build_included_maps(self, included: List[Dict[str, Any]]) -> None:
        """Build maps of user and campaign data from included array."""
        for item in included:
            if item['type'] == 'user':
                user_id = item['id']
                attrs = item.get('attributes', {})
                name = attrs.get('full_name') or attrs.get('vanity') or f"User {user_id}"
                self.user_map[user_id] = name

            elif item['type'] == 'campaign':
                campaign_id = item['id']
                attrs = item.get('attributes', {})
                name = attrs.get('creation_name') or f"Campaign {campaign_id}"
                self.campaign_map[campaign_id] = name

    def authenticate(self) -> bool:
        """Authenticate with Patreon using cookies."""
        print("Authenticating with Patreon...")
        try:
            self.session, self.csrf_token, self.user_info = auth.setup_authenticated_session()
            print(f"✓ Logged in as: {self.user_info['name']}")
            print(f"  Email: {self.user_info['email']}")
            print(f"  Active memberships: {self.user_info['pledge_count']}")
            self.health_monitor.record_auth_success()
            return True
        except FileNotFoundError as e:
            print(f"\n✗ Error: {e}")
            print("\nPlease export your Patreon cookies using a browser extension:")
            print("  1. Install 'Cookie-Editor' or 'EditThisCookie' extension")
            print("  2. Log into Patreon in your browser")
            print("  3. Export cookies as JSON")
            print(f"  4. Save to {config.COOKIES_DIR}/{config.COOKIES_FILE}")
            self.health_monitor.record_auth_failure(e)
            return False
        except auth.CookieExpiredError as e:
            print(f"\n✗ Cookie Expiration Error: {e}")
            print("\nYour cookies have expired. To fix this:")
            print("  1. Open your browser and log into Patreon")
            print("  2. Use a cookie export extension (Cookie-Editor or EditThisCookie)")
            print("  3. Export cookies as JSON")
            print(f"  4. Save to {config.COOKIES_DIR}/{config.COOKIES_FILE}")
            print("  5. Restart the monitor")
            self.health_monitor.record_cookie_expiration(e)
            return False
        except Exception as e:
            print(f"\n✗ Authentication failed: {e}")
            if config.SHOW_FULL_ERRORS:
                import traceback
                traceback.print_exc()
            self.health_monitor.record_auth_failure(e)
            return False

    def fetch_notifications(self) -> List[Dict[str, Any]]:
        """
        Fetch notifications from Patreon API.

        Returns:
            List of notification dictionaries (posts from creators you follow)
        """
        try:
            # Fetch from Patreon stream API (this shows posts from creators you follow)
            url = PATREON_API_STREAM_URL
            params = {
                'json-api-version': PATREON_API_VERSION,
                'include': 'user,campaign',  # Include user and campaign data
            }

            headers = {
                'Accept': 'application/json',
                'x-csrf-signature': self.csrf_token,
                'Referer': 'https://www.patreon.com/notifications'
            }

            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=config.REQUEST_TIMEOUT
            )
            response.raise_for_status()

            data = response.json()
            notifications = data.get('data', [])

            # Build maps for user and campaign data
            self._build_included_maps(data.get('included', []))

            logger.info(f"Fetched {len(notifications)} notification(s)")

            self.health_monitor.record_api_success()
            return notifications

        except Exception as e:
            logger.error(f"Failed to fetch notifications: {e}", exc_info=config.SHOW_FULL_ERRORS)
            self.health_monitor.record_api_failure(e)
            return []

    def parse_notification(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a notification object (post) into a standardized format.

        Args:
            notification: Raw post data from stream API

        Returns:
            Parsed notification dictionary
        """
        notification_id = notification.get('id')
        notification_type = notification.get('type')
        attributes = notification.get('attributes', {})

        # For posts from the stream
        if notification_type == 'post':
            title = attributes.get('title', 'Untitled')
            content = attributes.get('content', '')
            post_type = attributes.get('post_type', '')
            published_at = attributes.get('published_at', '')
            url = attributes.get('url', '')

            # Extract thumbnail from post_file or embed
            thumbnail = None
            if 'post_file' in attributes:
                post_file = attributes['post_file']
                if post_file and 'url' in post_file:
                    thumbnail = post_file['url']

            # Get creator from relationships
            creator = "Unknown Creator"
            relationships = notification.get('relationships', {})

            # Try user relationship first
            if 'user' in relationships:
                user_data = relationships['user'].get('data', {})
                user_id = user_data.get('id')
                if user_id and user_id in self.user_map:
                    creator = self.user_map[user_id]

            # Try campaign relationship if user not found
            if creator == "Unknown Creator" and 'campaign' in relationships:
                campaign_data = relationships['campaign'].get('data', {})
                campaign_id = campaign_data.get('id')
                if campaign_id and campaign_id in self.campaign_map:
                    creator = self.campaign_map[campaign_id]

            # Detect if post contains video
            has_video = self._detect_video(post_type, content, attributes)

            # Try to get better thumbnail from embed if available
            if not thumbnail and 'embed' in attributes:
                embed = attributes['embed']
                if embed and 'image' in embed:
                    thumbnail = embed['image']

            return {
                'id': notification_id,
                'type': notification_type,
                'post_type': post_type,
                'subject': title,
                'body': content[:MESSAGE_MAX_LENGTH] if content else '',  # First N chars
                'creator': creator,
                'url': url,
                'thumbnail': thumbnail,
                'created_at': published_at,
                'is_new_post': True,  # All stream items are posts
                'has_video': has_video,
            }

        # Fallback for other notification types
        subject = attributes.get('subject', '')
        body = attributes.get('body', '')
        created_at = attributes.get('created_at', '')
        url = attributes.get('url', '')
        thumbnail = attributes.get('thumbnail_url') or attributes.get('image_url')
        creator = self._extract_creator_name(subject, body)
        has_video = self._detect_video(notification_type, body, attributes)

        return {
            'id': notification_id,
            'type': notification_type,
            'post_type': '',
            'subject': subject,
            'body': body,
            'creator': creator,
            'url': url,
            'thumbnail': thumbnail,
            'created_at': created_at,
            'is_new_post': True,
            'has_video': has_video,
        }

    def _extract_creator_from_post(self, attributes: Dict[str, Any]) -> str:
        """Extract creator name from post attributes."""
        # Try various fields that might contain creator info
        title = attributes.get('title', '')

        # Some posts might have creator info in metadata
        # For now, return a generic identifier
        return "Creator"

    def _extract_creator_name(self, subject: str, body: str) -> str:
        """Extract creator name from notification subject/body."""
        # Try to find "posted by CREATOR" or "CREATOR posted" patterns
        patterns = [
            r'posted by (.+?)(?:\s|$)',
            r'^(.+?) posted',
            r'^(.+?) just',
        ]

        for pattern in patterns:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                return match.group(1).strip()

            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return UNKNOWN_CREATOR

    def _is_new_post_notification(self, notification_type: str, subject: str, body: str) -> bool:
        """
        Check if a notification is for a new post.

        Args:
            notification_type: Type of notification
            subject: Notification subject
            body: Notification body

        Returns:
            True if this is a new post notification
        """
        # Check notification type first
        if notification_type and 'post' in notification_type.lower():
            return True

        # Check subject and body for post-related keywords
        keywords = ['posted', 'new post', 'published', 'just published']
        text = f"{subject} {body}".lower()

        return any(keyword in text for keyword in keywords)

    def _detect_video(self, post_type: str, content: str, attributes: Dict[str, Any]) -> bool:
        """
        Detect if a post contains video content.

        Args:
            post_type: Type of post
            content: Post content (may contain URLs)
            attributes: Post attributes

        Returns:
            True if post contains video
        """
        # Check post_type
        if post_type and 'video' in post_type.lower():
            return True

        # Check for video embed
        if 'embed' in attributes:
            embed = attributes['embed']
            if embed and 'provider' in embed:
                provider = embed['provider'].lower()
                if any(vid_provider in provider for vid_provider in ['youtube', 'vimeo', 'twitch']):
                    return True

        # Check content for video URLs
        if content:
            video_patterns = [
                r'youtube\.com/watch',
                r'youtu\.be/',
                r'vimeo\.com/',
                r'twitch\.tv/',
            ]
            for pattern in video_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return True

        return False

    def _matches_keyword_filter(self, parsed: Dict[str, Any]) -> bool:
        """
        Check if notification matches keyword filters.

        Args:
            parsed: Parsed notification

        Returns:
            True if notification matches keyword filters (or no filters set)
        """
        creator = parsed['creator']

        # Check per-creator keywords first
        if creator in config.CREATOR_SETTINGS:
            creator_keywords = config.CREATOR_SETTINGS[creator].get('keywords', [])
            if creator_keywords:
                # Must match at least one creator-specific keyword
                text = f"{parsed['subject']} {parsed['body']}".lower()
                return any(keyword.lower() in text for keyword in creator_keywords)

        # Check global keywords
        if config.GLOBAL_KEYWORDS:
            text = f"{parsed['subject']} {parsed['body']}".lower()
            return any(keyword.lower() in text for keyword in config.GLOBAL_KEYWORDS)

        # No keywords configured, pass
        return True

    def _matches_content_filter(self, parsed: Dict[str, Any]) -> bool:
        """
        Check if notification matches content type filters.

        Args:
            parsed: Parsed notification

        Returns:
            True if notification matches content filters
        """
        creator = parsed['creator']
        post_type = parsed.get('post_type', '').lower()
        has_video = parsed.get('has_video', False)

        # Check per-creator content type filter first
        if creator in config.CREATOR_SETTINGS:
            creator_types = config.CREATOR_SETTINGS[creator].get('content_types', [])
            if creator_types:
                # Must match one of the allowed types for this creator
                for allowed_type in creator_types:
                    if allowed_type.lower() in post_type or \
                       (allowed_type == 'video_embed' and has_video):
                        return True
                return False  # Didn't match any allowed type

            # Check per-creator video_only flag
            if config.CREATOR_SETTINGS[creator].get('video_only', False):
                return has_video

        # Check global content type filters
        filters = config.CONTENT_TYPE_FILTERS

        if filters.get('video_only', False):
            return has_video

        if filters.get('image_only', False):
            return 'image' in post_type

        if filters.get('text_only', False):
            return not has_video and 'image' not in post_type and 'audio' not in post_type

        if filters.get('audio_only', False):
            return 'audio' in post_type

        if filters.get('exclude_text', False):
            # Exclude text-only posts (must have media)
            return has_video or 'image' in post_type or 'audio' in post_type

        # No content filters active, pass
        return True

    def _matches_creator_filter(self, parsed: Dict[str, Any]) -> bool:
        """
        Check if notification matches creator whitelist.

        Args:
            parsed: Parsed notification

        Returns:
            True if notification passes creator filter
        """
        creator = parsed['creator']

        # Check if creator is explicitly disabled in settings
        if creator in config.CREATOR_SETTINGS:
            if not config.CREATOR_SETTINGS[creator].get('enabled', True):
                return False

        # Check whitelist (empty = all creators allowed)
        if config.ENABLED_CREATORS:
            return creator in config.ENABLED_CREATORS

        return True

    def process_notifications(self, notifications: List[Dict[str, Any]]) -> int:
        """
        Process notifications and send alerts for new unseen posts.

        Args:
            notifications: List of raw notification dictionaries

        Returns:
            Number of new notifications sent
        """
        new_count = 0

        for notification in notifications:
            parsed = self.parse_notification(notification)

            # Skip if already seen
            if self.state_manager.is_seen(parsed['id']):
                continue

            # Filter for new posts only if configured
            if config.ONLY_NEW_POSTS and not parsed['is_new_post']:
                self.state_manager.mark_seen(parsed['id'])
                continue

            # Apply creator filter
            if not self._matches_creator_filter(parsed):
                self.state_manager.mark_seen(parsed['id'])
                logger.debug(f"Filtered out (creator): {parsed['creator']} - {parsed['subject']}")
                continue

            # Apply keyword filter
            if not self._matches_keyword_filter(parsed):
                self.state_manager.mark_seen(parsed['id'])
                logger.debug(f"Filtered out (keyword): {parsed['creator']} - {parsed['subject']}")
                continue

            # Apply content type filter
            if not self._matches_content_filter(parsed):
                self.state_manager.mark_seen(parsed['id'])
                logger.debug(f"Filtered out (content type): {parsed['creator']} - {parsed['subject']}")
                continue

            # Send notification
            self._send_notification(parsed)
            self.state_manager.mark_seen(parsed['id'])
            new_count += 1

        return new_count

    def _send_notification(self, notification: Dict[str, Any]) -> None:
        """
        Send a notification via configured services.

        Args:
            notification: Parsed notification dictionary
        """
        try:
            # Format title and message
            title = f"New Patreon Post: {notification['creator']}"
            message = notification['subject'] or notification['body']

            # Truncate message if too long
            if len(message) > MESSAGE_MAX_LENGTH:
                message = message[:MESSAGE_MAX_LENGTH - len(MESSAGE_TRUNCATE_SUFFIX)] + MESSAGE_TRUNCATE_SUFFIX

            # Prepare metadata
            metadata = {
                'creator': notification['creator'],
                'url': notification['url'],
                'thumbnail': notification['thumbnail'],
                'created_at': notification['created_at']
            }

            # Send via notification manager
            self.notification_manager.send_notification(title, message, metadata)
            self.health_monitor.record_notification_success()

            logger.info(f"Sent notification - Creator: {notification['creator']}, Subject: {notification['subject']}")
            if notification['url']:
                logger.debug(f"URL: {notification['url']}")

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            self.health_monitor.record_notification_failure(e)

    def run_once(self) -> None:
        """Run the monitor once and exit."""
        print("\n" + "=" * BANNER_WIDTH)
        print("Checking for new notifications...")
        print("=" * BANNER_WIDTH)

        notifications = self.fetch_notifications()
        if not notifications:
            print("No notifications found")
            return

        new_count = self.process_notifications(notifications)

        print("\n" + "=" * BANNER_WIDTH)
        if new_count > 0:
            print(f"✓ Sent {new_count} new notification(s)")
        else:
            print("✓ No new notifications")
        print("=" * BANNER_WIDTH)

    def run_continuous(self) -> None:
        """Run the monitor continuously."""
        print("\n" + "=" * BANNER_WIDTH)
        print(f"Starting continuous monitoring (checking every {config.CHECK_INTERVAL}s)")
        print("Press Ctrl+C to stop")
        print("=" * BANNER_WIDTH + "\n")

        try:
            while True:
                notifications = self.fetch_notifications()
                if notifications:
                    new_count = self.process_notifications(notifications)
                    if new_count > 0:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sent {new_count} notification(s)")
                    else:
                        logger.debug(f"No new notifications")
                else:
                    logger.warning("Failed to fetch notifications")

                time.sleep(config.CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n\nStopping monitor...")


def print_banner() -> None:
    """Print startup banner."""
    print()
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║         Patreon Notification Monitor                              ║")
    print("║         Monitor new posts from your favorite creators             ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print()


def validate_config() -> bool:
    """
    Validate configuration settings.

    Returns:
        True if configuration is valid, False otherwise
    """
    errors = []
    warnings = []

    # Check required attributes
    required_attrs = [
        'COOKIES_DIR', 'COOKIES_FILE', 'CHECK_INTERVAL', 'APPRISE_URLS',
        'STATE_FILE', 'STATE_RETENTION_DAYS', 'REQUEST_TIMEOUT',
        'VERBOSE', 'SHOW_FULL_ERRORS', 'USER_AGENT', 'ACCEPT_LANGUAGE',
        'HEALTH_MONITORING', 'ENABLED_CREATORS', 'CREATOR_SETTINGS',
        'GLOBAL_KEYWORDS', 'CONTENT_TYPE_FILTERS', 'ONLY_NEW_POSTS'
    ]

    for attr in required_attrs:
        if not hasattr(config, attr):
            errors.append(f"Missing required configuration: {attr}")

    # Validate types and values
    if hasattr(config, 'APPRISE_URLS'):
        if not isinstance(config.APPRISE_URLS, list):
            errors.append("APPRISE_URLS must be a list")
        elif len(config.APPRISE_URLS) == 0:
            warnings.append("APPRISE_URLS is empty - no notifications will be sent")

    if hasattr(config, 'CHECK_INTERVAL'):
        if not isinstance(config.CHECK_INTERVAL, (int, float)):
            errors.append("CHECK_INTERVAL must be a number")
        elif config.CHECK_INTERVAL < 0:
            errors.append("CHECK_INTERVAL must be >= 0")

    if hasattr(config, 'STATE_RETENTION_DAYS'):
        if not isinstance(config.STATE_RETENTION_DAYS, (int, float)):
            errors.append("STATE_RETENTION_DAYS must be a number")
        elif config.STATE_RETENTION_DAYS <= 0:
            errors.append("STATE_RETENTION_DAYS must be > 0")

    if hasattr(config, 'REQUEST_TIMEOUT'):
        if not isinstance(config.REQUEST_TIMEOUT, (int, float)):
            errors.append("REQUEST_TIMEOUT must be a number")
        elif config.REQUEST_TIMEOUT <= 0:
            errors.append("REQUEST_TIMEOUT must be > 0")

    if hasattr(config, 'HEALTH_MONITORING'):
        if not isinstance(config.HEALTH_MONITORING, dict):
            errors.append("HEALTH_MONITORING must be a dictionary")

    if hasattr(config, 'ENABLED_CREATORS'):
        if not isinstance(config.ENABLED_CREATORS, list):
            errors.append("ENABLED_CREATORS must be a list")

    if hasattr(config, 'CREATOR_SETTINGS'):
        if not isinstance(config.CREATOR_SETTINGS, dict):
            errors.append("CREATOR_SETTINGS must be a dictionary")

    # Print results
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


def configure_logging() -> None:
    """Configure logging based on config settings."""
    log_level = logging.DEBUG if config.VERBOSE else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main() -> int:
    """Main entry point."""
    configure_logging()
    print_banner()

    # Validate configuration
    if not validate_config():
        print("\nPlease fix the configuration errors in config.py and try again.")
        return 1

    # Initialize monitor
    monitor = PatreonNotificationMonitor()

    # Authenticate
    if not monitor.authenticate():
        return 1

    print()

    # Run based on configuration
    if config.CHECK_INTERVAL > 0:
        monitor.run_continuous()
    else:
        monitor.run_once()

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
        sys.exit(KEYBOARD_INTERRUPT_EXIT_CODE)
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=config.SHOW_FULL_ERRORS)
        print(f"\n\n✗ Unexpected error: {e}")
        sys.exit(1)
