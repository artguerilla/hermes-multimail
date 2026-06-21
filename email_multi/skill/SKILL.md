---
name: email-multi
description: >
  Multi-account IMAP/SMTP email adapter. Search, read, send emails across multiple mailboxes.
  Supports attachments, threading, and HTML-to-text conversion.
triggers:
  - email search, email read, email send, email reply
  - multi-account email, IMAP, SMTP
  - retrieve emails, poll inbox
---

# Email Multi Plugin

## Tools

### email_multi_list_accounts
List all configured email accounts.

### email_multi_poll_inbox
Poll for unseen emails. Optional `account_id` to filter.

### email_multi_list_messages
List messages from a folder with optional IMAP criteria. Requires `account_id`.

### email_multi_search_messages
Search emails with filters:
- `subject`: search subject line
- `from`: filter by sender
- `date_since`/`date_until`: date range (YYYY-MM-DD)
- `keyword`: search decoded subject, sender, and text body; ASCII keywords are first narrowed server-side with IMAP `TEXT`
- `has_attachment`: only messages with attachments
- `account_id`: limit to specific account

### email_multi_read
Read a message by UID. Set `download_attachments: true` to save locally.

### email_multi_download_attachment
Download one attachment from a message.

### email_multi_send
Send email. Supports `html_body`, `cc`, and `attachments` (file paths).

### email_multi_reply
Reply in-thread. Uses `In-Reply-To` and `References` headers automatically.

### email_multi_list_folders
List IMAP folders for one account.

### email_multi_mark_seen
Mark a message as seen.

### email_multi_delete_message
Delete a message by moving it to trash or expunging it in the selected folder.

Hermes registers these 11 tools from `email_multi/schemas.py`. The implementation
also keeps an internal compatibility handler named `email_multi_search`, but that
alias is not registered as a separate exported Hermes tool. Use
`email_multi_search_messages` for search calls.

## Example Accounts

| ID | Email | Provider |
|---|---|---|
| personal | user@example.com | Example IMAP |
| work | user@company.example | Company IMAP |

## Passwords
Set in `~/.hermes/.env`:
- `EMAIL_PERSONAL_PASSWORD`
- `EMAIL_WORK_PASSWORD`
