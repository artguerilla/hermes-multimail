"""Core IMAP/SMTP service — multi-account email operations.

Mirrors the Hermes gateway EmailAdapter behavior but supports
multiple accounts identified by account_id.
"""

import email as email_lib
import imaplib
import logging
import re
import smtplib
import ssl
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, parseaddr
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .config import get_account
from .parsing import (
    decode_header_value,
    extract_email_address,
    extract_html_body,
    extract_message_headers,
    extract_text_body,
    is_automated_sender,
)
from .attachments import extract_attachments

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 50_000
HEADER_FETCH_BATCH_SIZE = 100
FULL_FETCH_BATCH_SIZE = 25
GMAIL_RAW_CAPABILITY = "X-GM-EXT-1"
GMAIL_IMAP_HOSTS = {"imap.gmail.com", "imap.googlemail.com"}


def _get_imap(acc: dict) -> imaplib.IMAP4_SSL:
    """Create and login to IMAP connection."""
    imap = imaplib.IMAP4_SSL(acc["imap_host"], acc["imap_port"], timeout=30)
    imap.login(acc["email"], acc["password"])
    _send_imap_id(imap)
    return imap


def _get_smtp(acc: dict) -> smtplib.SMTP:
    """Create and login to SMTP connection."""
    smtp = smtplib.SMTP(acc["smtp_host"], acc["smtp_port"], timeout=30)
    smtp.starttls(context=ssl.create_default_context())
    smtp.login(acc["email"], acc["password"])
    return smtp


def _send_imap_id(imap: imaplib.IMAP4) -> None:
    """Send RFC 2971 IMAP ID command (best-effort)."""
    try:
        imap.xatom(
            "ID",
            '("name" "hermes-email-multi" "version" "1.0.0" '
            '"vendor" "frankieandfriends")',
        )
    except Exception:
        pass


Uid = Union[bytes, str]


def _uid_text(uid: Uid) -> str:
    return uid.decode() if isinstance(uid, bytes) else str(uid)


def _uid_set(uids: List[Uid]) -> str:
    return ",".join(_uid_text(uid) for uid in uids)


