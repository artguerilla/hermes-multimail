import imaplib
import smtplib
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from email_multi import service  # noqa: E402


class ConnectionHardeningTests(unittest.TestCase):
    def setUp(self):
        service._AUTH_FAILURES.clear()
        self.account = {
            "account_id": "work",
            "email": "agent@example.com",
            "password": "secret",
            "imap_host": "mail.example.com",
            "imap_port": 993,
            "smtp_host": "mail.example.com",
            "smtp_port": 587,
            "folders": {"inbox": "INBOX"},
            "auth_failure_cooldown_seconds": 300,
        }

    def tearDown(self):
        service._AUTH_FAILURES.clear()

    def test_imap_auth_failure_suppresses_immediate_retry(self):
        imap = Mock()
        imap.login.side_effect = imaplib.IMAP4.error("AUTHENTICATIONFAILED")

        with patch("email_multi.service.imaplib.IMAP4_SSL", return_value=imap) as ctor:
            with self.assertRaises(imaplib.IMAP4.error):
                service._get_imap(self.account)
            with self.assertRaises(service.AuthRetrySuppressed):
                service._get_imap(self.account)

        ctor.assert_called_once()
        imap.logout.assert_called_once()

    def test_smtp_uses_stable_ehlo_starttls_and_suppresses_auth_retry(self):
        smtp = Mock()
        smtp.has_extn.return_value = True
        smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad credentials")

        with patch("email_multi.service.smtplib.SMTP", return_value=smtp) as ctor:
            with self.assertRaises(smtplib.SMTPAuthenticationError):
                service._get_smtp(self.account)
            with self.assertRaises(service.AuthRetrySuppressed):
                service._get_smtp(self.account)

        ctor.assert_called_once()
        self.assertEqual(ctor.call_args.kwargs["local_hostname"], "example.com")
        self.assertEqual(smtp.ehlo.call_count, 2)
        smtp.starttls.assert_called_once()
        smtp.close.assert_called_once()

    def test_check_account_skips_smtp_after_imap_auth_failure(self):
        with patch("email_multi.service.get_account", return_value=self.account):
            imap_patch = patch(
                "email_multi.service._get_imap",
                side_effect=imaplib.IMAP4.error("AUTHENTICATIONFAILED"),
            )
            smtp_patch = patch("email_multi.service._get_smtp")
            with imap_patch, smtp_patch as get_smtp:
                result = service.check_account("work")

        self.assertFalse(result["imap"])
        self.assertFalse(result["smtp"])
        self.assertIn("AUTHENTICATIONFAILED", result["imap_error"])
        self.assertIn("Skipped after IMAP authentication failure", result["smtp_error"])
        get_smtp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
