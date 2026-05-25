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

### email_multi_search
Search emails with filters:
- `subject`: search subject line
- `from`: filter by sender
- `date_since`/`date_until`: date range (YYYY-MM-DD)
- `keyword`: search decoded subject, sender, and text body; Gmail-compatible servers may first narrow with best-effort `X-GM-RAW`, otherwise ASCII keywords use portable IMAP `TEXT`
- `has_attachment`: only messages with attachments
- `account_id`: limit to specific account

### email_multi_read
Read a message by UID. Set `download_attachments: true` to save locally.

### email_multi_send
Send email. Supports `html_body`, `cc`, and `attachments` (file paths).

### email_multi_reply
Reply in-thread. Uses `In-Reply-To` and `References` headers automatically.

## Configured Accounts

| ID | Email | Provider |
|---|---|---|
| gmail | falk.mp@gmail.com | Gmail |
| dieartguerilla | falk@dieartguerilla.de | Stalwart |
| infodieg | info@dieartguerilla.de | Stalwart |
| appwa2pdf | app@wa2pdf.de | Stalwart |
| businessdieg | business@dieartguerilla.de | Stalwart |

## Passwords
Set in `~/.hermes/.env`:
- `EMAIL_GMAIL_PASSWORD`
- `EMAIL_DIEARTGUERILLA_PASSWORD`
- `EMAIL_INFO_DIEG_PASSWORD`
- `EMAIL_APP_WA2PDF_PASSWORD`
- `EMAIL_BUSINESS_DIEG_PASSWORD`
