"""Core IMAP/SMTP service — multi-account email operations.

Mirrors the Hermes gateway EmailAdapter behavior but supports
multiple accounts identified by account_id.
"""

import email as email_lib
import imaplib
import logging
import re
import shlex
import smtplib
import ssl
import time
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from typing import Any, Dict, List, Optional, Tuple, Union

from .attachments import extract_attachments
from .config import get_account
from .parsing import (
    decode_header_value,
    extract_email_address,
    extract_html_body,
    extract_message_headers,
    extract_text_body,
    parse_address_list,
)

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 50_000
HEADER_FETCH_BATCH_SIZE = 100
FULL_FETCH_BATCH_SIZE = 25
DEFAULT_AUTH_FAILURE_COOLDOWN_SECONDS = 300
_AUTH_FAILURES: Dict[Tuple[str, str, str, str], float] = {}


class AuthRetrySuppressed(RuntimeError):
    """Raised when a recent auth failure makes another login attempt unsafe."""


def _get_imap(acc: dict) -> imaplib.IMAP4_SSL:
    """Create and login to IMAP connection."""
    _assert_auth_retry_allowed(acc, "imap")
    imap = imaplib.IMAP4_SSL(
        acc["imap_host"],
        acc["imap_port"],
        ssl_context=ssl.create_default_context(),
        timeout=30,
    )
    try:
        imap.login(acc["email"], acc["password"])
    except imaplib.IMAP4.error:
        _record_auth_failure(acc, "imap")
        try:
            imap.logout()
        except Exception:
            pass
        raise

    _clear_auth_failure(acc, "imap")
    _send_imap_id(imap)
    return imap


def _get_smtp(acc: dict) -> smtplib.SMTP:
    """Create and login to SMTP connection."""
    _assert_auth_retry_allowed(acc, "smtp")
    smtp = smtplib.SMTP(
        acc["smtp_host"],
        acc["smtp_port"],
        local_hostname=_smtp_local_hostname(acc),
        timeout=30,
    )
    try:
        smtp.ehlo()
        if not smtp.has_extn("starttls"):
            raise smtplib.SMTPNotSupportedError("SMTP server does not advertise STARTTLS")
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(acc["email"], acc["password"])
    except smtplib.SMTPAuthenticationError:
        _record_auth_failure(acc, "smtp")
        smtp.close()
        raise
    except Exception:
        smtp.close()
        raise

    _clear_auth_failure(acc, "smtp")
    return smtp


def _auth_key(acc: dict, protocol: str) -> Tuple[str, str, str, str]:
    return (
        protocol,
        str(acc.get("email", "")).lower(),
        str(acc.get(f"{protocol}_host", "")).lower(),
        str(acc.get(f"{protocol}_port", "")),
    )


def _auth_cooldown_seconds(acc: dict) -> int:
    try:
        return max(0, int(acc.get("auth_failure_cooldown_seconds", DEFAULT_AUTH_FAILURE_COOLDOWN_SECONDS)))
    except (TypeError, ValueError):
        return DEFAULT_AUTH_FAILURE_COOLDOWN_SECONDS


def _assert_auth_retry_allowed(acc: dict, protocol: str) -> None:
    retry_at = _AUTH_FAILURES.get(_auth_key(acc, protocol))
    if not retry_at:
        return

    wait_seconds = int(retry_at - time.monotonic())
    if wait_seconds > 0:
        account_id = acc.get("account_id") or acc.get("email") or "unknown"
        raise AuthRetrySuppressed(
            f"Recent {protocol.upper()} authentication failure for account '{account_id}'. "
            f"Suppressing retry for {wait_seconds}s to avoid provider IP blocking."
        )

    _AUTH_FAILURES.pop(_auth_key(acc, protocol), None)


def _record_auth_failure(acc: dict, protocol: str) -> None:
    cooldown = _auth_cooldown_seconds(acc)
    if cooldown > 0:
        _AUTH_FAILURES[_auth_key(acc, protocol)] = time.monotonic() + cooldown


def _clear_auth_failure(acc: dict, protocol: str) -> None:
    _AUTH_FAILURES.pop(_auth_key(acc, protocol), None)


def _smtp_local_hostname(acc: dict) -> str:
    configured = str(acc.get("smtp_local_hostname", "")).strip()
    if configured:
        return configured
    if "@" in str(acc.get("email", "")):
        return str(acc["email"]).rsplit("@", 1)[1]
    return "localhost"


def _send_imap_id(imap: imaplib.IMAP4) -> None:
    """Send RFC 2971 IMAP ID command (best-effort)."""
    try:
        imap.xatom(
            "ID",
            '("name" "hermes-multimail" "version" "1.0.2")',
        )
    except Exception:
        pass


