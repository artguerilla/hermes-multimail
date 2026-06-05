"""Tool schemas for the email_multi plugin.

Each schema defines a tool that Hermes LLM agents can call to interact with
email accounts. All tools require an `account_id` (except list_accounts) —
this is the key identifier for switching between mailboxes.

IMPORTANT for LLM usage:
- Always call `email_multi_list_accounts` first to discover available accounts
  and their `account_id` values.
- Use `account_id` to target a specific mailbox in all subsequent calls.
- To operate across multiple inboxes, call tools with different `account_id` values.
- The `account_id` matches the `account_id` field in `accounts.yaml`.
"""

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
    "List all configured email accounts with their connection status. "
    "Returns account_id, email address, IMAP/SMTP host, whether a password "
    "is configured, access control settings, and health checks. "
    "Use this FIRST to discover available mailboxes and their account_id "
    "values before calling any other email tool. No parameters required.",
    {},
)


_add(
    "email_multi_poll_inbox",
    "Poll for new unseen emails across all configured accounts (or a single "
    "one). Returns message summaries with subject, sender, date, and flags. "
    "Pass `account_id` to poll a specific mailbox; omit to poll all "
    "accessible accounts simultaneously. "
    "Use this to check for new mail without reading full message content.",
    {
        "account_id": {
            "type": "string",
            "description": (
                "Poll only this specific account. Omit to poll all accessible "
                "accounts. Use account_id from email_multi_list_accounts."
            ),
        },
        "limit": {
            "type": "integer",
            "description": "Maximum messages per account (default 20).",
        },
    },
)


_add(
    "email_multi_list_messages",
    "List messages from a specific folder within one account. "
    "Requires `account_id` — use email_multi_list_accounts to find valid IDs. "
    "Defaults to INBOX if no folder is specified. Supports IMAP SEARCH "
    "criteria: filter by subject, sender, date range, read/unread status, "
    "keywords, and attachment presence. "
    "Use `account_id` to switch between different mailboxes. "
    "Returns lightweight message headers (not full bodies).",
    {
        "account_id": {
            "type": "string",
            "description": (
                "The account to query. Required. Get valid IDs from "
                "email_multi_list_accounts."
            ),
        },
        "folder": {
            "type": "string",
            "description": (
                "IMAP folder name (e.g., 'INBOX', '[Gmail]/Sent Mail'). "
                "Defaults to INBOX. Use email_multi_list_folders to discover."
            ),
        },
        "query": {
            "type": "string",
            "description": (
                "Raw IMAP SEARCH criteria (e.g., 'UNSEEN', 'FROM \"user@x.com\"'). "
                "Use structured filters below for most cases."
            ),
        },
        "unseen_only": {
            "type": "boolean",
            "description": "Only return unread messages (UNSEEN flag).",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum results (default 50).",
        },
    },
    ["account_id"],
)


