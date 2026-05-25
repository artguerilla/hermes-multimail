"""Tool schemas for email-multi plugin."""

TOOLS = []


def _add(name, description, properties, required=None):
    TOOLS.append({
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required or [],
        },
    })


_add(
    "email_multi_list_accounts",
    "List all configured email accounts with their status.",
    {},
)

_add(
    "email_multi_poll_inbox",
    "Poll for new unseen emails across all configured accounts. Returns message summaries.",
    {
        "account_id": {"type": "string", "description": "Poll only this account (optional, omit for all)"},
        "limit": {"type": "integer", "description": "Max messages per account (default 20)"},
    },
)

_add(
    "email_multi_list_messages",
    "List messages from a folder with optional IMAP criteria.",
    {
        "account_id": {"type": "string", "description": "Account ID"},
        "folder": {"type": "string", "description": "Folder name (optional, defaults to inbox)"},
        "query": {"type": "string", "description": "Simple query string or IMAP criteria"},
        "unseen_only": {"type": "boolean", "description": "Only unseen messages"},
        "limit": {"type": "integer", "description": "Max results"},
    },
    ["account_id"],
)

_add(
    "email_multi_search_messages",
    "Search emails across accounts with filters. Supports: subject, from, date_since, date_until, keyword, has_attachment.",
    {
        "account_id": {"type": "string", "description": "Account ID to search (omit for all)"},
        "folder": {"type": "string", "description": "Folder name (optional)"},
        "subject": {"type": "string", "description": "Search in subject line"},
        "from": {"type": "string", "description": "Filter by sender email/domain"},
        "date_since": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
        "date_until": {"type": "string", "description": "End date (YYYY-MM-DD)"},
        "keyword": {"type": "string", "description": "Search in message body"},
        "has_attachment": {"type": "boolean", "description": "Only messages with attachments"},
        "limit": {"type": "integer", "description": "Max results (default 50)"},
    },
)

_add(
    "email_multi_read",
    "Read a specific email message. Returns headers, body text, HTML body (truncated), and attachment metadata.",
    {
        "account_id": {"type": "string", "description": "Account ID"},
        "message_id": {"type": "string", "description": "IMAP message UID"},
        "folder": {"type": "string", "description": "Folder name (optional)"},
        "include_html": {"type": "boolean", "description": "Include HTML body (default false)"},
        "download_attachments": {"type": "boolean", "description": "Download attachments to local cache"},
    },
    ["account_id", "message_id"],
)

_add(
    "email_multi_download_attachment",
    "Download one attachment from a message and return the local path.",
    {
        "account_id": {"type": "string", "description": "Account ID"},
        "message_id": {"type": "string", "description": "IMAP message UID"},
        "attachment_id": {"type": "string", "description": "Attachment filename or numeric index as string"},
        "folder": {"type": "string", "description": "Folder name (optional)"},
    },
    ["account_id", "message_id", "attachment_id"],
)

_add(
    "email_multi_send",
    "Send an email from a configured account. Supports plain text or HTML body, plus file attachments.",
    {
        "account_id": {"type": "string", "description": "Sender account ID"},
        "to": {"type": "array", "items": {"type": "string"}, "description": "Recipient email addresses"},
        "cc": {"type": "array", "items": {"type": "string"}, "description": "CC recipients"},
        "bcc": {"type": "array", "items": {"type": "string"}, "description": "BCC recipients"},
        "subject": {"type": "string", "description": "Email subject"},
        "body": {"type": "string", "description": "Plain text body"},
        "html_body": {"type": "string", "description": "HTML body (optional)"},
        "attachments": {"type": "array", "items": {"type": "string"}, "description": "File paths or MEDIA:/path attachments"},
    },
    ["account_id", "to", "subject", "body"],
)

_add(
    "email_multi_reply",
    "Reply to an email (in thread). Uses In-Reply-To and References headers for threading.",
    {
        "account_id": {"type": "string", "description": "Account ID"},
        "message_id": {"type": "string", "description": "Original message UID"},
        "folder": {"type": "string", "description": "Folder name (optional)"},
        "body": {"type": "string", "description": "Reply text"},
        "html_body": {"type": "string", "description": "Optional HTML reply body"},
        "reply_all": {"type": "boolean", "description": "Reply to all recipients"},
        "attachments": {"type": "array", "items": {"type": "string"}, "description": "File paths or MEDIA:/path attachments"},
    },
    ["account_id", "message_id", "body"],
)

_add(
    "email_multi_list_folders",
    "List IMAP folders for one account.",
    {
        "account_id": {"type": "string", "description": "Account ID"},
    },
    ["account_id"],
)

_add(
    "email_multi_mark_seen",
    "Mark a message as seen.",
    {
        "account_id": {"type": "string", "description": "Account ID"},
        "message_id": {"type": "string", "description": "IMAP message UID"},
        "folder": {"type": "string", "description": "Folder name (optional)"},
    },
    ["account_id", "message_id"],
)

_add(
    "email_multi_delete_message",
    "Delete a message (move to trash / expunge in selected folder).",
    {
        "account_id": {"type": "string", "description": "Account ID"},
        "message_id": {"type": "string", "description": "IMAP message UID"},
        "folder": {"type": "string", "description": "Folder name (optional)"},
    },
    ["account_id", "message_id"],
)