def _chunks(items: List[Uid], size: int) -> List[List[Uid]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _parse_fetch_uid(meta: bytes) -> Optional[str]:
    match = re.search(rb"\bUID\s+(\d+)\b", meta)
    return match.group(1).decode() if match else None


def _parse_fetch_flags(meta: bytes) -> List[str]:
    match = re.search(rb"\bFLAGS\s+\(([^)]*)\)", meta)
    if not match:
        return []
    return [flag for flag in match.group(1).decode(errors="replace").split() if flag]


def _parse_fetch_size(meta: bytes) -> int:
    match = re.search(rb"\bRFC822\.SIZE\s+(\d+)\b", meta)
    if not match:
        return 0
    try:
        return int(match.group(1))
    except ValueError:
        return 0


def _capability_tokens(data: Any) -> List[str]:
    if not data:
        return []

    tokens: List[str] = []
    for item in data:
        if isinstance(item, bytes):
            text = item.decode("ascii", errors="ignore")
        else:
            text = str(item)
        tokens.extend(part.upper() for part in text.split())
    return tokens


def _has_gmail_capability(imap: imaplib.IMAP4) -> bool:
    cached = getattr(imap, "capabilities", ())
    if GMAIL_RAW_CAPABILITY in _capability_tokens(cached):
        return True

    try:
        status, data = imap.capability()
    except Exception:
        return False
    if status != "OK":
        return False
    return GMAIL_RAW_CAPABILITY in _capability_tokens(data)


def _is_gmail_compatible(imap: imaplib.IMAP4, acc: dict) -> bool:
    host = str(acc.get("imap_host", "")).lower()
    return host in GMAIL_IMAP_HOSTS or _has_gmail_capability(imap)


def _quote_imap_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _search_uids(
    imap: imaplib.IMAP4,
    criteria: str,
    fallback_criteria: Optional[str] = None,
    gmail_raw_query: Optional[str] = None,
    acc: Optional[dict] = None,
) -> List[bytes]:
    """Search UIDs, retrying without optional narrowing if the server rejects it."""
    if gmail_raw_query and acc and _is_gmail_compatible(imap, acc):
        gmail_criteria = f"X-GM-RAW {_quote_imap_string(gmail_raw_query)}"
        status, data = imap.uid("search", None, gmail_criteria)
        if status == "OK":
            if not data or not data[0]:
                return []
            return data[0].split()
        logger.info("[email-multi] Gmail X-GM-RAW search rejected %r; retrying portable %r", gmail_raw_query, criteria)

    status, data = imap.uid("search", None, criteria)
    if status != "OK" and fallback_criteria and fallback_criteria != criteria:
        logger.info("[email-multi] IMAP search rejected %r; retrying %r", criteria, fallback_criteria)
        status, data = imap.uid("search", None, fallback_criteria)
    if status != "OK" or not data or not data[0]:
        return []
    return data[0].split()


def _fetch_uid_data(imap: imaplib.IMAP4, uids: List[Uid], fetch_spec: str) -> List[Any]:
    status, msg_data = imap.uid("fetch", _uid_set(uids), fetch_spec)
    if status == "OK" and msg_data:
        return msg_data
    if len(uids) <= 1:
        return []

    logger.info("[email-multi] Batched UID FETCH rejected; retrying %d UIDs individually", len(uids))
    rows = []
    for uid in uids:
        status, msg_data = imap.uid("fetch", _uid_text(uid), fetch_spec)
        if status == "OK" and msg_data:
            rows.extend(msg_data)
    return rows


def _fetch_headers(
    imap: imaplib.IMAP4,
    uids: List[Uid],
) -> Dict[str, Dict[str, Any]]:
    headers_by_uid: Dict[str, Dict[str, Any]] = {}
    for batch in _chunks(uids, HEADER_FETCH_BATCH_SIZE):
        msg_data = _fetch_uid_data(imap, batch, "(UID RFC822.HEADER FLAGS RFC822.SIZE)")
        if not msg_data:
            continue

        for part in msg_data:
            if not isinstance(part, tuple):
                continue
            meta = part[0] if isinstance(part[0], bytes) else b""
            header_bytes = part[1]
            uid = _parse_fetch_uid(meta)
            if not uid or not header_bytes:
                continue

            msg = email_lib.message_from_bytes(header_bytes)
            hdrs = extract_message_headers(msg)
            hdrs["uid"] = uid
            hdrs["flags"] = _parse_fetch_flags(meta)
            hdrs["size"] = _parse_fetch_size(meta)
            headers_by_uid[uid] = hdrs
    return headers_by_uid


def _message_from_raw(
    raw: bytes,
    uid: str,
    meta: bytes = b"",
    include_body: bool = True,
    include_attachments: bool = True,
    save_dir: Optional[str] = None,
    acc: Optional[dict] = None,
) -> Dict[str, Any]:
    msg = email_lib.message_from_bytes(raw)
    result = {
        "uid": uid,
        **extract_message_headers(msg),
    }

    if meta:
        result["flags"] = _parse_fetch_flags(meta)
        result["size"] = _parse_fetch_size(meta)

    if include_body:
        result["body_text"] = extract_text_body(msg)
        result["body_html"] = extract_html_body(msg)
        if len(result["body_text"]) > MAX_MESSAGE_LENGTH:
            result["body_text"] = result["body_text"][:MAX_MESSAGE_LENGTH] + "\n\n... [truncated]"

    if include_attachments:
        result["attachments"] = extract_attachments(
            msg,
            skip_attachments=(acc or {}).get("skip_attachments", False),
            save_dir=save_dir,
        )

    return result


def _fetch_full_messages(
    imap: imaplib.IMAP4,
    uids: List[Uid],
    acc: dict,
    include_body: bool = True,
    include_attachments: bool = True,
    save_dir: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    messages_by_uid: Dict[str, Dict[str, Any]] = {}
    for batch in _chunks(uids, FULL_FETCH_BATCH_SIZE):
        msg_data = _fetch_uid_data(imap, batch, "(UID RFC822 FLAGS RFC822.SIZE)")
        if not msg_data:
            continue

        for part in msg_data:
            if not isinstance(part, tuple):
                continue
            meta = part[0] if isinstance(part[0], bytes) else b""
            raw = part[1]
            uid = _parse_fetch_uid(meta)
            if not uid or not raw:
                continue
            messages_by_uid[uid] = _message_from_raw(
                raw,
                uid,
                meta=meta,
                include_body=include_body,
                include_attachments=include_attachments,
                save_dir=save_dir,
                acc=acc,
            )
    return messages_by_uid


def list_folders(account_id: str) -> List[Dict[str, Any]]:
    """List IMAP folders for an account."""
    acc = get_account(account_id)
    if not acc:
        raise ValueError(f"Account not found: {account_id}")

    imap = _get_imap(acc)
    try:
        status, data = imap.list()
        if status != "OK":
            return []
        folders = []
        for item in data:
            if isinstance(item, bytes):
                # Decode folder name (may use non-UTF8)
                parts = item.split(b'"')
                if len(parts) >= 4:
                    name = parts[-2].decode("utf-8", errors="replace")
                else:
                    name = item.decode("utf-8", errors="replace")
                folders.append({"name": name, "flags": []})
        return folders
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def search_messages(
    account_id: str,
    folder: Optional[str] = None,
    criteria: str = "UNSEEN",
    limit: int = 50,
    fallback_criteria: Optional[str] = None,
    gmail_raw_query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search messages and return lightweight headers."""
    acc = get_account(account_id)
    if not acc:
        raise ValueError(f"Account not found: {account_id}")

    folder = folder or acc["folders"]["inbox"]
    imap = _get_imap(acc)
    try:
        imap.select(folder, readonly=True)
        uids = _search_uids(
            imap,
            criteria,
            fallback_criteria=fallback_criteria,
            gmail_raw_query=gmail_raw_query,
            acc=acc,
        )
        selected = uids[-limit:]
        headers_by_uid = _fetch_headers(imap, selected)
        return [
            headers_by_uid[_uid_text(uid)]
            for uid in reversed(selected)
            if _uid_text(uid) in headers_by_uid
        ]
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def get_message(
    account_id: str,
    message_uid: str,
    folder: Optional[str] = None,
    include_body: bool = True,
    include_attachments: bool = True,
    save_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch a full message by UID."""
    acc = get_account(account_id)
    if not acc:
        raise ValueError(f"Account not found: {account_id}")

    folder = folder or acc["folders"]["inbox"]
    imap = _get_imap(acc)
    try:
        imap.select(folder, readonly=True)
        status, data = imap.uid("fetch", message_uid, "(UID RFC822 FLAGS RFC822.SIZE)")
        if status != "OK":
            raise RuntimeError(f"Failed to fetch message {message_uid}: {status}")

        for part in data:
            if isinstance(part, tuple):
                meta = part[0] if isinstance(part[0], bytes) else b""
                uid = _parse_fetch_uid(meta) or message_uid
                return _message_from_raw(
                    part[1],
                    uid,
                    meta=meta,
                    include_body=include_body,
                    include_attachments=include_attachments,
                    save_dir=save_dir,
                    acc=acc,
                )
        raise RuntimeError(f"Failed to fetch message {message_uid}: empty response")
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def search_full_messages(
    account_id: str,
    folder: Optional[str] = None,
    criteria: str = "UNSEEN",
    limit: int = 50,
    fallback_criteria: Optional[str] = None,
    gmail_raw_query: Optional[str] = None,
    include_body: bool = True,
    include_attachments: bool = True,
    save_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search and fetch full messages using one IMAP session for the account."""
    acc = get_account(account_id)
    if not acc:
        raise ValueError(f"Account not found: {account_id}")

    folder = folder or acc["folders"]["inbox"]
    imap = _get_imap(acc)
    try:
        imap.select(folder, readonly=True)
        uids = _search_uids(
            imap,
            criteria,
            fallback_criteria=fallback_criteria,
            gmail_raw_query=gmail_raw_query,
            acc=acc,
        )
        selected = uids[-limit:]
        messages_by_uid = _fetch_full_messages(
            imap,
            selected,
            acc=acc,
            include_body=include_body,
            include_attachments=include_attachments,
            save_dir=save_dir,
        )
        return [
            messages_by_uid[_uid_text(uid)]
            for uid in reversed(selected)
            if _uid_text(uid) in messages_by_uid
        ]
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def send_email(
    account_id: str,
    to: List[str],
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    attachments: Optional[List[str]] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
) -> str:
    """Send an email. Returns Message-ID."""
    acc = get_account(account_id)
    if not acc:
        raise ValueError(f"Account not found: {account_id}")

    domain = acc["email"].split("@")[1]
    msg_id = f"<hermes-{uuid.uuid4().hex[:12]}@{domain}>"

    if body_html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))
    else:
        msg = MIMEMultipart() if attachments else MIMEText(body_text, "plain", "utf-8")
        if attachments:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))

    msg["From"] = acc["email"]
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = msg_id

    if cc:
        msg["Cc"] = ", ".join(cc)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    # Attach files
    if attachments:
        for file_path in attachments:
            from .attachments import create_attachment_part
            msg.attach(create_attachment_part(file_path))

    all_recipients = list(to)
    if cc:
        all_recipients.extend(cc)
    if bcc:
        all_recipients.extend(bcc)

    smtp = _get_smtp(acc)
    try:
        smtp.send_message(msg, from_addr=acc["email"], to_addrs=all_recipients)
    finally:
        try:
            smtp.quit()
        except Exception:
            smtp.close()

    logger.info("[email-multi] Sent from %s to %s (subject: %s)", account_id, to, subject)
    return msg_id


def reply_email(
    account_id: str,
    original_uid: str,
    body_text: str,
    body_html: Optional[str] = None,
    reply_all: bool = False,
    attachments: Optional[List[str]] = None,
    folder: Optional[str] = None,
) -> str:
    """Reply to an existing email."""
    acc = get_account(account_id)
    folder = folder or acc["folders"]["inbox"]

    imap = _get_imap(acc)
    try:
        imap.select(folder, readonly=True)
        status, data = imap.uid("fetch", original_uid, "(RFC822)")
        if status != "OK":
            raise RuntimeError(f"Failed to fetch original message: {status}")

        raw = data[0][1]
        orig_msg = email_lib.message_from_bytes(raw)

        subject = decode_header_value(orig_msg.get("Subject", ""))
        if not subject.startswith("Re:"):
            subject = f"Re: {subject}"

        in_reply_to = orig_msg.get("Message-ID", "")
        references = orig_msg.get("References", "") or in_reply_to

        if reply_all:
            to_addrs = extract_all_reply_addresses(orig_msg, exclude=acc["email"])
        else:
            # Reply to sender only
            from_addr = orig_msg.get("From", "")
            to_addrs = [extract_email_address(from_addr)]

        return send_email(
            account_id=account_id,
            to=to_addrs,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            in_reply_to=in_reply_to,
            references=references,
        )
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def extract_all_reply_addresses(orig_msg, exclude: str = "") -> List[str]:
    """Extract Reply-To or From address, plus Cc for reply-all."""
    exclude = exclude.lower()
    addresses = []

    # Reply-To first
    reply_to = orig_msg.get("Reply-To", "")
    if reply_to:
        import re
        for m in re.finditer(r"<([^>]+)>", reply_to):
            addr = m.group(1).lower()
            if addr != exclude:
                addresses.append(m.group(1))

    # If no Reply-To, use From
    if not addresses:
        from_addr = orig_msg.get("From", "")
        import re
        for m in re.finditer(r"<([^>]+)>", from_addr):
            addr = m.group(1).lower()
            if addr != exclude:
                addresses.append(m.group(1))

    # Add Cc recipients for reply-all
    cc = orig_msg.get("Cc", "")
    if cc:
        import re
        for m in re.finditer(r"<([^>]+)>", cc):
            addr = m.group(1).lower()
            if addr != exclude and m.group(1) not in addresses:
                addresses.append(m.group(1))

    return addresses if addresses else ["unknown@nowhere"]


def mark_seen(account_id: str, message_uid: str, folder: Optional[str] = None) -> bool:
    """Mark a message as seen (remove \\Seen flag)."""
    acc = get_account(account_id)
    folder = folder or acc["folders"]["inbox"]
    imap = _get_imap(acc)
    try:
        imap.select(folder)
        status, _ = imap.uid("store", message_uid, "+FLAGS", "\\Seen")
        return status == "OK"
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def delete_message(account_id: str, message_uid: str, folder: Optional[str] = None) -> bool:
    """Move message to trash."""
    acc = get_account(account_id)
    folder = folder or acc["folders"]["inbox"]
    imap = _get_imap(acc)
    try:
        imap.select(folder)
        status, _ = imap.uid("store", message_uid, "+FLAGS", "\\Deleted")
        if status == "OK":
            imap.expunge()
        return status == "OK"
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def check_account(account_id: str) -> Dict[str, Any]:
    """Test IMAP and SMTP connectivity for an account."""
    acc = get_account(account_id)
    if not acc:
        raise ValueError(f"Account not found: {account_id}")

    result = {"account_id": account_id, "imap": False, "smtp": False}

    try:
        imap = _get_imap(acc)
        imap.select(acc["folders"]["inbox"], readonly=True)
        status, data = imap.uid("search", None, "ALL")
        count = len(data[0].split()) if data and data[0] else 0
        result["imap"] = True
        result["message_count"] = count
        imap.logout()
    except Exception as e:
        result["imap_error"] = str(e)

    try:
        smtp = _get_smtp(acc)
        result["smtp"] = True
        smtp.quit()
    except Exception as e:
        result["smtp_error"] = str(e)

    return result


def check_allowed(account_id: str, sender_addr: str) -> bool:
    """Check if a sender is allowed to interact with this account."""
    acc = get_account(account_id)
    if not acc:
        return False
    if acc.get("allow_all", False):
        return True
    allowed = [a.lower() for a in acc.get("allowed_users", [])]
    if not allowed:
        # Match Hermes' practical default: if no allow-list is configured, don't block local/operator use.
        return True
    return sender_addr.lower() in allowed
