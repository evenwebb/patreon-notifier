"""Typed structures for parsed notifications."""

from __future__ import annotations

from typing import TypedDict


class ParsedNotification(TypedDict):
    """Normalized notification used by filtering and Apprise delivery."""

    id: str | None
    type: str | None
    post_type: str
    subject: str
    body: str
    creator: str
    campaign: str
    url: str
    thumbnail: str | None
    created_at: str
    is_new_post: bool
    has_video: bool
