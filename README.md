<div align="center">

# Patreon Notifier

**Monitor Patreon and send notifications via [Apprise](https://github.com/caronc/apprise).**

[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](https://github.com/evenwebb/patreon-notifier/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Apprise](https://img.shields.io/badge/notifications-Apprise-9cf.svg)](https://github.com/caronc/apprise)

[Quick start](#quick-start) · [Configuration](#configuration) · [Usage](#usage) · [Troubleshooting](#troubleshooting) · [Security](#security) · [License](#license)

</div>

---

## What this is

Patreon Notifier is a small **Python CLI** that uses your **existing Patreon browser session** (exported cookies), checks your Patreon stream for new posts, and sends notifications via Apprise (Telegram, Discord, email, Slack, Pushover, and more).

> **Note:** This project uses Patreon’s web session and internal-style API endpoints. Patreon may change behavior without notice; treat this as a **best-effort personal automation**, not a guaranteed integration.

> **Compatibility:** The login page payload and stream API shapes described in this README were **checked and working on 5 May 2026**. Patreon can change cookies, HTML, or JSON at any time—if something stops working, export fresh cookies, pull the latest release, and open an issue if it still fails.

---

## Quick start

### 1) Install (recommended)

```bash
git clone https://github.com/evenwebb/patreon-notifier.git
cd patreon-notifier
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -U pip
pip install -e ".[dev]"
```

If you prefer **`requirements.txt`** for dependencies only, install them and run the module from the repo root (or use `pip install -e .` so the `patreon-notifier` command is available):

```bash
pip install -r requirements.txt
python -m patreon_notifier   # from the cloned repo directory
# optional: pip install -e . --no-deps   # adds the patreon-notifier console script
```

### 2) Export cookies

- Log into Patreon in your browser
- Export cookies as JSON using a browser extension (e.g. [Cookie-Editor](https://cookie-editor.com/))
- Save to `cookies/cookies.json`

See [`cookies/README.md`](cookies/README.md).

### 3) Create `config.py`

```bash
cp config.example.py config.py
```

Then edit `config.py` and set **at least one** Apprise URL in `APPRISE_URLS`.

### 4) Run

After `pip install -e .`, use the installed command (or run as a module):

```bash
patreon-notifier
# or: python -m patreon_notifier
```

---

## Configuration

- **Primary config**: `config.py` (gitignored)
- **Template**: `config.example.py`
- **Fallback behavior**: if `config.py` is missing, the app will load `config.example.py` (useful for tests/CI). In practice, you should create `config.py` for real notifications.

Key settings:

| Setting | Purpose |
|---------|---------|
| `APPRISE_URLS` | Notification destinations (must be non-empty to send alerts) |
| `CHECK_INTERVAL` | Seconds between checks (`0` = run once) |
| `VERBOSE` | Enable debug logging |
| `LOG_FILE` | Optional path for **rotating** log file; empty = stderr only |
| `LOG_MAX_BYTES` / `LOG_BACKUP_COUNT` | Rotation size and number of backups (when `LOG_FILE` is set) |
| `ENABLED_CREATORS` / `CREATOR_SETTINGS` / `GLOBAL_KEYWORDS` | Filtering |
| `CONTENT_TYPE_FILTERS` | Content-type filters (video-only, exclude text, etc.) |
| `HEALTH_MONITORING` / `HEALTH_APPRISE_URLS` | Optional health alerts |
| `NOTIFICATION_TITLE_TEMPLATE` / `NOTIFICATION_BODY_TEMPLATE` | Apprise title/body ([templates below](#notification-templates)) |
| `NOTIFICATION_APPEND_URL_TO_BODY` | If true, append post URL when it is not already in the body |
| `STATE_FILE` / `STATE_RETENTION_DAYS` | Dedupe store path and pruning |
| `FETCH_MAX_RETRIES` / `FETCH_RETRY_BACKOFF_SECONDS` / `FETCH_MAX_STREAM_PAGES` | Stream request retries and pagination |
| `COOKIES_DIR` / `COOKIES_FILE` | Where cookie JSON is loaded from |

Apprise URL formats: [Apprise wiki](https://github.com/caronc/apprise/wiki).

**Code layout:** installable package `patreon_notifier/` — `cli.py` (entry), `monitor.py` (stream + filters), `notification_format.py` (templates), `auth.py`, `state.py`, `notifications.py`, `health.py`, `config_loader.py`, `types.py`, `constants.py`.

### Notification templates

Title and body are Python [format strings](https://docs.python.org/3/library/string.html#format-string-syntax): use `{placeholder}` names, and `{{` / `}}` for literal braces. Unknown placeholders become empty (no crash).

| Placeholder | Value |
|-------------|--------|
| `{creator}` | Creator display name |
| `{campaign}` | Campaign / project name when the API includes it |
| `{subject}` / `{title}` | Post title |
| `{body}` / `{description}` | Teaser or description (length-limited when parsed) |
| `{url}` | Post link on Patreon |
| `{thumbnail}` | Image URL when available |
| `{post_type}` | e.g. `text_only`, `video_embed` |
| `{created_at}` | Timestamp from the API |
| `{notification_type}` | Stream item type (e.g. `post`) |
| `{has_video}` | `true` or `false` |
| `{subject_or_body}` | Title if set, otherwise body text |

**Global defaults** are `NOTIFICATION_TITLE_TEMPLATE`, `NOTIFICATION_BODY_TEMPLATE`, and `NOTIFICATION_APPEND_URL_TO_BODY` in `config.py`.

**Per-creator overrides:** in `CREATOR_SETTINGS`, under the creator’s exact name, you may set `notification_title_template`, `notification_body_template`, and/or `notification_append_url_to_body` (bool). See `config.example.py`.

**Dry check (no Patreon):** validate templates against built-in sample data:

```bash
patreon-notifier --test-templates
```

---

## Usage

### One-shot

Run once (either set `CHECK_INTERVAL = 0` or use `--once`):

```bash
patreon-notifier --once
```

### Continuous loop

Set `CHECK_INTERVAL` to a positive number (seconds), e.g. `300` for every 5 minutes:

```bash
patreon-notifier
```

### Verbose logging

```bash
patreon-notifier --verbose
```

### Dry run (no Apprise)

Log what would be notified without calling Apprise (useful with `VERBOSE = True`):

```bash
patreon-notifier --once --dry-run --verbose
```

### Quiet mode

Less console noise (warnings/errors only in logs unless combined with `--verbose`):

```bash
patreon-notifier --quiet
```

### Test notification templates

```bash
patreon-notifier --test-templates
```

### Cron (example)

```bash
*/10 * * * * cd /path/to/patreon-notifier && /path/to/.venv/bin/patreon-notifier >> monitor.log 2>&1
```

---

## Security

- **`cookies/*.json`** and **`config.py`** contain secrets. Do not commit them (see `.gitignore`).
- Prefer restricted file permissions on your cookie and config files on disk.
- Use app passwords or scoped tokens where your notification provider allows (e.g. email).

---

## Troubleshooting

<details>
<summary><strong>Authentication failed or “cookie expired”</strong></summary>

- Re-export cookies while logged into Patreon in the browser.
- Ensure important session cookies (e.g. `session_id`) are present in the export.
- Confirm the file path matches `COOKIES_DIR` / `COOKIES_FILE` in `config.py`.

</details>

<details>
<summary><strong>No notifications received</strong></summary>

- Confirm `APPRISE_URLS` is non-empty and URLs match [Apprise docs](https://github.com/caronc/apprise/wiki).
- Test a URL: `apprise -vv -t "Test" -b "Hello" 'your://url'`.
- Set `VERBOSE = True` and check console output.
- Check filters: `ENABLED_CREATORS`, `GLOBAL_KEYWORDS`, and `CONTENT_TYPE_FILTERS` may hide everything.

</details>

<details>
<summary><strong>Duplicate or missing posts</strong></summary>

- Duplicates: state file may be out of sync; inspect `notification_state.json`.
- Missing: old entries are pruned after `STATE_RETENTION_DAYS`; increase if needed.

</details>

<details>
<summary><strong>API or layout changes on Patreon’s side</strong></summary>

- Symptoms: HTTP errors, empty data, or parsing issues after Patreon updates.
- Mitigation: update cookies, pull the latest script, and open an issue with logs (redact secrets).

</details>

---

## License

This project is licensed under the **GNU General Public License v3.0** — see [`LICENSE`](LICENSE).
