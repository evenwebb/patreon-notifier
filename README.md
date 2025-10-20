# Patreon Notification Monitor

A Python script that monitors Patreon for new posts from your subscribed creators and sends you notifications through various channels.

## Features

- **Multiple Notification Services**: 90+ services via Apprise (Telegram, Discord, Email, Slack, Pushover, SMS, and more!)
- **Smart State Management**: Tracks seen notifications to avoid duplicates
- **Advanced Filtering**: Per-creator filters, keyword matching, content type filtering, video detection
- **Health Monitoring**: Alerts you when authentication or API errors occur
- **Flexible Configuration**: Customize notification preferences and filtering rules
- **Continuous or One-Time Monitoring**: Run once or continuously check for new posts
- **Cookie-Based Authentication**: Uses your existing Patreon session from browser cookies

## Notification Services

The script supports notification through **Apprise** - a universal notification library supporting 90+ services:

- **Messaging**: Telegram, Discord, Slack, Microsoft Teams, Mattermost
- **Mobile Push**: Pushover, Pushbullet, Pushy, Notify My Android
- **Email**: Gmail, Outlook, SendGrid, Mailgun, and any SMTP server
- **SMS**: Twilio, MessageBird, Nexmo, AWS SNS
- **And 85+ more!** - See [full list](https://github.com/caronc/apprise/wiki)

## Installation

### Prerequisites

- Python 3.7 or higher
- Patreon account with active subscriptions
- Browser with cookie export extension

### Setup

1. **Install Dependencies**

```bash
pip install -r requirements.txt
```

This installs:
- `requests` - HTTP library for Patreon API
- `apprise` - Universal notification library

2. **Export Patreon Cookies**

   - Install a cookie export browser extension:
     - Chrome/Edge: [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)
     - Firefox: [Cookie-Editor](https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/)

   - Log into Patreon in your browser
   - Open the cookie extension and export cookies as JSON
   - Save the file to `cookies/cookies.json`

3. **Configure Notifications**

Edit `config.py` to customize your notification preferences:

```python
# Apprise URLs - add as many services as you want!
APPRISE_URLS = [
    'tgram://bot_token/chat_id',           # Telegram
    'discord://webhook_id/webhook_token',   # Discord
    'mailto://user:pass@gmail.com',        # Email
    # See 90+ more: https://github.com/caronc/apprise/wiki
]

# Check interval (0 = run once, >0 = continuous monitoring)
CHECK_INTERVAL = 300  # Check every 5 minutes

# Filtering options
ENABLED_CREATORS = []  # Whitelist specific creators (empty = all)
GLOBAL_KEYWORDS = []   # Only notify for posts matching keywords
CONTENT_TYPE_FILTERS = {
    'video_only': False,    # Only notify for video posts
    'exclude_text': False,  # Exclude text-only posts
}
```

### Setting Up Notification Services

All services use simple URL configuration via Apprise. Here are the most popular:

**Telegram:**
1. Create a bot with [@BotFather](https://t.me/botfather) → get `bot_token`
2. Get your `chat_id` from [@userinfobot](https://t.me/userinfobot)
3. Add to config: `'tgram://bot_token/chat_id'`

**Discord:**
1. Server Settings → Integrations → Webhooks → New Webhook
2. Copy webhook URL (format: `https://discord.com/api/webhooks/ID/TOKEN`)
3. Add to config: `'discord://ID/TOKEN'`

**Email (Gmail):**
1. Enable 2FA and create [app-specific password](https://myaccount.google.com/apppasswords)
2. Add to config: `'mailto://username:app_password@gmail.com'`

**Slack:**
1. Create app at [api.slack.com](https://api.slack.com/apps)
2. Get tokens from OAuth & Permissions
3. Add to config: `'slack://token_a/token_b/token_c/#channel'`

**Pushover:**
1. Sign up at [pushover.net](https://pushover.net/)
2. Add to config: `'pover://user_key@token'`

**Pushbullet:**
1. Get access token from [Settings](https://www.pushbullet.com/#settings)
2. Add to config: `'pbul://access_token'`

**87+ More Services:**
- See [Apprise Wiki](https://github.com/caronc/apprise/wiki) for complete documentation
- Services include: Microsoft Teams, Mastodon, Matrix, IFTTT, Gotify, Twilio SMS, AWS SNS, and many more!

## Usage

### Run Once (Check for new posts and exit)

```bash
python patreon_notifier.py
```

Set `CHECK_INTERVAL = 0` in `config.py` to run in one-time mode.

### Continuous Monitoring

```bash
python patreon_notifier.py
```

Set `CHECK_INTERVAL = 300` (or any value in seconds) in `config.py` to run continuously.

### Run with Cron (Linux/macOS)

To check for new posts every 10 minutes:

```bash
# Edit crontab
crontab -e

# Add this line (adjust path to your installation)
*/10 * * * * cd /path/to/patreon-notifications && python3 patreon_notifier.py >> monitor.log 2>&1
```

### Run with Task Scheduler (Windows)

1. Open Task Scheduler
2. Create a new task
3. Set trigger to run every X minutes
4. Set action to run: `python.exe "C:\path\to\patreon_notifier.py"`

## Configuration Options

### Main Settings

| Option | Description | Default |
|--------|-------------|---------|
| `CHECK_INTERVAL` | Seconds between checks (0 = run once) | 300 |
| `ONLY_NEW_POSTS` | Only notify for new posts | True |
| `APPRISE_URLS` | List of Apprise service URLs | [] |
| `STATE_RETENTION_DAYS` | Days to keep seen notifications | 30 |

### Filtering Options

| Option | Description | Default |
|--------|-------------|---------|
| `ENABLED_CREATORS` | Whitelist of creator names (empty = all) | [] |
| `CREATOR_SETTINGS` | Per-creator advanced settings (keywords, video_only, content_types) | {} |
| `GLOBAL_KEYWORDS` | Only notify if post title/body contains keywords | [] |
| `CONTENT_TYPE_FILTERS` | Filter by content type (video_only, image_only, text_only, audio_only, exclude_text) | all False |

### Health Monitoring

| Option | Description | Default |
|--------|-------------|---------|
| `HEALTH_MONITORING` | Enable health monitoring and alerts | enabled: True |
| `HEALTH_APPRISE_URLS` | Separate Apprise URLs for health alerts | [] |

### State Management

The script maintains a `notification_state.json` file that tracks which notifications you've already seen. This prevents duplicate notifications.

- **Location**: `notification_state.json` (in script directory)
- **Auto-pruning**: Entries older than `STATE_RETENTION_DAYS` are automatically removed
- **Reset**: Delete the file to reset and get notifications for all posts again

## File Structure

```
patreon-notifications/
├── auth.py                      # Authentication module
├── config.py                    # Configuration settings
├── config.example.py           # Example configuration template
├── patreon_notifier.py         # Main script
├── notification_services.py    # Notification service implementations (Apprise)
├── health_monitor.py           # Health monitoring and alerting
├── state_manager.py            # State tracking for seen notifications
├── notification_state.json     # State file (created automatically)
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── QUICKSTART.md              # Quick start guide
├── .gitignore                 # Git ignore rules
└── cookies/                   # Cookie storage directory
    └── cookies.json          # Your Patreon cookies
```

## Troubleshooting

### Authentication Failed

- Make sure your cookies are up to date
- Re-export cookies from your browser
- Ensure `session_id` cookie is present

### No Notifications Received

- Check that `APPRISE_URLS` is configured with at least one service
- Verify service-specific settings (API keys, URLs, etc.)
- Run with `VERBOSE = True` in config.py for detailed logs
- Check if filtering rules are excluding all posts

### Apprise Services Not Working

- Verify your service URLs are correct (check [Apprise Wiki](https://github.com/caronc/apprise/wiki))
- Make sure `apprise` is installed: `pip install apprise`
- Check console for specific error messages
- Test your URL with the Apprise CLI: `apprise -vv -t "Test" -b "Message" YOUR_URL`

### Health Monitoring Alerts

- Health alerts are sent after `max_consecutive_failures` (default: 3) consecutive errors
- Alerts have a 1-hour cooldown to prevent spam
- Configure `HEALTH_APPRISE_URLS` for separate alert channels

## Advanced Usage

### Per-Creator Filtering

Configure advanced per-creator settings:

```python
CREATOR_SETTINGS = {
    'CreatorName': {
        'enabled': True,
        'keywords': ['announcement', 'exclusive'],  # Only notify for posts with these keywords
        'video_only': True,                         # Only notify for video posts
        'content_types': ['video_embed'],           # Allowed content types
    },
}
```

### Keyword Filtering

Filter notifications by keywords (case-insensitive):

```python
# Global keywords (applies to all creators)
GLOBAL_KEYWORDS = ['announcement', 'new release', 'exclusive']

# Per-creator keywords (in CREATOR_SETTINGS)
CREATOR_SETTINGS = {
    'CreatorName': {
        'keywords': ['Q&A', 'behind the scenes'],
    },
}
```

### Content Type Filtering

Filter by media type:

```python
CONTENT_TYPE_FILTERS = {
    'video_only': True,      # Only video posts
    'exclude_text': True,    # Exclude text-only posts (get media posts only)
}
```

### Video Detection

The script automatically detects video content from:
- Post type (video_embed)
- Embedded video providers (YouTube, Vimeo, Twitch)
- Video URLs in post content

### Custom Notification Format

Modify notification format in `patreon_notifier.py`:

```python
def _send_notification(self, notification: Dict[str, Any]):
    title = f"New Post: {notification['creator']}"
    message = notification['subject']
```

## Security Notes

- **Cookie Security**: Your `cookies.json` file contains authentication credentials. Keep it secure and don't commit it to git.
- **API Tokens**: Store sensitive tokens (email passwords, bot tokens) securely
- **File Permissions**: Consider restricting file permissions on config files

## Dependencies

- `requests` - HTTP library for Patreon API calls
- `apprise` - Universal notification library supporting 90+ services
- Standard library modules for desktop notifications (no additional packages needed)

## License

This script is provided as-is for personal use.

## Credits

A self-contained notification system for Patreon with built-in authentication.
