<p align="center">
  <img src="assets/hermes-multimail-header.png" alt="hermes-multimail — One Hermes plugin. Many inboxes. Less chaos." width="100%">
</p>

<h1 align="center">hermes-multimail</h1>

<p align="center">
  <strong>One Hermes plugin. Many inboxes. Less chaos.</strong>
</p>

<p align="center">
  Multi-account IMAP/SMTP for Hermes Agent — search, read, send, reply, and handle attachments without patching Hermes core.
</p>

<p align="center">
  <a href="#why-this-exists">Why</a>
  ·
  <a href="#installation">Install</a>
  ·
  <a href="#configuration">Configure</a>
  ·
  <a href="#access-control">Security Model</a>
  ·
  <a href="#tools">Tools</a>
  ·
  <a href="#contributing">Contribute</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.9%2B-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="Hermes Plugin" src="https://img.shields.io/badge/Hermes-plugin-purple">
  <img alt="Security" src="https://img.shields.io/badge/security-fail--closed-orange">
</p>

<p align="center">
  <em>Built by artguerilla for agents who keep asking: “wait… which inbox was that again?”</em>
</p>

---

## Why this exists

Hermes has a clean plugin system, but real inbox workflows get messy fast: multiple accounts, different providers, attachments, replies, and agents that need to know exactly which mailbox they are touching.

`hermes-multimail` keeps that boring and reliable.

No Hermes core patches.  
No private orchestration setup.  
No magic account guessing.  

Just standard IMAP/SMTP wrapped in safe, explicit tools with fail-closed access control.

## What it does

- **Multi-account mail** — manage several IMAP/SMTP accounts from one config
- **Search and read** — list, search, and read messages across accessible accounts
- **Send and reply** — send new emails or reply in-thread with proper headers
- **Attachment handling** — inspect and optionally download attachments
- **HTML to text** — fallback text extraction for HTML-only emails
- **Fail-closed access** — deny access unless identity/allowlist rules are satisfied
- **No plaintext passwords** — credentials must come from environment variables
- **Small dependency surface** — IMAP/SMTP use Python standard library; YAML loading uses `PyYAML`

## Example workflow

1. Ask Hermes to list available mailboxes.
2. Search all accessible inboxes for an invoice.
3. Read the matching email from the correct account.
4. Download the attachment only when needed.
5. Reply from the mailbox that received the original thread.

No account guessing. No core patching. No “oops, wrong inbox.”

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

## Naming

The plugin uses **hyphens** for the Hermes plugin name and **underscores** for Python/tool names:

| Context | Name |
|---|---|
| `plugins.enabled` in config | `email-multi` |
| Python package | `email_multi` |
| Tool names | `email_multi_list_accounts`, etc. |
| Skill name | `email-multi` |

## Configuration

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

See `accounts.example.yaml` for a fuller reference.

## Environment variables

Store secrets in the environment Hermes loads, commonly `~/.hermes/.env`:

```bash
# Email passwords
EMAIL_GMAIL_PASSWORD=your_app_password

# Trusted caller identity for access control
EMAIL_MULTI_CALLER=user@gmail.com

# Optional: trust params["caller"] from Hermes gateway tool calls
# EMAIL_MULTI_TRUST_CALLER_PARAM=true

# Optional: custom Hermes home
# HERMES_HOME=/path/to/custom-hermes-home
```

Restrict local env permissions:

```bash
chmod 600 ~/.hermes/.env
```

See `.env.example` for all supported variables.

## Access Control

`hermes-multimail` uses a **fail-closed** access model.

A mail account is accessible only when one of these conditions is true:

- `allow_all: true` is set for that account
- `EMAIL_MULTI_CALLER` is set and matches one of the account’s `allowed_users`
- `EMAIL_MULTI_TRUST_CALLER_PARAM=true` is set and the runtime injects a verified `params["caller"]`

By default, `params["caller"]` is **not trusted**, because model/tool-call parameters may be manipulated in some deployments.

If an account has neither `allowed_users` nor `allow_all`, access is denied.

## Security

- **No plaintext passwords** — the `password` field in account config is rejected
- **Use `password_env`** — credentials must be referenced through environment variables
- **Fail-closed access** — missing identity or missing allowlist denies access
- **No allowlist leakage** — denial errors do not expose configured allowlists
- **Attachment control** — use `skip_attachments: true` to disable attachment downloads
- **Dedicated accounts recommended** — avoid connecting personal inboxes directly
- **App passwords recommended** — especially for Gmail with 2FA

See `SECURITY.md` for the full security model.

## Tools

| Tool | Description |
|------|-------------|
| `email_multi_list_accounts` | List accessible configured accounts with status |
| `email_multi_poll_inbox` | Poll for new unseen emails across accessible accounts |
| `email_multi_list_messages` | List messages from a folder with IMAP criteria |
| `email_multi_search_messages` | Search across accounts by subject, sender, date, keyword, or attachment presence |
| `email_multi_read` | Read a message with optional attachment download |
| `email_multi_download_attachment` | Download a specific attachment from a message |
| `email_multi_send` | Send email with plain text, HTML, attachments, CC, and BCC |
| `email_multi_reply` | Reply in-thread with `In-Reply-To` and `References` headers |
| `email_multi_list_folders` | List IMAP folders for an account |
| `email_multi_mark_seen` | Mark a message as read |
| `email_multi_delete_message` | Move/delete a message via the configured trash behavior |

### Search filters

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

`keyword` uses portable IMAP `TEXT` search for ASCII keywords when possible. Results are still checked client-side against decoded subject, sender, and text body. Non-ASCII keywords fall back to client-side filtering.

## Testing

```bash
# Syntax check
python3 -m py_compile email_multi/*.py

# Run all tests
python3 -m unittest

# Lint
ruff check email_multi tests

# Build and package check
python -m build
twine check dist/*
```

## CI and branch flow

This repo uses:

```txt
feature/* → dev → main
```

Dependabot targets `dev`, and release/promotion happens through a `dev → main` PR.

## Contributing

Contributions are welcome.

Keep PRs focused, update docs for user-facing changes, and run the verification suite before opening a PR.

See `CONTRIBUTING.md` for details.

## License

MIT

## Upstream

Built on top of the Hermes Agent plugin architecture.
