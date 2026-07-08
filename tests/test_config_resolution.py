"""Tests for account config loading and environment resolution.

Security: plaintext passwords are rejected; password_env is required.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from email_multi import config  # noqa: E402


class ConfigResolutionTests(unittest.TestCase):
    def setUp(self):
        self._old_hermes_home = os.environ.pop(config.HERMES_HOME_ENV, None)
        self._old_accounts = os.environ.pop(config.ACCOUNTS_ENV, None)
        self._old_password = os.environ.pop("TEST_EMAIL_PASSWORD", None)
        # Clear cache so each test gets fresh data
        config._clear_accounts_cache()
        self.tmp = tempfile.TemporaryDirectory()
        os.environ[config.HERMES_HOME_ENV] = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()
        config._clear_accounts_cache()
        os.environ.pop(config.HERMES_HOME_ENV, None)
        os.environ.pop(config.ACCOUNTS_ENV, None)
        os.environ.pop("TEST_EMAIL_PASSWORD", None)
        if self._old_hermes_home is not None:
            os.environ[config.HERMES_HOME_ENV] = self._old_hermes_home
        if self._old_accounts is not None:
            os.environ[config.ACCOUNTS_ENV] = self._old_accounts
        if self._old_password is not None:
            os.environ["TEST_EMAIL_PASSWORD"] = self._old_password

    def _plugin_dir_patch(self):
        """Return a patch that makes _plugin_dir() point to the test temp dir."""
        return patch.object(config, "_plugin_dir", return_value=Path(self.tmp.name))

    def _write_accounts_yaml(self, text):
        path = Path(self.tmp.name) / "accounts.yaml"
        path.write_text(text)

    @patch.object(config, "_plugin_dir")
    def test_load_accounts_from_yaml_accounts_list_and_resolves_password_env(self, mock_dir):
        os.environ["TEST_EMAIL_PASSWORD"] = "secret-value"
        mock_dir.return_value = Path(self.tmp.name)
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

    @patch.object(config, "_plugin_dir")
    def test_plaintext_password_rejected(self, mock_dir):
        mock_dir.return_value = Path(self.tmp.name)
        self._write_accounts_yaml(
            """
accounts:
  - account_id: work
    email: work@example.com
    imap_host: imap.example.com
    smtp_host: smtp.example.com
    password: plaintext-secret
"""
        )

        with self.assertRaises(ValueError) as ctx:
            config.load_accounts()
        self.assertIn("Plaintext", str(ctx.exception))
        self.assertIn("password_env", str(ctx.exception))

    @patch.object(config, "_plugin_dir")
    def test_missing_password_env_rejected(self, mock_dir):
        mock_dir.return_value = Path(self.tmp.name)
        self._write_accounts_yaml(
            """
accounts:
  - account_id: work
    email: work@example.com
    imap_host: imap.example.com
    smtp_host: smtp.example.com
"""
        )

        with self.assertRaises(ValueError) as ctx:
            config.load_accounts()
        self.assertIn("password_env", str(ctx.exception))

    @patch.object(config, "_plugin_dir")
    def test_empty_password_env_var_rejected(self, mock_dir):
        mock_dir.return_value = Path(self.tmp.name)
        self._write_accounts_yaml(
            """
accounts:
  - account_id: work
    email: work@example.com
    imap_host: imap.example.com
    smtp_host: smtp.example.com
    password_env: UNSET_VAR_XYZ
