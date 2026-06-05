"""Tests for account config loading and environment resolution."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from email_multi import config  # noqa: E402


class ConfigResolutionTests(unittest.TestCase):
    def setUp(self):
        self._old_hermes_home = os.environ.pop(config.HERMES_HOME_ENV, None)
        self._old_accounts = os.environ.pop(config.ACCOUNTS_ENV, None)
        self._old_password = os.environ.pop("TEST_EMAIL_PASSWORD", None)
        self.tmp = tempfile.TemporaryDirectory()
        os.environ[config.HERMES_HOME_ENV] = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop(config.HERMES_HOME_ENV, None)
        os.environ.pop(config.ACCOUNTS_ENV, None)
        os.environ.pop("TEST_EMAIL_PASSWORD", None)
        if self._old_hermes_home is not None:
            os.environ[config.HERMES_HOME_ENV] = self._old_hermes_home
        if self._old_accounts is not None:
            os.environ[config.ACCOUNTS_ENV] = self._old_accounts
        if self._old_password is not None:
            os.environ["TEST_EMAIL_PASSWORD"] = self._old_password

    def _write_accounts_yaml(self, text):
        path = Path(self.tmp.name) / "plugins" / "email_multi" / "accounts.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(text)

    def test_load_accounts_from_yaml_accounts_list_and_resolves_password_env(self):
        os.environ["TEST_EMAIL_PASSWORD"] = "secret-value"
        self._write_accounts_yaml(
            """
accounts:
  - account_id: work
    email: work@example.com
    imap_host: imap.example.com
    smtp_host: smtp.example.com
    password_env: TEST_EMAIL_PASSWORD
"""
        )

        accounts = config.load_accounts()

        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["account_id"], "work")
        self.assertEqual(accounts[0]["password"], "secret-value")
        self.assertNotIn("password_env", accounts[0])

    def test_load_accounts_raises_when_password_env_missing(self):
        """If password_env references an unset env var, raise EnvironmentError."""
        # Ensure the env var is definitely not set
        os.environ.pop("MISSING_TEST_PASSWORD", None)
        self._write_accounts_yaml(
            """
accounts:
  - account_id: broken
    email: broken@example.com
    imap_host: imap.example.com
    smtp_host: smtp.example.com
    password_env: MISSING_TEST_PASSWORD
"""
        )

        with self.assertRaises(EnvironmentError) as ctx:
            config.load_accounts()

        self.assertIn("MISSING_TEST_PASSWORD", str(ctx.exception))
        self.assertIn("broken", str(ctx.exception))

    def test_load_accounts_from_json_env_when_yaml_absent(self):
        os.environ[config.ACCOUNTS_ENV] = json.dumps(
            {
                "accounts": [
                    {
                        "account_id": "personal",
                        "email": "me@example.com",
                        "imap_host": "imap.example.com",
                        "smtp_host": "smtp.example.com",
                    }
                ]
            }
        )

        accounts = config.load_accounts()

        self.assertEqual([account["account_id"] for account in accounts], ["personal"])

    def test_defaults_are_applied_to_minimal_account(self):
        os.environ[config.ACCOUNTS_ENV] = json.dumps(
            [
                {
                    "account_id": "minimal",
                    "email": "minimal@example.com",
                    "imap_host": "imap.example.com",
                    "smtp_host": "smtp.example.com",
                }
            ]
        )

        account = config.load_accounts()[0]

        self.assertEqual(account["imap_port"], 993)
        self.assertEqual(account["smtp_port"], 587)
        self.assertEqual(account["allowed_users"], [])
        self.assertFalse(account["allow_all"])
        self.assertFalse(account["skip_attachments"])
        self.assertEqual(account["poll_interval"], 15)
        self.assertEqual(
            account["folders"],
            {
                "inbox": "INBOX",
                "sent": "Sent",
                "drafts": "Drafts",
                "trash": "Trash",
            },
        )

    def test_explicit_defaults_are_preserved(self):
        os.environ[config.ACCOUNTS_ENV] = json.dumps(
            [
                {
                    "account_id": "custom",
                    "email": "custom@example.com",
                    "imap_host": "imap.example.com",
                    "imap_port": 1993,
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 2525,
                    "allowed_users": ["operator@example.com"],
                    "allow_all": True,
                    "skip_attachments": True,
                    "poll_interval": 60,
                    "folders": {"inbox": "Inbox", "trash": "Deleted Items"},
                }
            ]
        )

        account = config.load_accounts()[0]

        self.assertEqual(account["imap_port"], 1993)
        self.assertEqual(account["smtp_port"], 2525)
        self.assertEqual(account["allowed_users"], ["operator@example.com"])
        self.assertTrue(account["allow_all"])
        self.assertTrue(account["skip_attachments"])
        self.assertEqual(account["poll_interval"], 60)
        self.assertEqual(account["folders"]["inbox"], "Inbox")
        self.assertEqual(account["folders"]["trash"], "Deleted Items")
        self.assertEqual(account["folders"]["sent"], "Sent")
        self.assertEqual(account["folders"]["drafts"], "Drafts")

    def test_get_account_and_list_account_ids_return_stable_ids(self):
        os.environ[config.ACCOUNTS_ENV] = json.dumps(
            [
                {"account_id": "first", "email": "first@example.com", "imap_host": "imap1", "smtp_host": "smtp1"},
                {"account_id": "second", "email": "second@example.com", "imap_host": "imap2", "smtp_host": "smtp2"},
            ]
        )

        self.assertEqual(config.list_account_ids(), ["first", "second"])
        self.assertEqual(config.get_account("second")["email"], "second@example.com")
        self.assertIsNone(config.get_account("missing"))


if __name__ == "__main__":
    unittest.main()
