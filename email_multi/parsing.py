"""Email parsing utilities — HTML→text, body extraction, header decoding.

Mirrors the Hermes gateway email adapter behavior.
"""

import email as email_lib
import re
from email.header import decode_header
from email.utils import getaddresses, parseaddr
from typing import List


def decode_header_value(raw: str) -> str:
    """Decode an RFC 2047 encoded email header into a plain string."""
    if not raw:
        return ""
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def extract_email_address(raw: str) -> str:
    """Extract bare email address from 'Name <addr>' or bare format."""
    if not raw:
        return ""
    _, addr = parseaddr(raw)
    return addr.strip().lower() if addr else raw.strip().lower()


def parse_address_list(raw: str) -> List[str]:
    """Parse a comma-separated address header into lowercase email addresses.

    Handles both 'Display Name <addr@example.com>' and bare 'addr@example.com'
    formats using the standard library parser.
    """
    if not raw:
        return []
    pairs = getaddresses([raw])
    return [addr.lower() for _, addr in pairs if addr and "@" in addr]


def extract_text_body(msg: email_lib.message.Message) -> str:
    """Extract plain-text body, falling back to HTML→text."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        # Fallback: HTML
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if content_type == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    return html_to_text(html)
        return ""
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                return html_to_text(text)
            return text
        return ""


def extract_html_body(msg: email_lib.message.Message) -> str:
    """Extract HTML body if available."""
    if not msg.is_multipart():
        if msg.get_content_type() == "text/html":
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        return ""

    for part in msg.walk():
        content_type = part.get_content_type()
        disposition = str(part.get("Content-Disposition", ""))
        if "attachment" in disposition:
            continue
        if content_type == "text/html":
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
    return ""


def html_to_text(html: str) -> str:
    """Naive HTML tag stripper for fallback text extraction."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_message_headers(msg: email_lib.message.Message) -> dict:
    """Extract common headers from a message."""
    return {
        "subject": decode_header_value(msg.get("Subject", "(no subject)")),
        "from": msg.get("From", ""),
        "from_addr": extract_email_address(msg.get("From", "")),
        "from_name": decode_header_value(msg.get("From", "")),
        "to": msg.get("To", ""),
        "to_addrs": _extract_all_addresses(msg.get("To", "")),
        "cc": msg.get("Cc", ""),
        "cc_addrs": _extract_all_addresses(msg.get("Cc", "")),
        "date": msg.get("Date", ""),
        "message_id": msg.get("Message-ID", ""),
        "in_reply_to": msg.get("In-Reply-To", ""),
        "references": msg.get("References", ""),
    }


def _extract_all_addresses(raw: str) -> List[str]:
    """Extract all email addresses from a To/Cc header."""
    return parse_address_list(raw)


# Automated sender detection (from Hermes adapter)
_NOREPLY_PATTERNS = (
    "noreply", "no-reply", "no_reply", "donotreply", "do-not-reply",
    "mailer-daemon", "postmaster", "bounce", "notifications@",
    "automated@", "auto-confirm", "auto-reply", "automailer",
)

_AUTOMATED_HEADERS = {
    "Auto-Submitted": lambda v: v.lower() != "no",
    "Precedence": lambda v: v.lower() in {"bulk", "list", "junk"},
    "X-Auto-Response-Suppress": lambda v: bool(v),
    "List-Unsubscribe": lambda v: bool(v),
}


def is_automated_sender(address: str, headers: dict) -> bool:
    """Check if sender is automated/noreply."""
    addr = address.lower()
    if any(pattern in addr for pattern in _NOREPLY_PATTERNS):
        return True
    for header, check in _AUTOMATED_HEADERS.items():
        value = headers.get(header, "")
        if value and check(value):
            return True
    return False
