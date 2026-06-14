"""Typed structures for parsed notifications and creator info."""

from __future__ import annotations

from typing import TypedDict


class ParsedNotification(TypedDict, total=False):
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


class CreatorInfo(TypedDict):
    """Creator information from Patreon API."""

    name: str
    vanity: str
    campaign_id: str | None
    url: str


class UserInfo(TypedDict):
    """Authenticated user information."""

    user_id: str
    name: str
    email: str
    pledge_count: int