"""
        )

        with self.assertRaises(ValueError) as ctx:
            config.load_accounts()
        self.assertIn("UNSET_VAR_XYZ", str(ctx.exception))

    @patch.object(config, "_plugin_dir")
    def test_load_accounts_from_json_env_when_yaml_absent(self, mock_dir):
        """ACCOUNTS_ENV JSON is used when no YAML file exists at plugin dir."""
        mock_dir.return_value = Path("/nonexistent-test-path")
        os.environ[config.ACCOUNTS_ENV] = json.dumps(
            {
                "accounts": [
                    {
                        "account_id": "personal",
                        "email": "me@example.com",
                        "imap_host": "imap.example.com",
                        "smtp_host": "smtp.example.com",
                        "password_env": "TEST_EMAIL_PASSWORD",
                    }
                ]
            }
        )
        os.environ["TEST_EMAIL_PASSWORD"] = "secret-value"

        accounts = config.load_accounts()

        self.assertEqual([account["account_id"] for account in accounts], ["personal"])

    @patch.object(config, "_plugin_dir")
    def test_defaults_are_applied_to_minimal_account(self, mock_dir):
        mock_dir.return_value = Path("/nonexistent-test-path")
        os.environ["TEST_EMAIL_PASSWORD"] = "secret-value"
        os.environ[config.ACCOUNTS_ENV] = json.dumps(
            [
                {
                    "account_id": "minimal",
                    "email": "minimal@example.com",
                    "imap_host": "imap.example.com",
                    "smtp_host": "smtp.example.com",
                    "password_env": "TEST_EMAIL_PASSWORD",
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
        self.assertEqual(account["auth_failure_cooldown_seconds"], 300)
        self.assertEqual(
            account["folders"],
            {
                "inbox": "INBOX",
                "sent": "Sent",
                "drafts": "Drafts",
                "trash": "Trash",
            },
        )

    @patch.object(config, "_plugin_dir")
    def test_explicit_defaults_are_preserved(self, mock_dir):
        mock_dir.return_value = Path("/nonexistent-test-path")
        os.environ["TEST_EMAIL_PASSWORD"] = "secret-value"
        os.environ[config.ACCOUNTS_ENV] = json.dumps(
            [
                {
                    "account_id": "custom",
                    "email": "custom@example.com",
                    "imap_host": "imap.example.com",
                    "imap_port": 1993,
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 2525,
                    "password_env": "TEST_EMAIL_PASSWORD",
                    "allowed_users": ["user@example.com"],
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
        self.assertEqual(account["allowed_users"], ["user@example.com"])
        self.assertTrue(account["allow_all"])
        self.assertTrue(account["skip_attachments"])
        self.assertEqual(account["poll_interval"], 60)
        self.assertEqual(account["folders"]["inbox"], "Inbox")
        self.assertEqual(account["folders"]["trash"], "Deleted Items")
        self.assertEqual(account["folders"]["sent"], "Sent")
        self.assertEqual(account["folders"]["drafts"], "Drafts")

    @patch.object(config, "_plugin_dir")
    def test_get_account_and_list_account_ids_return_stable_ids(self, mock_dir):
        mock_dir.return_value = Path("/nonexistent-test-path")
        os.environ["TEST_EMAIL_PASSWORD"] = "secret-value"
        os.environ[config.ACCOUNTS_ENV] = json.dumps(
            [
                {"account_id": "first", "email": "first@example.com", "imap_host": "imap1", "smtp_host": "smtp1", "password_env": "TEST_EMAIL_PASSWORD"},
                {"account_id": "second", "email": "second@example.com", "imap_host": "imap2", "smtp_host": "smtp2", "password_env": "TEST_EMAIL_PASSWORD"},
            ]
        )

        self.assertEqual(config.list_account_ids(), ["first", "second"])
        self.assertEqual(config.get_account("second")["email"], "second@example.com")
        self.assertIsNone(config.get_account("missing"))

    @patch.object(config, "_plugin_dir")
    def test_cache_returns_same_data(self, mock_dir):
        """load_accounts() should cache results within TTL."""
        os.environ["TEST_EMAIL_PASSWORD"] = "secret-value"
        mock_dir.return_value = Path(self.tmp.name)
        self._write_accounts_yaml(
            """
accounts:
  - account_id: cached
    email: cached@example.com
    imap_host: imap.example.com
    smtp_host: smtp.example.com
    password_env: TEST_EMAIL_PASSWORD
"""
        )

        accounts1 = config.load_accounts()
        accounts2 = config.load_accounts()
        self.assertIs(accounts1, accounts2, "cache should return same object")

    @patch.object(config, "_plugin_dir")
    def test_cache_expires_after_ttl(self, mock_dir):
        """Cache should expire after TTL."""
        os.environ["TEST_EMAIL_PASSWORD"] = "secret-value"
        mock_dir.return_value = Path(self.tmp.name)
        self._write_accounts_yaml(
            """
accounts:
  - account_id: cached
    email: cached@example.com
    imap_host: imap.example.com
    smtp_host: smtp.example.com
    password_env: TEST_EMAIL_PASSWORD
"""
        )

        accounts1 = config.load_accounts()
        # Force cache expiry
        config._accounts_cache_time -= config._ACCOUNTS_CACHE_TTL + 1
        accounts2 = config.load_accounts()
        self.assertEqual(accounts1[0]["account_id"], accounts2[0]["account_id"])


if __name__ == "__main__":
    unittest.main()