def _quote_imap_search_value(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _quote_gmail_raw_value(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _has_gmail_account_hint(acc: Optional[dict]) -> bool:
    if not acc:
        return False
    values = [
        acc.get("imap_host", ""),
        acc.get("smtp_host", ""),
        acc.get("email", ""),
        acc.get("account_id", ""),
    ]
    return any("gmail" in str(value).lower() or "googlemail" in str(value).lower() for value in values)


def _has_gmail_capability(imap: imaplib.IMAP4) -> bool:
    capability_values = getattr(imap, "capabilities", None) or []
    joined = b" ".join(
        value if isinstance(value, bytes) else str(value).encode()
        for value in capability_values
    )
    if b"X-GM-EXT-1" in joined.upper():
        return True

    try:
        status, data = imap.capability()
    except Exception:
        return False
    if status != "OK" or not data:
        return False
    joined = b" ".join(value if isinstance(value, bytes) else str(value).encode() for value in data)
    return b"X-GM-EXT-1" in joined.upper()


def _can_use_gmail_raw_search(imap: imaplib.IMAP4, acc: Optional[dict]) -> bool:
    return _has_gmail_account_hint(acc) or _has_gmail_capability(imap)


def _gmail_raw_query_from_criteria(criteria: str) -> Optional[str]:
    """Translate a conservative subset of IMAP SEARCH criteria to Gmail raw query."""
    try:
        tokens = shlex.split(criteria)
    except ValueError:
        return None

    raw_parts: List[str] = []
    i = 0
    while i < len(tokens):
        key = tokens[i].upper()
        if key == "ALL":
            i += 1
            continue
        if key == "UNSEEN":
            raw_parts.append("is:unread")
            i += 1
            continue
        if key == "SUBJECT" and i + 1 < len(tokens):
            raw_parts.append(f"subject:{_quote_gmail_raw_value(tokens[i + 1])}")
            i += 2
            continue
        if key == "FROM" and i + 1 < len(tokens):
            raw_parts.append(f"from:{_quote_gmail_raw_value(tokens[i + 1])}")
            i += 2
            continue
        if key in {"TEXT", "BODY"} and i + 1 < len(tokens):
            raw_parts.append(_quote_gmail_raw_value(tokens[i + 1]))
            i += 2
            continue
        return None

    return " ".join(raw_parts) if raw_parts else None


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


def _search_uids(
    imap: imaplib.IMAP4,
    criteria: str,
    fallback_criteria: Optional[str] = None,
    acc: Optional[dict] = None,
) -> List[bytes]:
    """Search UIDs, retrying without optional narrowing if the server rejects it."""
    raw_query = None
    if _can_use_gmail_raw_search(imap, acc):
        raw_query = _gmail_raw_query_from_criteria(criteria)

    if raw_query:
        status, data = imap.uid("search", None, "X-GM-RAW", _quote_imap_search_value(raw_query))
        if status == "OK":
            if not data or not data[0]:
                return []
            return data[0].split()
        logger.info("[email-multi] Gmail raw search rejected %r; retrying generic %r", raw_query, criteria)

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
) -> List[Dict[str, Any]]:
    """Search messages and return lightweight headers."""
    acc = get_account(account_id)
    if not acc:
        raise ValueError(f"Account not found: {account_id}")

    folder = folder or acc["folders"]["inbox"]
    imap = _get_imap(acc)
    try:
        imap.select(folder, readonly=True)
        uids = _search_uids(imap, criteria, fallback_criteria=fallback_criteria, acc=acc)
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
        uids = _search_uids(imap, criteria, fallback_criteria=fallback_criteria, acc=acc)
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
    """Extract reply-all recipients from Reply-To/From plus To/Cc, excluding sender.

    Precedence: Reply-To > From. To and Cc recipients are appended for reply-all.
    Addresses are lowercased and deduplicated while preserving stable order.

    Raises ValueError when no valid recipients remain after exclusion.
    """
    exclude_lower = exclude.lower()
    seen: set = set()
    addresses: List[str] = []

    def _add(raw: str) -> None:
        for addr in parse_address_list(raw):
            if addr != exclude_lower and addr not in seen:
                seen.add(addr)
                addresses.append(addr)

    # Reply-To takes precedence over From
    reply_to = orig_msg.get("Reply-To", "")
    if reply_to:
        _add(reply_to)

    # Fall back to From when Reply-To contributed nothing
    if not addresses:
        _add(orig_msg.get("From", ""))

    # Include all To and Cc recipients (reply-all)
    _add(orig_msg.get("To", ""))
    _add(orig_msg.get("Cc", ""))

    if not addresses:
        raise ValueError("No valid reply recipients found after excluding sender")

    return addresses


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
    trash_folder = acc.get("folders", {}).get("trash", "Trash")
    imap = _get_imap(acc)
    try:
        imap.select(folder)
        if folder != trash_folder:
            status, _ = imap.uid("copy", message_uid, trash_folder)
            if status != "OK":
                return False
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
    skip_smtp = False

    try:
        imap = _get_imap(acc)
    except (imaplib.IMAP4.error, AuthRetrySuppressed) as e:
        result["imap_error"] = str(e)
        skip_smtp = True
    except Exception as e:
        result["imap_error"] = str(e)
    else:
        try:
            imap.select(acc["folders"]["inbox"], readonly=True)
            status, data = imap.uid("search", None, "ALL")
            count = len(data[0].split()) if data and data[0] else 0
            result["imap"] = True
            result["message_count"] = count
        except Exception as e:
            result["imap_error"] = str(e)
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    if skip_smtp:
        result["smtp_error"] = "Skipped after IMAP authentication failure to avoid provider IP blocking."
    else:
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
        # No allowlist configured — fail closed for security
        return False
    return sender_addr.lower() in allowed
