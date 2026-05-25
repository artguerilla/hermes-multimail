# hermes-multimail

**Multi-account IMAP/SMTP email adapter for [Hermes Agent](https://github.com/NousResearch/hermes-agent).**

Drops into any `~/.hermes/plugins/` directory — zero core modifications, zero external dependencies.

## Features

- **Multi-account** — manage multiple IMAP/SMTP accounts from a single config
- **Attachment handling** — extract, cache and download attachments locally
- **HTML → text** — automatic fallback for HTML-only emails
- **Thread-safe replies** — `In-Reply-To` and `References` headers out of the box
- **Access control** — per-account allowlists (`allowed_users` / `allow_all`)
- **Skip attachments** — optional `skip_attachments` flag for security/bandwidth
- **Zero dependencies** — Python standard library only (`imaplib`, `smtplib`, `email`)

## Installation

```bash
# Clone into your plugins directory
cd ~/.hermes/plugins
git clone https://github.com/artguerilla/hermes-multimail.git

# Move the plugin directory
mv hermes-multimail/email_multi .
rm -rf hermes-multimail

# Enable in config
echo "plugins:" >> ~/.hermes/config.yaml
echo "  enabled:" >> ~/.hermes/config.yaml
echo "  - email_multi" >> ~/.hermes/config.yaml
```

Or drop the plugin directly:

```bash
git clone https://github.com/artguerilla/hermes-multimail.git ~/.hermes/plugins/email_multi-temp
cp -r ~/.hermes/plugins/email_multi-temp/email_multi ~/.hermes/plugins/
rm -rf ~/.hermes/plugins/email_multi-temp
```

## Configuration

### 1. Accounts

Create `~/.hermes/plugins/email_multi/accounts.yaml`:

```yaml
accounts:
  - account_id: gmail
    email: user@gmail.com
    display_name: Gmail
    password_env: EMAIL_GMAIL_PASSWORD  # resolved from .env
    imap_host: imap.gmail.com
    imap_port: 993
    smtp_host: smtp.gmail.com
    smtp_port: 587
    allowed_users: []
    allow_all: false
    skip_attachments: false
    folders:
      inbox: INBOX
      sent: "[Gmail]/Sent Mail"
      drafts: "[Gmail]/Drafts"
      trash: "[Gmail]/Trash"
  - account_id: company
    email: user@company.com
    display_name: Work
    password_env: EMAIL_COMPANY_PASSWORD
    imap_host: imap.company.com
    imap_port: 993
    smtp_host: smtp.company.com
    smtp_port: 587
    allowed_users: []
    allow_all: false
    skip_attachments: false
    folders:
      inbox: INBOX
      sent: Sent
      drafts: Drafts
      trash: Trash
```

### 2. Environment Variables

Add to `~/.hermes/.env`:

```bash
EMAIL_GMAIL_PASSWORD=your_app_password
EMAIL_COMPANY_PASSWORD=your_app_password
```

Restrict permissions:
```bash
chmod 600 ~/.hermes/.env
```

### 3. Enable Plugin

In `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled:
    - email_multi
```

Then restart Hermes:
```bash
hermes gateway restart
```

## Tools

| Tool | Description |
|------|-------------|
| `email_multi_list_accounts` | List all configured accounts with status |
| `email_multi_poll_inbox` | Poll for new unseen emails across all accounts |
| `email_multi_list_messages` | List messages from a folder with IMAP criteria |
| `email_multi_search_messages` | Search across accounts (subject, from, dates, keyword, attachments) |
| `email_multi_read` | Read a message with optional attachment download |
| `email_multi_download_attachment` | Download a specific attachment from a message |
| `email_multi_send` | Send email (plain text, HTML, attachments, CC/BCC) |
| `email_multi_reply` | Reply in-thread (In-Reply-To / References) |
| `email_multi_list_folders` | List IMAP folders for an account |
| `email_multi_mark_seen` | Mark a message as read |
| `email_multi_delete_message` | Delete/move to trash |

### Search Filters

```json
{
  "account_id": "gmail",
  "subject": "Invoice",
  "from": "billing@example.com",
  "date_since": "2024-01-01",
  "date_until": "2024-12-31",
  "keyword": "paid",
  "has_attachment": true,
  "limit": 50
}
```

For Gmail-compatible IMAP servers, structured search filters are first tried as
a best-effort `X-GM-RAW` query when the server advertises `X-GM-EXT-1` or the
account uses a known Gmail IMAP host. The mapped fields are `keyword`,
`subject`, `from`, `date_since`, `date_until`, `unseen_only`, and
`has_attachment`; arbitrary IMAP `query`/`criteria` values stay on the portable
path. This acceleration is non-authoritative: if Gmail raw search is not clearly
supported or the server rejects it, search falls back to the standards-based
IMAP criteria.

Without Gmail acceleration, `keyword` is sent to IMAP as a portable `TEXT`
search for ASCII keywords, so the server narrows candidates before full messages
are fetched. Results are still checked client-side against decoded subject,
sender, and text body. If the server rejects the `TEXT` search, or if the
keyword is non-ASCII, the tool falls back to the non-keyword IMAP criteria and
applies the decoded keyword filter locally.

Search results are fetched over a single IMAP session per account and use
multi-UID fetch batches for headers and full messages. If a server rejects a
batched UID fetch, the same session retries those UIDs individually.

## Security

- **Dedicated mail accounts** — use purpose-built email addresses, not personal inboxes
- **App passwords** — use app-specific passwords instead of main credentials (especially Gmail with 2FA)
- **No plaintext secrets** — passwords resolved from environment variables only
- **Access control** — `allowed_users` and `allow_all` per account
- **Skip attachments** — `skip_attachments: true` disables attachment downloads

## License

MIT

## Upstream

Built on top of [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin architecture.
Mirrors Hermes gateway `EmailAdapter` behavior (IMAP/SMTP, polling, threading, HTML→text).
