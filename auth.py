"""
Patreon Cookie Authentication Module

Handles loading cookies from JSON file and creating an authenticated session.
"""

import json
import os
import re
import requests
from pathlib import Path
from typing import Tuple, Optional

import config


def find_cookie_file() -> str:
    """
    Find the cookie file using smart detection.

    Priority order:
    1. Check for cookies/cookies.json - if exists, use it (even if other .json files exist)
    2. If not found, look for any other .json files in cookies/ directory
       - If exactly 1 .json file found: use it
       - If 0 files: raise FileNotFoundError
       - If 2+ files: raise ValueError with helpful message

    Returns:
        Path to cookie file

    Raises:
        FileNotFoundError: If no cookie files found
        ValueError: If multiple cookie files found and none named cookies.json
    """
    cookies_dir = Path(config.COOKIES_DIR)

    # Create cookies directory if it doesn't exist
    if not cookies_dir.exists():
        cookies_dir.mkdir(parents=True, exist_ok=True)
        raise FileNotFoundError(
            f"No cookie files found. Please export your Patreon cookies and save to '{cookies_dir}/cookies.json'"
        )

    # Priority 1: Check for cookies.json
    default_path = cookies_dir / config.COOKIES_FILE
    if default_path.exists():
        return str(default_path)

    # Priority 2: Look for any .json files
    json_files = list(cookies_dir.glob('*.json'))

    if len(json_files) == 0:
        raise FileNotFoundError(
            f"No JSON files found in '{cookies_dir}/' directory.\n"
            f"Please export your Patreon cookies and save to '{cookies_dir}/cookies.json'"
        )
    elif len(json_files) == 1:
        return str(json_files[0])
    else:
        # Multiple files found
        file_list = '\n  - '.join([f.name for f in json_files])
        raise ValueError(
            f"Multiple JSON files found in '{cookies_dir}/':\n  - {file_list}\n\n"
            f"Please rename one to 'cookies.json' or remove the extras."
        )


def load_cookies_from_file(cookies_path: str = None) -> dict:
    """
    Load cookies from a JSON file exported from a browser extension.

    Args:
        cookies_path: Path to the cookies JSON file (uses config.COOKIES_FILE if None)

    Returns:
        Dictionary of cookie name->value pairs

    Raises:
        FileNotFoundError: If cookie file doesn't exist
        json.JSONDecodeError: If cookie file is invalid JSON
    """
    if cookies_path is None:
        cookies_path = config.COOKIES_FILE

    with open(cookies_path, 'r') as f:
        cookie_data = json.load(f)

    # Handle different cookie export formats
    if isinstance(cookie_data, dict) and 'cookies' in cookie_data:
        # Format: {"url": "...", "cookies": [...]}
        cookies_list = cookie_data['cookies']
    elif isinstance(cookie_data, list):
        # Format: [{"name": "...", "value": "..."}]
        cookies_list = cookie_data
    else:
        raise ValueError("Unsupported cookie file format")

    # Convert to simple dict
    cookies = {}
    for cookie in cookies_list:
        cookies[cookie['name']] = cookie['value']

    return cookies


def create_authenticated_session(cookies: dict) -> requests.Session:
    """
    Create a requests session with Patreon cookies.

    Args:
        cookies: Dictionary of cookie name->value pairs

    Returns:
        Authenticated requests.Session object
    """
    session = requests.Session()

    # Add cookies to session
    for name, value in cookies.items():
        session.cookies.set(name, value, domain='.patreon.com')

    # Set default headers
    session.headers.update({
        'User-Agent': config.USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': config.ACCEPT_LANGUAGE,
        'Referer': 'https://www.patreon.com/'
    })

    return session


def extract_csrf_token(session: requests.Session) -> str:
    """
    Extract CSRF token from Patreon home page.

    Args:
        session: Authenticated requests session

    Returns:
        CSRF signature token

    Raises:
        ValueError: If CSRF token cannot be extracted
    """
    response = session.get('https://www.patreon.com/home')
    response.raise_for_status()

    # Extract __NEXT_DATA__ JSON
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        response.text,
        re.DOTALL
    )

    if not match:
        raise ValueError("Could not find page data - authentication may have failed")

    data = json.loads(match.group(1))
    bootstrap = data.get('props', {}).get('pageProps', {}).get('bootstrapEnvelope', {})

    csrf = bootstrap.get('csrfSignature')
    if not csrf:
        raise ValueError("Could not extract CSRF token")

    return csrf


def validate_authentication(session: requests.Session, csrf_token: str) -> dict:
    """
    Validate that the session is properly authenticated.

    Args:
        session: Authenticated requests session
        csrf_token: CSRF token

    Returns:
        Dictionary with user info (id, name, email, pledge_count)

    Raises:
        ValueError: If authentication validation fails
    """
    response = session.get('https://www.patreon.com/home')
    response.raise_for_status()

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        response.text,
        re.DOTALL
    )

    if not match:
        raise ValueError("Authentication failed - could not load user data")

    data = json.loads(match.group(1))
    bootstrap = data.get('props', {}).get('pageProps', {}).get('bootstrapEnvelope', {})

    user_id = bootstrap.get('userId')
    if not user_id:
        raise ValueError("Authentication failed - no user ID found")

    common = bootstrap.get('commonBootstrap', {})
    user = common.get('currentUser', {}).get('data', {})
    attrs = user.get('attributes', {})

    pledges = user.get('relationships', {}).get('pledges', {}).get('data', [])

    return {
        'user_id': user_id,
        'name': attrs.get('full_name', 'Unknown'),
        'email': attrs.get('email', 'Unknown'),
        'pledge_count': len(pledges)
    }


def setup_authenticated_session(cookies_path: str = None) -> Tuple[requests.Session, str, dict]:
    """
    Complete authentication setup: load cookies, create session, get CSRF token, validate.

    Args:
        cookies_path: Path to cookies JSON file (uses smart detection if None)

    Returns:
        Tuple of (session, csrf_token, user_info)

    Raises:
        Various exceptions if authentication fails at any step
    """
    if cookies_path is None:
        cookies_path = find_cookie_file()

    # Load cookies
    cookies = load_cookies_from_file(cookies_path)

    # Check for required session_id cookie
    if 'session_id' not in cookies:
        raise ValueError("Missing required 'session_id' cookie - please export cookies from your browser")

    # Create session
    session = create_authenticated_session(cookies)

    # Extract CSRF token
    csrf_token = extract_csrf_token(session)

    # Validate authentication
    user_info = validate_authentication(session, csrf_token)

    # Add CSRF token to session headers for API calls
    session.headers.update({
        'x-csrf-signature': csrf_token
    })

    return session, csrf_token, user_info
