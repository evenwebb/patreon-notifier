"""
Patreon cookie authentication: load exported browser cookies and build a session.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

from patreon_notifier.config_loader import config

logger = logging.getLogger(__name__)

PATREON_DOMAIN = ".patreon.com"
PATREON_HOME_URL = "https://www.patreon.com/home"
PATREON_REFERER_URL = "https://www.patreon.com/"


class CookieExpiredError(Exception):
    """Raised when Patreon cookies have expired and need to be refreshed."""


def find_cookie_file() -> str:
    """
    Resolve the cookie JSON path.

    Priority:
    1. ``{COOKIES_DIR}/{COOKIES_FILE}`` if it exists
    2. Sole ``*.json`` under ``COOKIES_DIR``
    3. Error if none or ambiguous
    """
    cookies_dir = Path(config.COOKIES_DIR)

    if not cookies_dir.exists():
        cookies_dir.mkdir(parents=True, exist_ok=True)
        raise FileNotFoundError(
            f"No cookie files found. Please export your Patreon cookies and save to "
            f"'{cookies_dir}/cookies.json'"
        )

    default_path = cookies_dir / config.COOKIES_FILE
    if default_path.exists():
        return str(default_path)

    json_files = list(cookies_dir.glob("*.json"))

    if len(json_files) == 0:
        raise FileNotFoundError(
            f"No JSON files found in '{cookies_dir}/' directory.\n"
            f"Please export your Patreon cookies and save to '{cookies_dir}/cookies.json'"
        )
    if len(json_files) == 1:
        return str(json_files[0])

    file_list = "\n  - ".join(f.name for f in json_files)
    raise ValueError(
        f"Multiple JSON files found in '{cookies_dir}/':\n  - {file_list}\n\n"
        f"Please rename one to 'cookies.json' or remove the extras."
    )


def load_cookies_from_file(cookies_path: Optional[str] = None) -> Dict[str, str]:
    """Load name→value cookie map from a browser-export JSON file."""
    if cookies_path is None:
        cookies_path = config.COOKIES_FILE

    with open(cookies_path, encoding="utf-8") as f:
        cookie_data = json.load(f)

    if isinstance(cookie_data, dict) and "cookies" in cookie_data:
        cookies_list = cookie_data["cookies"]
    elif isinstance(cookie_data, list):
        cookies_list = cookie_data
    else:
        raise ValueError("Unsupported cookie file format")

    return {c["name"]: c["value"] for c in cookies_list}


def create_authenticated_session(cookies: Dict[str, str]) -> requests.Session:
    """Attach Patreon cookies and default browser-like headers."""
    session = requests.Session()

    for name, value in cookies.items():
        session.cookies.set(name, value, domain=PATREON_DOMAIN)

    session.headers.update(
        {
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": config.ACCEPT_LANGUAGE,
            "Referer": PATREON_REFERER_URL,
        }
    )

    return session


def extract_csrf_token(session: requests.Session) -> str:
    """Parse CSRF signature from ``/home`` ``__NEXT_DATA__``."""
    response = session.get(PATREON_HOME_URL)
    response.raise_for_status()

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
        response.text,
        re.DOTALL,
    )

    if not match:
        raise CookieExpiredError(
            "Could not authenticate with Patreon - your cookies appear to have expired. "
            "Please export fresh cookies from your browser and update your cookie file."
        )

    data = json.loads(match.group(1))
    bootstrap = data.get("props", {}).get("pageProps", {}).get("bootstrapEnvelope", {})

    csrf = bootstrap.get("csrfSignature") or bootstrap.get("session", {}).get("csrf_signature")

    if not csrf:
        raise CookieExpiredError(
            "Could not extract CSRF token - your cookies appear to have expired. "
            "Please export fresh cookies from your browser and update your cookie file."
        )

    return str(csrf)


def validate_authentication(session: requests.Session, csrf_token: str) -> Dict[str, Any]:
    """Read current user from ``/home`` ``__NEXT_DATA__``."""
    _ = csrf_token  # API symmetry with callers; second fetch uses the same session.
    response = session.get(PATREON_HOME_URL)
    response.raise_for_status()

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
        response.text,
        re.DOTALL,
    )

    if not match:
        raise CookieExpiredError(
            "Could not load user data - your cookies appear to have expired. "
            "Please export fresh cookies from your browser and update your cookie file."
        )

    data = json.loads(match.group(1))
    bootstrap = data.get("props", {}).get("pageProps", {}).get("bootstrapEnvelope", {})

    user_id = bootstrap.get("userId") or bootstrap.get("session", {}).get("user_id")

    if not user_id:
        raise CookieExpiredError(
            "No user ID found - your cookies appear to have expired. "
            "Please export fresh cookies from your browser and update your cookie file."
        )

    common = bootstrap.get("commonBootstrap", {})
    user = common.get("currentUser", {}).get("data", {})
    attrs = user.get("attributes", {})
    pledges = user.get("relationships", {}).get("pledges", {}).get("data", [])

    return {
        "user_id": str(user_id),
        "name": attrs.get("full_name", "Unknown"),
        "email": attrs.get("email", "Unknown"),
        "pledge_count": len(pledges),
    }


def setup_authenticated_session(
    cookies_path: Optional[str] = None,
) -> Tuple[requests.Session, str, Dict[str, Any]]:
    """Load cookies, validate session, return ``(session, csrf_token, user_info)``."""
    if cookies_path is None:
        cookies_path = find_cookie_file()

    cookies = load_cookies_from_file(cookies_path)

    if "session_id" not in cookies:
        raise ValueError(
            "Missing required 'session_id' cookie - please export cookies from your browser"
        )

    session = create_authenticated_session(cookies)
    csrf_token = extract_csrf_token(session)
    user_info = validate_authentication(session, csrf_token)

    session.headers.update({"x-csrf-signature": csrf_token})

    return session, csrf_token, user_info
