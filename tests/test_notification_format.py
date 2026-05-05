"""Template formatting for Apprise title/body."""

from __future__ import annotations

from typing import cast

from patreon_notifier.notification_format import (
    build_format_context,
    format_notification_text,
    resolve_templates_for_creator,
)
from patreon_notifier.types import ParsedNotification


def _sample_parsed() -> ParsedNotification:
    return ParsedNotification(
        id="1",
        type="post",
        post_type="text_only",
        subject="My title",
        body="First line of body",
        creator="Ada",
        campaign="Ada's Patreon",
        url="https://www.patreon.com/posts/example",
        thumbnail=None,
        created_at="2026-01-02T12:00:00Z",
        is_new_post=True,
        has_video=False,
    )


def test_build_format_context_aliases_and_has_video() -> None:
    ctx = build_format_context(_sample_parsed())
    assert ctx["creator"] == "Ada"
    assert ctx["campaign"] == "Ada's Patreon"
    assert ctx["thumbnail"] == ""
    assert ctx["title"] == ctx["subject"] == "My title"
    assert ctx["description"] == ctx["body"] == "First line of body"
    assert ctx["url"].endswith("example")
    assert ctx["post_type"] == "text_only"
    assert ctx["notification_type"] == "post"
    assert ctx["has_video"] == "false"
    assert ctx["subject_or_body"] == "My title"


def test_unknown_placeholder_becomes_empty() -> None:
    p = _sample_parsed()
    title, body = format_notification_text(
        p,
        title_template="[{typo_here}] {creator}",
        body_template="ok",
        append_url_if_missing=False,
    )
    assert title == "[] Ada"
    assert body == "ok"


def test_append_url_when_missing_from_body() -> None:
    p = _sample_parsed()
    _, body = format_notification_text(
        p,
        title_template="t",
        body_template="Hello",
        append_url_if_missing=True,
    )
    assert body.startswith("Hello\n\n")
    assert p["url"] in body


def test_append_url_skips_when_already_in_body() -> None:
    p = _sample_parsed()
    _, body = format_notification_text(
        p,
        title_template="t",
        body_template="See {url}",
        append_url_if_missing=True,
    )
    assert body.count("patreon.com") == 1


def test_thumbnail_in_context() -> None:
    p = cast(
        ParsedNotification,
        {**dict(_sample_parsed()), "thumbnail": "https://cdn.example/i.jpg"},
    )
    assert build_format_context(p)["thumbnail"] == "https://cdn.example/i.jpg"


def test_resolve_templates_per_creator_overrides() -> None:
    title_t, body_t, append = resolve_templates_for_creator(
        "Ada",
        title_template="GLOBAL",
        body_template="BODY",
        append_url=True,
        creator_settings={
            "Ada": {
                "notification_title_template": "VIP {subject}",
                "notification_append_url_to_body": False,
            }
        },
    )
    assert title_t == "VIP {subject}"
    assert body_t == "BODY"
    assert append is False


def test_subject_or_body_falls_back_to_body() -> None:
    p = cast(ParsedNotification, {**dict(_sample_parsed()), "subject": "", "body": "Only body"})
    _, body = format_notification_text(
        p,
        title_template="{creator}",
        body_template="{subject_or_body}",
        append_url_if_missing=False,
    )
    assert body == "Only body"
