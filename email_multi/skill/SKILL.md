---
name: email-multi
description: >
  Multi-account IMAP/SMTP email adapter. Search, read, send emails across
  multiple mailboxes. Supports attachments, threading, and HTML-to-text conversion.
triggers:
  - email search, email read, email send, email reply
  - multi-account email, IMAP, SMTP
  - retrieve emails, poll inbox
  - download attachment, mark email as read
---

# Email Multi Plugin

## Quick Start

1. **Discover accounts**: Call `email_multi_list_accounts` to see all configured mailboxes and their `account_id` values.
2. **Pick an account**: Use the `account_id` from step 1 in all subsequent tool calls.
3. **Search or list**: Use `email_multi_search_messages` for full-text search or `email_multi_list_messages` for folder browsing.
4. **Read details**: Use `email_multi_read` with the message `uid` to get the full content.

## Tools

### email_multi_list_accounts
List all configured email accounts with status.
- **When to use**: Always call this first to discover available accounts and their `account_id` values.
- **Returns**: Array of accounts with `account_id`, `email`, `imap_host`, `smtp_host`, `password_configured`, and `health` status.
- **Parameters**: None.

### email_multi_poll_inbox
Poll for unseen emails across accounts.
- **When to use**: Quick check for new unread messages without reading full content.
- **Returns**: Message summaries (subject, sender, date, flags) for unread emails.
- **Parameters**: `account_id` (optional — omit for all accounts), `limit` (default 20).

### email_multi_list_messages
List messages from a folder with filters.
- **When to use**: Browse a specific folder (INBOX, Sent, Drafts) with lightweight headers only.
- **Returns**: Message headers — not full bodies. Use `email_multi_read` for full content.
- **Parameters**: `account_id` (required), `folder` (default INBOX), `unseen_only`, `query`, `limit`.

### email_multi_search_messages
Full-text search across one or all accounts.
- **When to use**: Find emails by subject, sender, keyword, date range, or attachment presence.
- **Returns**: Messages with truncated body text (500 chars), headers, and attachment metadata. Each result includes `account_id` to identify the source mailbox.
- **Parameters**: `account_id` (optional — omit for all), `subject`, `from`, `date_since`, `date_until`, `keyword`, `has_attachment`, `limit`.
- **Account switching**: Each result carries its `account_id`. Pass that `account_id` to `email_multi_read` to get the full message.

### email_multi_read
Read a full message by UID.
- **When to use**: Get complete message content after finding it via search or list.
- **Returns**: All headers, decoded text body, and attachment metadata.
- **Parameters**: `account_id` (required), `message_id` (required — the UID from search/list results), `include_html`, `download_attachments`.

### email_multi_download_attachment
Download a specific attachment.
- **When to use**: Extract a file from an email (invoice, photo, document).
- **Parameters**: `account_id`, `message_id`, `attachment_id` (filename or 0-based index).

### email_multi_send
Send a new email.
- **When to use**: Compose and send email from any configured account.
- **Parameters**: `account_id` (determines From: address), `to`, `subject`, `body`, plus optional `cc`, `bcc`, `html_body`, `attachments`.

### email_multi_reply
Reply to an existing message.
- **When to use**: Respond to an email with proper threading (In-Reply-To, References).
- **Parameters**: `account_id` (the mailbox that received the original), `message_id` (original UID), `body`, optional `reply_all`, `html_body`, `attachments`.

### email_multi_list_folders
List IMAP folders for an account.
- **When to use**: Discover available folders (INBOX, Sent, custom labels) before querying.
- **Parameters**: `account_id` (required).

### email_multi_mark_seen
Mark a message as read.
- **When to use**: After processing a message, mark it read to avoid duplicate handling.
- **Parameters**: `account_id`, `message_id`.

### email_multi_delete_message
Delete a message (moves to Trash or expunges).
- **When to use**: Remove unwanted emails. Destructive — confirm content first.
- **Parameters**: `account_id`, `message_id`.

## Multi-Account Workflow

```
1. email_multi_list_accounts
   → Returns: [{account_id: "gmail", ...}, {account_id: "work", ...}]

2. email_multi_search_messages (no account_id)
   → Searches ALL accounts, results include account_id

3. email_multi_read(account_id: "gmail", message_id: "12345")
   → Reads full message from specific mailbox

4. email_multi_send(account_id: "work", ...)
   → Sends from work mailbox
```

## Access Control

Each account can have `allowed_users` and `allow_all` settings:
- `allowed_users: []` (default): unrestricted — any caller can access
- `allowed_users: ["alice@example.com"]`: only listed users can access
- `allow_all: true`: always allows access regardless of allowlist

Caller identity is resolved from:
1. `params["caller"]` — explicit identity in the tool call
2. `EMAIL_MULTI_CALLER` environment variable

When allowlist is active and caller identity is unavailable, access is DENIED (fail-closed).