_add(
    "email_multi_search_messages",
    "Search emails across one or all accounts with rich filters. "
    "This is the most powerful search tool — fetches full message bodies "
    "(truncated to 500 chars in results) and attachment metadata. "
    "\n\n"
    "Account targeting:\n"
    "- Pass `account_id` to search a specific mailbox only.\n"
    "- Omit `account_id` to search ALL accessible accounts at once. "
    "Results include `account_id` so you know which mailbox each hit came from.\n\n"
    "Filters:\n"
    "- `subject`: search email subject lines.\n"
    "- `from`: filter by sender address or domain (e.g., 'billing@' or 'gmail.com').\n"
    "- `date_since` / `date_until`: date range in YYYY-MM-DD format.\n"
    "- `keyword`: full-text search across subject, sender, and decoded text body. "
    "ASCII keywords are narrowed server-side first (IMAP TEXT), then verified "
    "client-side. Non-ASCII keywords use client-side fallback.\n"
    "- `has_attachment`: only messages that include attachments.\n\n"
    "Use `email_multi_read` with the returned `uid` to get the full message.",
    {
        "account_id": {
            "type": "string",
            "description": (
                "Search within a specific account. Omit to search ALL accessible "
                "accounts. Results include account_id for multi-account disambiguation."
            ),
        },
        "folder": {
            "type": "string",
            "description": "Search within a specific folder (defaults to INBOX).",
        },
        "subject": {
            "type": "string",
            "description": "Search text in the email subject line.",
        },
        "from": {
            "type": "string",
            "description": (
                "Filter by sender — full email, partial address, or domain "
                "(e.g., 'user@gmail.com', 'billing@', 'gmail.com')."
            ),
        },
        "date_since": {
            "type": "string",
            "description": "Start date in YYYY-MM-DD format (inclusive).",
        },
        "date_until": {
            "type": "string",
            "description": "End date in YYYY-MM-DD format (inclusive).",
        },
        "keyword": {
            "type": "string",
            "description": (
                "Search text across subject, sender, and decoded message body. "
                "ASCII keywords use server-side IMAP TEXT search for performance."
            ),
        },
        "has_attachment": {
            "type": "boolean",
            "description": "Only return messages with file attachments.",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum results per account (default 50).",
        },
    },
)


_add(
    "email_multi_read",
    "Read a full email message by its UID (unique message identifier). "
    "Returns all headers, decoded text body, and attachment metadata. "
    "Set `download_attachments: true` to save attachments locally — "
    "they are cached under the Hermes home directory. "
    "Set `include_html: true` to also get the raw HTML body. "
    "Use `account_id` to specify which mailbox the message belongs to. "
    "Get the UID from email_multi_list_messages or email_multi_search_messages results.",
    {
        "account_id": {
            "type": "string",
            "description": (
                "The mailbox containing the message. Required. Use the same "
                "account_id returned by list/search tools."
            ),
        },
        "message_id": {
            "type": "string",
            "description": (
                "IMAP message UID (unique identifier). Get from list_messages "
                "or search_messages results — it is the 'uid' field."
            ),
        },
        "folder": {
            "type": "string",
            "description": (
                "IMAP folder name if the message is not in INBOX. "
                "Defaults to INBOX."
            ),
        },
        "include_html": {
            "type": "boolean",
            "description": "Include raw HTML body alongside text body (default: false).",
        },
        "download_attachments": {
            "type": "boolean",
            "description": (
                "Save attachments to local disk. Files are cached under "
                "$HERMES_HOME/cache/email_multi/<account_id>/<uid>/."
            ),
        },
    },
    ["account_id", "message_id"],
)


_add(
    "email_multi_download_attachment",
    "Download a single attachment from a specific email message. "
    "Identify the attachment by filename or numeric index (0-based). "
    "Returns the local file path after download. "
    "Use email_multi_read first to see available attachments.",
    {
        "account_id": {
            "type": "string",
            "description": "The mailbox containing the message.",
        },
        "message_id": {
            "type": "string",
            "description": "IMAP message UID of the message containing the attachment.",
        },
        "attachment_id": {
            "type": "string",
            "description": (
                "Either the exact filename (e.g., 'invoice.pdf') or a 0-based "
                "numeric index (e.g., '0' for first attachment). Check available "
                "attachments via email_multi_read first."
            ),
        },
        "folder": {
            "type": "string",
            "description": "IMAP folder if message is not in INBOX.",
        },
    },
    ["account_id", "message_id", "attachment_id"],
)


