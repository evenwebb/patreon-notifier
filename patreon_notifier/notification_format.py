"""Build Apprise title/body from config templates and parsed stream items."""

from __future__ import annotations

from typing import Any, Mapping

from patreon_notifier.constants import (
    MESSAGE_MAX_LENGTH,
    MESSAGE_TRUNCATE_SUFFIX,
    TITLE_MAX_LENGTH,
)
from patreon_notifier.types import ParsedNotification


class _SafeFormat(dict):
    """Missing `{placeholder}` keys format as empty strings."""

    def __missing__(self, key: str) -> str:
        return ""


def build_format_context(parsed: ParsedNotification) -> dict[str, str]:
    subject = (parsed.get("subject") or "").strip()
    body = (parsed.get("body") or "").strip()
    url = (parsed.get("url") or "").strip()
    creator = (parsed.get("creator") or "").strip()
    post_type = (parsed.get("post_type") or "").strip()
    created_at = (parsed.get("created_at") or "").strip()
    ntype = (parsed.get("type") or "").strip()
    has_video = bool(parsed.get("has_video", False))
    thumb = parsed.get("thumbnail")
    thumbnail = (thumb if isinstance(thumb, str) else "") or ""
    campaign = (parsed.get("campaign") or "").strip()

    return {
        "creator": creator,
        "subject": subject,
        "body": body,
        "title": subject,
        "description": body,
        "url": url,
        "post_type": post_type,
        "created_at": created_at,
        "notification_type": ntype,
        "has_video": "true" if has_video else "false",
        "subject_or_body": subject or body,
        "thumbnail": thumbnail,
        "campaign": campaign,
    }


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= len(MESSAGE_TRUNCATE_SUFFIX):
        return text[:max_len]
    return text[: max_len - len(MESSAGE_TRUNCATE_SUFFIX)] + MESSAGE_TRUNCATE_SUFFIX


def format_notification_text(
    parsed: ParsedNotification,
    *,
    title_template: str,
    body_template: str,
    append_url_if_missing: bool,
    body_max_length: int = MESSAGE_MAX_LENGTH,
    title_max_length: int = TITLE_MAX_LENGTH,
) -> tuple[str, str]:
    """Return (title, body) for Apprise. Unknown placeholders become empty strings."""
    ctx = _SafeFormat(build_format_context(parsed))
    title = title_template.format_map(ctx)
    body = body_template.format_map(ctx)

    url = ctx["url"]
    if append_url_if_missing and url and url not in body:
        sep = "\n\n" if body else ""
        body = f"{body}{sep}{url}"

    return _truncate(title.strip(), title_max_length), _truncate(body, body_max_length)


def resolve_templates_for_creator(
    creator: str,
    *,
    title_template: str,
    body_template: str,
    append_url: bool,
    creator_settings: Mapping[str, Any] | None,
) -> tuple[str, str, bool]:
    """Apply per-creator overrides from CREATOR_SETTINGS (if any)."""
    raw = None
    if isinstance(creator_settings, Mapping):
        raw = creator_settings.get(creator)
    cs = raw if isinstance(raw, dict) else {}

    title_t = title_template
    if "notification_title_template" in cs:
        title_t = cs["notification_title_template"]
    body_t = body_template
    if "notification_body_template" in cs:
        body_t = cs["notification_body_template"]
    append = append_url
    if "notification_append_url_to_body" in cs:
        append = bool(cs["notification_append_url_to_body"])
    return title_t, body_t, append


def template_test_sample_parsed() -> ParsedNotification:
    """Synthetic notification for ``--test-templates`` (no Patreon call)."""
    return ParsedNotification(
        id="template-test",
        type="post",
        post_type="video_embed",
        subject="Sample post title",
        body="Sample teaser or description text.",
        creator="Sample Creator",
        campaign="Sample Campaign",
        url="https://www.patreon.com/posts/template-test-example",
        thumbnail="https://example.com/thumb.jpg",
        created_at="2026-05-05T12:00:00Z",
        is_new_post=True,
        has_video=True,
    )
