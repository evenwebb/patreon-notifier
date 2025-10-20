"""
Example Configuration for Patreon Notification Monitor

Copy this file to config.py and customize the settings.
"""

# ============================================================================
# QUICK START EXAMPLES
# ============================================================================

# Example 1: Telegram only
# APPRISE_URLS = ['tgram://bot_token/chat_id']

# Example 2: Multiple services via Apprise
# APPRISE_URLS = [
#     'tgram://bot_token/chat_id',           # Telegram
#     'discord://webhook_id/webhook_token',   # Discord
#     'pover://user_key@token',              # Pushover
# ]

# Example 3: Email notifications
# APPRISE_URLS = ['mailto://user:pass@gmail.com']

# Example 4: Filter for specific creators with keywords
# ENABLED_CREATORS = ['CreatorA', 'CreatorB']
# GLOBAL_KEYWORDS = ['announcement', 'exclusive']

# ============================================================================
# YOUR CONFIGURATION
# ============================================================================

COOKIES_DIR = "cookies"
COOKIES_FILE = "cookies.json"

CHECK_INTERVAL = 300  # Check every 5 minutes
ONLY_NEW_POSTS = True

# Apprise URLs - supports 90+ notification services!
# Documentation: https://github.com/caronc/apprise/wiki
APPRISE_URLS = [
    # Add your service URLs here:

    # Telegram (get bot_token from @BotFather, chat_id from @userinfobot)
    # 'tgram://123456789:ABCdefGHIjklMNOpqrsTUVwxyz/123456789',

    # Discord (from Server Settings > Integrations > Webhooks)
    # 'discord://webhook_id/webhook_token',

    # Email (Gmail requires app-specific password)
    # 'mailto://username:password@gmail.com',

    # Slack
    # 'slack://token_a/token_b/token_c/#channel',

    # Pushover
    # 'pover://user_key@token',

    # Pushbullet
    # 'pbul://access_token',

    # Microsoft Teams
    # 'msteams://token_a/token_b/token_c',

    # See 90+ more: https://github.com/caronc/apprise/wiki#notification-services
]

# ============================================================================
# FILTERING OPTIONS
# ============================================================================

# Per-creator filtering (whitelist mode - empty = all creators)
ENABLED_CREATORS = [
    # 'CreatorName',
    # 'AnotherCreator',
]

# Advanced per-creator settings
CREATOR_SETTINGS = {
    # 'CreatorName': {
    #     'enabled': True,
    #     'keywords': ['announcement', 'exclusive'],
    #     'video_only': False,
    #     'content_types': [],  # ['video_embed', 'image_file', 'text_only', 'audio_file']
    # },
}

# Global keyword filtering (case-insensitive)
GLOBAL_KEYWORDS = [
    # 'announcement',
    # 'new release',
]

# Content type filters (all disabled by default)
CONTENT_TYPE_FILTERS = {
    'video_only': False,
    'image_only': False,
    'text_only': False,
    'audio_only': False,
    'exclude_text': False,
}

# ============================================================================
# HEALTH MONITORING
# ============================================================================

HEALTH_MONITORING = {
    'enabled': True,
    'alert_on_auth_failure': True,
    'alert_on_api_errors': True,
    'alert_on_notification_errors': True,
    'max_consecutive_failures': 3,
}

# Separate Apprise URLs for health alerts (uses main APPRISE_URLS if empty)
HEALTH_APPRISE_URLS = [
    # 'tgram://bot_token/admin_chat_id',
]

# State management
STATE_FILE = "notification_state.json"
STATE_RETENTION_DAYS = 30

# Advanced settings
REQUEST_TIMEOUT = 30
VERBOSE = True
SHOW_FULL_ERRORS = True
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
ACCEPT_LANGUAGE = "en-GB,en;q=0.9"
