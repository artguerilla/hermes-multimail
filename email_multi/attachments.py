"""Attachment handling — download, cache, and send attachments.

Mirrors Hermes gateway adapter attachment behavior:
- Images cached to media cache
- Documents cached to file cache
- Attachments sent as MIMEBase parts
"""

import mimetypes
from email.header import decode_header
from email.mime.application import MIMEApplication
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from pathlib import Path
from typing import Any, Dict, List, Optional

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".tiff"}
_AUDIO_EXTS = {".mp3", ".ogg", ".wav", ".m4a", ".aac", ".flac"}
_VIDEO_EXTS = {".mp4", ".webm", ".avi", ".mov", ".mkv"}


def decode_filename(raw: str) -> str:
    """Decode RFC 2047 filename."""
    if not raw:
        return "attachment.bin"
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def classify_attachment(filename: str, content_type: str) -> str:
    """Classify attachment as image, document, audio, or video."""
    ext = Path(filename).suffix.lower()
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _AUDIO_EXTS:
        return "audio"
    if ext in _VIDEO_EXTS:
        return "video"
    return "document"


def extract_attachments(
    msg,  # email.message.Message
    skip_attachments: bool = False,
    save_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Extract attachment metadata and optionally save files locally.

    Returns list of {filename, type, media_type, size, path (if saved)}.
    """
    attachments = []
    if not msg.is_multipart():
        return attachments

    for part in msg.walk():
        disposition = str(part.get("Content-Disposition", ""))
        content_type = part.get_content_type()

        # Only process actual attachments (skip body parts)
        if "attachment" not in disposition and "inline" not in disposition:
            continue

        # Skip text body parts
        if content_type in {"text/plain", "text/html"} and "attachment" not in disposition:
            continue

        if skip_attachments:
            continue

        filename = part.get_filename()
        if filename:
            filename = decode_filename(filename)
        else:
            ext = mimetypes.guess_extension(content_type) or ".bin"
            filename = f"attachment{ext}"

        payload = part.get_payload(decode=True)
        if not payload:
            continue

        att_type = classify_attachment(filename, content_type)
        att = {
            "filename": filename,
            "type": att_type,
            "media_type": content_type,
            "size": len(payload),
            "content_id": part.get("Content-ID", ""),
        }

        # Save to disk if requested
        if save_dir:
            save_path = Path(save_dir) / filename
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(payload)
            att["path"] = str(save_path)

        attachments.append(att)

    return attachments


def create_attachment_part(file_path: str, filename: Optional[str] = None) -> MIMEBase:
    """Create a MIME attachment part from a local file.

    Uses RFC 2231 encoding for non-ASCII filenames.
    """
    from email.utils import encode_rfc2231

    p = Path(file_path)
    fname = filename or p.name
    content_type, encoding = mimetypes.guess_type(str(p))

    with open(p, "rb") as f:
        data = f.read()

    if content_type is None:
        content_type = "application/octet-stream"

    # Split content type
    main_type, sub_type = content_type.split("/", 1) if "/" in content_type else ("application", "octet-stream")

    if main_type == "image":
        part = MIMEImage(data, _subtype=sub_type)
    elif main_type == "audio":
        part = MIMEAudio(data, _subtype=sub_type)
    else:
        part = MIMEApplication(data, _subtype=sub_type)

    # Use RFC 2231 encoding for non-ASCII filenames
    if not fname.isascii():
        encoded = encode_rfc2231(fname, "utf-8")
        part.add_header("Content-Disposition", "attachment", filename=encoded)
    else:
        part.add_header("Content-Disposition", f"attachment; filename={fname}")
    return part


def media_path_to_attachment(media_ref: str) -> Optional[Dict[str, Any]]:
    """Convert a MEDIA:/path/to/file reference to an attachment dict.

    Handles both MEDIA: prefix and plain file:// URLs.
    """
    path = media_ref
    if path.startswith("MEDIA:"):
        path = path[6:]
    if path.startswith("file://"):
        from urllib.parse import unquote
        path = unquote(path[7:])

    p = Path(path)
    if not p.exists():
        return None

    content_type, _ = mimetypes.guess_type(str(p))
    return {
        "path": str(p),
        "filename": p.name,
        "type": classify_attachment(p.name, content_type or ""),
        "media_type": content_type or "application/octet-stream",
        "size": p.stat().st_size,
    }
