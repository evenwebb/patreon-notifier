"""Core Patreon stream polling, parsing, filtering, and notification dispatch."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import requests

from patreon_notifier import auth
from patreon_notifier.config_loader import config
from patreon_notifier.constants import (
    BANNER_WIDTH,
    MESSAGE_MAX_LENGTH,
    PATREON_API_STREAM_URL,
    PATREON_API_VERSION,
    UNKNOWN_CREATOR,
)
from patreon_notifier.health import HealthMonitor
from patreon_notifier.notification_format import (
    format_notification_text,
    resolve_templates_for_creator,
)
from patreon_notifier.notifications import NotificationManager
from patreon_notifier.state import StateManager
from patreon_notifier.types import ParsedNotification

logger = logging.getLogger(__name__)

_CREATOR_NAME_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"posted by (.+?)(?:\s|$)",
        r"^(.+?) posted",
        r"^(.+?) just",
    )
)

_VIDEO_URL_RE = re.compile(
    r"youtube\.com/watch|youtu\.be/|vimeo\.com/|twitch\.tv/",
    re.IGNORECASE,
)

class PatreonNotificationMonitor:
    """Poll Patreon stream, dedupe, filter, notify."""

    def __init__(self, *, dry_run: bool = False, quiet: bool = False) -> None:
        self.dry_run = dry_run
        self.quiet = quiet
        self.session: Optional[requests.Session] = None
        self.csrf_token: Optional[str] = None
        self.user_info: Optional[Dict[str, Any]] = None
        self.state_manager = StateManager()
        self.notification_manager = NotificationManager()
        self.health_monitor = HealthMonitor(dry_run=dry_run)
        self.user_map: Dict[str, str] = {}
        self.campaign_map: Dict[str, str] = {}

    def _user_out(self, message: str) -> None:
        logger.info(message)
        if not self.quiet:
            print(message)

    def _build_included_maps(self, included: List[Dict[str, Any]]) -> None:
        self.user_map.clear()
        self.campaign_map.clear()
        for item in included:
            itype = item.get("type")
            if itype == "user":
                user_id = item["id"]
                attrs = item.get("attributes", {})
                name = attrs.get("full_name") or attrs.get("vanity") or f"User {user_id}"
                self.user_map[user_id] = name

            elif itype == "campaign":
                campaign_id = item["id"]
                attrs = item.get("attributes", {})
                name = attrs.get("creation_name") or f"Campaign {campaign_id}"
                self.campaign_map[campaign_id] = name

    def authenticate(self) -> bool:
        self._user_out("Authenticating with Patreon...")
        try:
            self.session, self.csrf_token, self.user_info = auth.setup_authenticated_session()
            self._user_out(f"✓ Logged in as: {self.user_info['name']}")
            self._user_out(f"  Email: {self.user_info['email']}")
            self._user_out(f"  Active memberships: {self.user_info['pledge_count']}")
            self.health_monitor.record_auth_success()
            return True
        except FileNotFoundError as e:
            logger.error("Cookie file error: %s", e)
            if not self.quiet:
                print(f"\n✗ Error: {e}")
                print("\nPlease export your Patreon cookies using a browser extension:")
                print("  1. Install 'Cookie-Editor' or 'EditThisCookie' extension")
                print("  2. Log into Patreon in your browser")
                print("  3. Export cookies as JSON")
                print(f"  4. Save to {config.COOKIES_DIR}/{config.COOKIES_FILE}")
            self.health_monitor.record_auth_failure(e)
            return False
        except auth.CookieExpiredError as e:
            logger.error("Cookie expiration: %s", e)
            if not self.quiet:
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
            logger.error("Authentication failed: %s", e, exc_info=config.SHOW_FULL_ERRORS)
            if not self.quiet:
                print(f"\n✗ Authentication failed: {e}")
                if config.SHOW_FULL_ERRORS:
                    import traceback

                    traceback.print_exc()
            self.health_monitor.record_auth_failure(e)
            return False

    def _get_json_with_retries(
        self,
        url: str,
        params: Optional[Dict[str, Any]],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        max_retries = max(1, int(getattr(config, "FETCH_MAX_RETRIES", 3)))
        backoff = float(getattr(config, "FETCH_RETRY_BACKOFF_SECONDS", 2.0))
        for attempt in range(max_retries):
            try:
                resp = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=config.REQUEST_TIMEOUT,
                )
                if resp.status_code in (429, 502, 503, 504) and attempt < max_retries - 1:
                    sleep_s = backoff * (attempt + 1)
                    logger.warning(
                        "Stream request %s returned %s; retrying in %.1fs",
                        url,
                        resp.status_code,
                        sleep_s,
                    )
                    time.sleep(sleep_s)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    sleep_s = backoff * (attempt + 1)
                    logger.warning("Stream request failed (%s); retrying in %.1fs", e, sleep_s)
                    time.sleep(sleep_s)
                else:
                    raise
        raise RuntimeError("BUG: stream retry loop exited unexpectedly")

    def fetch_notifications(self) -> List[Dict[str, Any]]:
        try:
            headers = {
                "Accept": "application/json",
                "x-csrf-signature": self.csrf_token,
                "Referer": "https://www.patreon.com/notifications",
            }
            first_params = {
                "json-api-version": PATREON_API_VERSION,
                "include": "user,campaign",
            }
            max_pages = int(getattr(config, "FETCH_MAX_STREAM_PAGES", 10))

            all_notifications: List[Dict[str, Any]] = []
            included_by_key: Dict[tuple[str, str], Dict[str, Any]] = {}
            current_url: Optional[str] = PATREON_API_STREAM_URL
            params: Optional[Dict[str, Any]] = first_params
            pages_fetched = 0

            while current_url and pages_fetched < max_pages:
                payload = self._get_json_with_retries(current_url, params, headers)
                params = None

                batch = payload.get("data", []) or []
                all_notifications.extend(batch)
                for inc in payload.get("included", []) or []:
                    t, rid = inc.get("type"), inc.get("id")
                    if t is not None and rid is not None:
                        included_by_key[(str(t), str(rid))] = inc

                pages_fetched += 1
                next_link = (payload.get("links") or {}).get("next")
                if isinstance(next_link, str) and next_link.strip():
                    current_url = next_link.strip()
                else:
                    current_url = None

            self._build_included_maps(list(included_by_key.values()))
            logger.info(
                "Fetched %s notification(s) across %s stream page(s)",
                len(all_notifications),
                pages_fetched,
            )

            self.health_monitor.record_api_success()
            return all_notifications

        except Exception as e:
            logger.error("Failed to fetch notifications: %s", e, exc_info=config.SHOW_FULL_ERRORS)
            self.health_monitor.record_api_failure(e)
            return []

    def parse_notification(self, notification: Dict[str, Any]) -> ParsedNotification:
        notification_id = notification.get("id")
        notification_type = notification.get("type")
        attributes = notification.get("attributes", {})

        if notification_type == "post":
            title = attributes.get("title", "Untitled")
            content = (
                attributes.get("content")
                or attributes.get("teaser_text")
                or attributes.get("description")
                or ""
            )
            post_type = attributes.get("post_type", "")
            published_at = attributes.get("published_at") or attributes.get("created_at") or ""
            url = (attributes.get("url") or attributes.get("patreon_url") or "") or ""

            thumbnail = None
            post_file = attributes.get("post_file")
            if post_file and isinstance(post_file, dict) and post_file.get("url"):
                thumbnail = post_file["url"]

            creator = UNKNOWN_CREATOR
            relationships = notification.get("relationships", {}) or {}
            campaign_name = self._campaign_name_from_relationships(relationships)

            user_rel = relationships.get("user")
            if isinstance(user_rel, dict):
                user_data = user_rel.get("data") or {}
                user_id = user_data.get("id")
                if user_id and user_id in self.user_map:
                    creator = self.user_map[user_id]

            if creator == UNKNOWN_CREATOR:
                camp_rel = relationships.get("campaign")
                if isinstance(camp_rel, dict):
                    campaign_data = camp_rel.get("data") or {}
                    campaign_id = campaign_data.get("id")
                    if campaign_id and campaign_id in self.campaign_map:
                        creator = self.campaign_map[campaign_id]

            has_video = self._detect_video(post_type, content, attributes)

            if not thumbnail:
                embed = attributes.get("embed")
                if isinstance(embed, dict) and embed.get("image"):
                    thumbnail = embed["image"]

            return cast(
                ParsedNotification,
                {
                    "id": notification_id,
                    "type": notification_type,
                    "post_type": post_type,
                    "subject": title,
                    "body": content[:MESSAGE_MAX_LENGTH] if content else "",
                    "creator": creator,
                    "campaign": campaign_name,
                    "url": url,
                    "thumbnail": thumbnail,
                    "created_at": published_at,
                    "is_new_post": True,
                    "has_video": has_video,
                },
            )

        subject = attributes.get("subject", "")
        body = attributes.get("body", "")
        created_at = attributes.get("created_at", "")
        url = (attributes.get("url") or attributes.get("patreon_url") or "") or ""
        thumbnail = attributes.get("thumbnail_url") or attributes.get("image_url")
        creator = self._extract_creator_name(subject, body)
        has_video = self._detect_video(str(notification_type or ""), body, attributes)
        relationships = notification.get("relationships", {}) or {}
        campaign_name = self._campaign_name_from_relationships(relationships)

        return cast(
            ParsedNotification,
            {
                "id": notification_id,
                "type": notification_type,
                "post_type": "",
                "subject": subject,
                "body": body,
                "creator": creator,
                "campaign": campaign_name,
                "url": url,
                "thumbnail": thumbnail,
                "created_at": created_at,
                "is_new_post": True,
                "has_video": has_video,
            },
        )

    def _campaign_name_from_relationships(self, relationships: Dict[str, Any]) -> str:
        camp_rel = relationships.get("campaign")
        if isinstance(camp_rel, dict):
            campaign_data = camp_rel.get("data") or {}
            campaign_id = campaign_data.get("id")
            if campaign_id and campaign_id in self.campaign_map:
                return self.campaign_map[campaign_id]
        return ""

    def _extract_creator_name(self, subject: str, body: str) -> str:
        for pattern in _CREATOR_NAME_PATTERNS:
            match = pattern.search(subject)
            if match:
                return match.group(1).strip()
            match = pattern.search(body)
            if match:
                return match.group(1).strip()
        return UNKNOWN_CREATOR

    def _detect_video(self, post_type: str, content: str, attributes: Dict[str, Any]) -> bool:
        if post_type and "video" in post_type.lower():
            return True

        embed = attributes.get("embed")
        if isinstance(embed, dict) and embed.get("provider"):
            provider = embed["provider"].lower()
            if any(v in provider for v in ("youtube", "vimeo", "twitch")):
                return True

        if content and _VIDEO_URL_RE.search(content):
            return True

        return False

    def _matches_keyword_filter(self, parsed: ParsedNotification) -> bool:
        creator = parsed["creator"]

        if creator in config.CREATOR_SETTINGS:
            creator_keywords = config.CREATOR_SETTINGS[creator].get("keywords", [])
            if creator_keywords:
                text = f"{parsed['subject']} {parsed['body']}".lower()
                return any(keyword.lower() in text for keyword in creator_keywords)

        if config.GLOBAL_KEYWORDS:
            text = f"{parsed['subject']} {parsed['body']}".lower()
            return any(keyword.lower() in text for keyword in config.GLOBAL_KEYWORDS)

        return True

    def _matches_content_filter(self, parsed: ParsedNotification) -> bool:
        creator = parsed["creator"]
        post_type = parsed.get("post_type", "").lower()
        has_video = parsed.get("has_video", False)

        if creator in config.CREATOR_SETTINGS:
            creator_settings = config.CREATOR_SETTINGS[creator]
            creator_types = creator_settings.get("content_types", [])
            if creator_types:
                for allowed_type in creator_types:
                    if allowed_type.lower() in post_type or (
                        allowed_type == "video_embed" and has_video
                    ):
                        return True
                return False

            if creator_settings.get("video_only", False):
                return has_video

        filters = config.CONTENT_TYPE_FILTERS

        if filters.get("video_only", False):
            return has_video

        if filters.get("image_only", False):
            return "image" in post_type

        if filters.get("text_only", False):
            return not has_video and "image" not in post_type and "audio" not in post_type

        if filters.get("audio_only", False):
            return "audio" in post_type

        if filters.get("exclude_text", False):
            return has_video or "image" in post_type or "audio" in post_type

        return True

    def _matches_creator_filter(self, parsed: ParsedNotification) -> bool:
        creator = parsed["creator"]

        if creator in config.CREATOR_SETTINGS:
            if not config.CREATOR_SETTINGS[creator].get("enabled", True):
                return False

        if config.ENABLED_CREATORS:
            return creator in config.ENABLED_CREATORS

        return True

    def process_notifications(self, notifications: List[Dict[str, Any]]) -> int:
        new_count = 0
        try:
            for notification in notifications:
                parsed = self.parse_notification(notification)
                nid = parsed.get("id")
                if not nid:
                    logger.warning("Skipping stream item without id (type=%s)", parsed.get("type"))
                    continue

                if self.state_manager.is_seen(nid):
                    continue

                if config.ONLY_NEW_POSTS and not parsed["is_new_post"]:
                    self.state_manager.mark_seen(nid, persist=False)
                    continue

                if not self._matches_creator_filter(parsed):
                    self.state_manager.mark_seen(nid, persist=False)
                    logger.debug(
                        "Filtered out (creator): %s - %s", parsed["creator"], parsed["subject"]
                    )
                    continue

                if not self._matches_keyword_filter(parsed):
                    self.state_manager.mark_seen(nid, persist=False)
                    logger.debug(
                        "Filtered out (keyword): %s - %s", parsed["creator"], parsed["subject"]
                    )
                    continue

                if not self._matches_content_filter(parsed):
                    self.state_manager.mark_seen(nid, persist=False)
                    logger.debug(
                        "Filtered out (content type): %s - %s",
                        parsed["creator"],
                        parsed["subject"],
                    )
                    continue

                self._send_notification(parsed)
                self.state_manager.mark_seen(nid, persist=False)
                new_count += 1
        finally:
            self.state_manager.flush()

        return new_count

    def _send_notification(self, notification: ParsedNotification) -> None:
        try:
            title_template = getattr(
                config, "NOTIFICATION_TITLE_TEMPLATE", "New Patreon Post: {creator}"
            )
            body_template = getattr(
                config, "NOTIFICATION_BODY_TEMPLATE", "{subject_or_body}"
            )
            append_url = getattr(config, "NOTIFICATION_APPEND_URL_TO_BODY", True)
            title_template, body_template, append_url = resolve_templates_for_creator(
                notification["creator"],
                title_template=title_template,
                body_template=body_template,
                append_url=append_url,
                creator_settings=getattr(config, "CREATOR_SETTINGS", {}) or {},
            )

            try:
                title, message = format_notification_text(
                    notification,
                    title_template=title_template,
                    body_template=body_template,
                    append_url_if_missing=append_url,
                )
            except ValueError as e:
                logger.error("Invalid NOTIFICATION_*_TEMPLATE: %s", e)
                self.health_monitor.record_notification_failure(e)
                return

            if self.dry_run:
                preview = message.replace("\n", " ")
                if len(preview) > 100:
                    preview = preview[:97] + "..."
                logger.info("dry-run: would send notification — %s — %s", title, preview)
                return

            metadata = {
                "creator": notification["creator"],
                "url": notification["url"],
                "thumbnail": notification["thumbnail"],
                "created_at": notification["created_at"],
            }

            self.notification_manager.send_notification(title, message, metadata)
            self.health_monitor.record_notification_success()

            logger.info(
                "Sent notification - Creator: %s, Subject: %s",
                notification["creator"],
                notification["subject"],
            )
            if notification["url"]:
                logger.debug("URL: %s", notification["url"])

        except Exception as e:
            logger.error("Failed to send notification: %s", e)
            self.health_monitor.record_notification_failure(e)

    def run_once(self) -> None:
        self._user_out("\n" + "=" * BANNER_WIDTH)
        self._user_out("Checking for new notifications...")
        self._user_out("=" * BANNER_WIDTH)

        notifications = self.fetch_notifications()
        if not notifications:
            self._user_out("No notifications found")
            return

        new_count = self.process_notifications(notifications)

        self._user_out("\n" + "=" * BANNER_WIDTH)
        if new_count > 0:
            self._user_out(f"✓ Sent {new_count} new notification(s)")
        else:
            self._user_out("✓ No new notifications")
        self._user_out("=" * BANNER_WIDTH)

    def run_continuous(self) -> None:
        self._user_out("\n" + "=" * BANNER_WIDTH)
        self._user_out(f"Starting continuous monitoring (checking every {config.CHECK_INTERVAL}s)")
        self._user_out("Press Ctrl+C to stop")
        self._user_out("=" * BANNER_WIDTH + "\n")

        try:
            while True:
                notifications = self.fetch_notifications()
                if notifications:
                    new_count = self.process_notifications(notifications)
                    if new_count > 0:
                        msg = (
                            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                            f"Sent {new_count} notification(s)"
                        )
                        self._user_out(msg)
                    else:
                        logger.debug("No new notifications")
                else:
                    logger.warning("Failed to fetch notifications")

                time.sleep(config.CHECK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Stopping monitor (keyboard interrupt)")
            if not self.quiet:
                print("\n\nStopping monitor...")
