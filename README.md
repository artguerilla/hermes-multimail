# hermes-multimail

**Multi-account IMAP/SMTP email plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent).**

Drops into any `~/.hermes/plugins/` directory with no core Hermes modifications.

## Features

- **Multi-account** — manage multiple IMAP/SMTP accounts from a single config
- **Attachment handling** — extract, cache and download attachments locally
- **HTML → text** — automatic fallback for HTML-only emails
- **Thread-safe replies** — `In-Reply-To` and `References` headers out of the box
- **Access control** — per-account allowlists (`allowed_users` / `allow_all`)
- **Fail-closed security** — denies access when identity is unavailable or allowlist is missing
- **No plaintext passwords** — credentials must be provided via environment variables
- **Small dependency surface** — IMAP/SMTP use the Python standard library; YAML config loading requires `PyYAML`

## Installation

### Option A: Drop-in directory

```bash
git clone https://github.com/artguerilla/hermes-multimail.git
mkdir -p ~/.hermes/plugins
cp -R hermes-multimail/email_multi ~/.hermes/plugins/email_multi
```

### Option B: pip install

```bash
pip install hermes-multimail
```

### Enable the plugin

In `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled:
    - email-multi
```

Then restart Hermes.

### Naming

The plugin uses **hyphens** for the plugin name and **underscores** for Python/tool names:

| Context | Name |
|---|---|
| `plugins.enabled` in config | `email-multi` |
| Python package | `email_multi` |
| Tool names | `email_multi_list_accounts`, etc. |
| Skill name | `email-multi` |

## Configuration

### 1. Accounts

Create `~/.hermes/plugins/email_multi/accounts.yaml`:

```yaml
accounts:
  - account_id: gmail
    email: user@gmail.com
    display_name: Gmail
    password_env: EMAIL_GMAIL_PASSWORD
    imap_host: imap.gmail.com
    imap_port: 993
    smtp_host: smtp.gmail.com
    smtp_port: 587
    allowed_users:
      - user@gmail.com
    allow_all: false
    skip_attachments: false
    folders:
      inbox: INBOX
      sent: "[Gmail]/Sent Mail"
      drafts: "[Gmail]/Drafts"
      trash: "[Gmail]/Trash"
```

See `accounts.example.yaml` for a full reference.

### 2. Environment Variables

```bash
# Email passwords (never commit these)
EMAIL_GMAIL_PASSWORD=your_app_password

# Trusted caller identity (recommended for access control)
EMAIL_MULTI_CALLER=user@gmail.com

# Optional: trust params["caller"] from Hermes gateway
# EMAIL_MULTI_TRUST_CALLER_PARAM=true
```

Restrict permissions:
```bash
chmod 600 ~/.hermes/.env
```

See `.env.example` for all supported variables.

### 3. HERMES_HOME

By default the plugin reads config from `~/.hermes/plugins/email_multi/accounts.yaml`
and caches attachments under `~/.hermes/cache/email_multi/`.

Set `HERMES_HOME` to use a different base directory:

```bash
export HERMES_HOME=/path/to/custom-hermes-home
```

## Access Control

The plugin uses a **fail-closed** access control model:

- **`EMAIL_MULTI_CALLER`** — trusted caller identity from the runtime environment. This is the primary identity source.
- **`EMAIL_MULTI_TRUST_CALLER_PARAM`** — set to `true` to also accept `params["caller"]` from tool call parameters. Default: `false` (not trusted).
- **`allowed_users`** — explicit list of authorized email addresses per account. Required for any account that does not have `allow_all: true`.
- **`allow_all`** — when `true`, bypasses allowlist checks for that account.

If no caller identity can be resolved and the account has an allowlist, access is denied.
If an account has neither `allowed_users` nor `allow_all`, access is denied (fail-closed).

## Security

- **No plaintext passwords** — the `password` field in accounts config is rejected. Use `password_env` to reference environment variables.
- **Fail-closed access control** — denies access when identity is unavailable
- **No secret leakage in errors** — error messages never expose passwords, allowlists, or credentials
- **`skip_attachments`** — disable attachment downloads for untrusted accounts
- **App passwords** — use app-specific passwords, especially for Gmail with 2FA

See [SECURITY.md](SECURITY.md) for details.

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

`keyword` is sent to IMAP as a portable `TEXT` search for ASCII keywords. Results are
still checked client-side against decoded subject, sender, and text body. Non-ASCII
keywords fall back to client-side filtering.

## Testing

```bash
# Syntax check
python3 -m py_compile email_multi/*.py

# Run all tests
python3 -m unittest

# Lint
ruff check email_multi tests
```

## License

MIT

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Upstream

Built on top of [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin architecture.
