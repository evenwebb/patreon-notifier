# Cookies Directory

This directory stores your exported Patreon cookies for authentication.

## Setup Instructions

1. Install a cookie export browser extension:
   - [Cookie-Editor](https://cookie-editor.cgagnier.ca/) (Chrome/Firefox/Edge)
   - [EditThisCookie](http://www.editthiscookie.com/) (Chrome)

2. Log into [Patreon](https://www.patreon.com/) in your browser

3. Export your cookies as JSON format

4. Save the exported file as `cookies.json` in this directory

## File Format

The monitor supports two cookie export formats:

**Format 1** (Cookie-Editor):
```json
[
  {"name": "session_id", "value": "your_session_id_here"},
  {"name": "other_cookie", "value": "value"}
]
```

**Format 2** (Some extensions):
```json
{
  "url": "https://www.patreon.com",
  "cookies": [
    {"name": "session_id", "value": "your_session_id_here"},
    {"name": "other_cookie", "value": "value"}
  ]
}
```

## Security Note

**Important:** Cookie files contain sensitive authentication data. Never commit them to version control or share them publicly. The `.gitignore` file in this directory ensures cookie files are not accidentally committed.

## When Cookies Expire

If you see a "Cookie Expiration Error", simply repeat the setup instructions above to export fresh cookies from your browser.