_add(
    "email_multi_send",
    "Send a new email from a configured account. Supports plain text, "
    "HTML (via `html_body`), CC/BCC recipients, and file attachments. "
    "The sender address is determined by the `account_id` — choose the "
    "mailbox whose email address should appear in the From: header. "
    "Attachments accept local file paths or MEDIA:/path references. "
    "Returns the Message-ID of the sent email.",
    {
        "account_id": {
            "type": "string",
            "description": (
                "Sender mailbox. Determines the From: address. "
                "Choose from email_multi_list_accounts."
            ),
        },
        "to": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of recipient email addresses.",
        },
        "cc": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of CC recipient addresses (optional).",
        },
        "bcc": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of BCC recipient addresses (optional).",
        },
        "subject": {
            "type": "string",
            "description": "Email subject line.",
        },
        "body": {
            "type": "string",
            "description": "Plain text message body.",
        },
        "html_body": {
            "type": "string",
            "description": "HTML message body (optional). Sent as multipart/alternative.",
        },
        "attachments": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "File paths or MEDIA:/path references to attach. "
                "e.g., ['/tmp/report.pdf', 'MEDIA:/path/to/image.png']"
            ),
        },
    },
    ["account_id", "to", "subject", "body"],
)


_add(
    "email_multi_reply",
    "Reply to an existing email message. Automatically sets In-Reply-To "
    "and References headers for proper threading. "
    "Use `reply_all: true` to include all To: and Cc: recipients "
    "(the original sender is always included). "
    "The reply is sent from the account that received the original message. "
    "Supports plain text, HTML, CC/BCC, and file attachments. "
    "Returns the Message-ID of the reply.",
    {
        "account_id": {
            "type": "string",
            "description": (
                "The mailbox that received the original message. "
                "Use the account_id from the original message."
            ),
        },
        "message_id": {
            "type": "string",
            "description": (
                "IMAP UID of the message you are replying to. "
                "Used for In-Reply-To and References threading headers."
            ),
        },
        "folder": {
            "type": "string",
            "description": "IMAP folder if original message is not in INBOX.",
        },
        "body": {
            "type": "string",
            "description": "Reply text body.",
        },
        "html_body": {
            "type": "string",
            "description": "HTML reply body (optional).",
        },
        "reply_all": {
            "type": "boolean",
            "description": (
                "Reply to all original recipients (To + Cc). "
                "Default: false (reply to sender only)."
            ),
        },
        "attachments": {
            "type": "array",
            "items": {"type": "string"},
            "description": "File paths or MEDIA:/path references to attach.",
        },
    },
    ["account_id", "message_id", "body"],
)


_add(
    "email_multi_list_folders",
    "List all IMAP mailboxes (folders) for a specific account. "
    "Returns folder names and their IMAP flags (e.g., \\Inbox, \\Sent, \\Trash). "
    "Use this to discover valid folder names for use in other tools. "
    "Note: Gmail uses bracketed names like '[Gmail]/Sent Mail'.",
    {
        "account_id": {
            "type": "string",
            "description": "The account whose folders to list.",
        },
    },
    ["account_id"],
)


_add(
    "email_multi_mark_seen",
    "Mark a message as read (set the \\Seen flag). "
    "Use this after reading a message to prevent it from appearing as unread "
    "in future polls or UNSEEN searches.",
    {
        "account_id": {
            "type": "string",
            "description": "The mailbox containing the message.",
        },
        "message_id": {
            "type": "string",
            "description": "IMAP UID of the message to mark as seen.",
        },
        "folder": {
            "type": "string",
            "description": "IMAP folder if message is not in INBOX.",
        },
    },
    ["account_id", "message_id"],
)


_add(
    "email_multi_delete_message",
    "Delete a message by moving it to the Trash folder (or expunging if "
    "already in Trash). "
    "Behavior depends on the current folder:\n"
    "- If message is in INBOX or another non-Trash folder: copies to Trash "
    "folder, then removes from original folder.\n"
    "- If message is already in Trash: sets Deleted flag and expunges.\n\n"
    "This is a destructive operation. Use email_multi_read first to confirm "
    "the message before deleting.",
    {
        "account_id": {
            "type": "string",
            "description": "The mailbox containing the message.",
        },
        "message_id": {
            "type": "string",
            "description": "IMAP UID of the message to delete.",
        },
        "folder": {
            "type": "string",
            "description": (
                "IMAP folder if message is not in INBOX. "
                "Defaults to INBOX."
            ),
        },
    },
    ["account_id", "message_id"],
)
