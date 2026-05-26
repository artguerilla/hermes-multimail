"""Tests for attachment filename, classification, extraction, and path handling."""
import os
import sys
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from email_multi.attachments import (  # noqa: E402
    classify_attachment,
    decode_filename,
    extract_attachments,
    media_path_to_attachment,
)


def _message_with_attachments():
    msg = EmailMessage()
    msg["Subject"] = "attachments"
    msg.set_content("plain body")
    msg.add_alternative("<p>html body</p>", subtype="html")
    msg.add_attachment(
        b"image-bytes",
        maintype="image",
        subtype="png",
        filename="photo.png",
    )
    msg.add_attachment(
        b"pdf-bytes",
        maintype="application",
        subtype="pdf",
        filename="report.pdf",
    )
    return msg


class AttachmentTests(unittest.TestCase):
    def test_decode_filename_handles_rfc_2047(self):
        self.assertEqual(decode_filename("=?utf-8?b?UsOpc3Vtw6kucGRm?="), "Résumé.pdf")

    def test_decode_filename_empty_defaults_to_attachment_bin(self):
        self.assertEqual(decode_filename(""), "attachment.bin")

    def test_classify_attachment_by_extension(self):
        self.assertEqual(classify_attachment("photo.jpg", "image/jpeg"), "image")
        self.assertEqual(classify_attachment("voice.mp3", "audio/mpeg"), "audio")
        self.assertEqual(classify_attachment("clip.mp4", "video/mp4"), "video")
        self.assertEqual(classify_attachment("report.pdf", "application/pdf"), "document")

    def test_extract_attachments_ignores_text_bodies_and_sets_metadata(self):
        attachments = extract_attachments(_message_with_attachments())

        self.assertEqual(len(attachments), 2)
        self.assertEqual(attachments[0]["filename"], "photo.png")
        self.assertEqual(attachments[0]["type"], "image")
        self.assertEqual(attachments[0]["media_type"], "image/png")
        self.assertEqual(attachments[0]["size"], len(b"image-bytes"))
        self.assertEqual(attachments[1]["filename"], "report.pdf")
        self.assertEqual(attachments[1]["type"], "document")
        self.assertEqual(attachments[1]["media_type"], "application/pdf")
        self.assertEqual(attachments[1]["size"], len(b"pdf-bytes"))

    def test_extract_attachments_includes_inline_non_text_files(self):
        msg = EmailMessage()
        msg.set_content("plain body")
        msg.add_related(
            b"inline-image",
            maintype="image",
            subtype="png",
            cid="image-1",
            filename="inline.png",
        )

        attachments = extract_attachments(msg)

        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]["filename"], "inline.png")
        self.assertEqual(attachments[0]["content_id"], "image-1")

    def test_extract_attachments_skip_attachments_returns_empty_list(self):
        self.assertEqual(extract_attachments(_message_with_attachments(), skip_attachments=True), [])

    def test_extract_attachments_save_dir_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            attachments = extract_attachments(_message_with_attachments(), save_dir=tmp)

            paths = [Path(item["path"]) for item in attachments]
            self.assertEqual([path.name for path in paths], ["photo.png", "report.pdf"])
            self.assertEqual(paths[0].read_bytes(), b"image-bytes")
            self.assertEqual(paths[1].read_bytes(), b"pdf-bytes")

    def test_extract_attachments_without_filename_uses_content_type_extension(self):
        msg = EmailMessage()
        msg.set_content("plain body")
        msg.add_attachment(
            b"binary",
            maintype="application",
            subtype="octet-stream",
        )

        attachments = extract_attachments(msg)

        self.assertEqual(attachments[0]["filename"], "attachment.bin")

    def test_media_path_to_attachment_accepts_plain_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.txt"
            path.write_text("hello")

            attachment = media_path_to_attachment(str(path))

            self.assertEqual(attachment["path"], str(path))
            self.assertEqual(attachment["filename"], "note.txt")
            self.assertEqual(attachment["type"], "document")
            self.assertEqual(attachment["media_type"], "text/plain")
            self.assertEqual(attachment["size"], len("hello"))

    def test_media_path_to_attachment_accepts_file_uri(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image file.png"
            path.write_bytes(b"png")
            uri = path.as_uri()

            attachment = media_path_to_attachment(uri)

            self.assertEqual(attachment["path"], str(path))
            self.assertEqual(attachment["filename"], "image file.png")
            self.assertEqual(attachment["type"], "image")

    def test_media_path_to_attachment_missing_path_returns_none(self):
        missing = Path(tempfile.gettempdir()) / "missing-hermes-attachment.bin"
        try:
            os.unlink(missing)
        except FileNotFoundError:
            pass

        self.assertIsNone(media_path_to_attachment(str(missing)))


if __name__ == "__main__":
    unittest.main()
