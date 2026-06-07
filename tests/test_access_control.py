"""Tests for access-control enforcement.

Covers:
  1. Identity resolution (EMAIL_MULTI_CALLER env var and optional params["caller"])
  2. auth.is_account_accessible() — the full allowlist x identity matrix
  3. auth.assert_account_access() — PermissionError messages
  4. Tool handler integration — denied calls return access-denied JSON errors
  5. Filtered multi-account operations (list_accounts, poll_inbox, search)
  6. Fail-closed: empty allowed_users denies access
  7. params["caller"] not trusted by default
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import email_multi.auth as auth
from email_multi import tools

# ---------------------------------------------------------------------------
# Fixture accounts used across all test classes
# ---------------------------------------------------------------------------

_RESTRICTED = {
    "account_id": "restricted",
    "email": "restricted@example.com",
    "imap_host": "imap.example.com",
    "imap_port": 993,
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
    "password": "secret",
    "allowed_users": ["alice@example.com"],
    "allow_all": False,
    "skip_attachments": False,
    "poll_interval": 15,
    "folders": {"inbox": "INBOX", "sent": "Sent", "drafts": "Drafts", "trash": "Trash"},
}

# No allowed_users, no allow_all — fail-closed denies access
_NO_ALLOWLIST = {
    "account_id": "no_allowlist",
    "email": "noallow@example.com",
    "imap_host": "imap.example.com",
    "imap_port": 993,
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
    "password": "secret",
    "allowed_users": [],
    "allow_all": False,
    "skip_attachments": False,
    "poll_interval": 15,
    "folders": {"inbox": "INBOX", "sent": "Sent", "drafts": "Drafts", "trash": "Trash"},
}

_ALLOW_ALL = {
    "account_id": "allopen",
    "email": "allopen@example.com",
    "imap_host": "imap.example.com",
    "imap_port": 993,
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
    "password": "secret",
    "allowed_users": [],
    "allow_all": True,
    "skip_attachments": False,
    "poll_interval": 15,
    "folders": {"inbox": "INBOX", "sent": "Sent", "drafts": "Drafts", "trash": "Trash"},
}

_ALL_ACCOUNTS = [_RESTRICTED, _NO_ALLOWLIST, _ALLOW_ALL]

_ACCOUNTS_BY_ID = {a["account_id"]: a for a in _ALL_ACCOUNTS}


def _fake_get_account(account_id):
    return _ACCOUNTS_BY_ID.get(account_id)


def _fake_load_accounts():
    return _ALL_ACCOUNTS


# ---------------------------------------------------------------------------
# 1. Identity resolution
# ---------------------------------------------------------------------------

class TestGetCallerIdentity(unittest.TestCase):
    def setUp(self):
        os.environ.pop("EMAIL_MULTI_CALLER", None)
        os.environ.pop("EMAIL_MULTI_TRUST_CALLER_PARAM", None)

    def tearDown(self):
        os.environ.pop("EMAIL_MULTI_CALLER", None)
        os.environ.pop("EMAIL_MULTI_TRUST_CALLER_PARAM", None)

    def test_from_env_only(self):
        os.environ["EMAIL_MULTI_CALLER"] = "Bob@Example.COM"
        result = auth.get_caller_identity({})
        self.assertEqual(result, "bob@example.com")

    def test_params_not_trusted_by_default(self):
        """params["caller"] is ignored unless EMAIL_MULTI_TRUST_CALLER_PARAM=true."""
        result = auth.get_caller_identity({"caller": "alice@example.com"})
        self.assertIsNone(result)

    def test_params_trusted_when_env_enabled(self):
        os.environ["EMAIL_MULTI_TRUST_CALLER_PARAM"] = "true"
        result = auth.get_caller_identity({"caller": "alice@example.com"})
        self.assertEqual(result, "alice@example.com")

    def test_env_takes_priority_over_params(self):
        os.environ["EMAIL_MULTI_CALLER"] = "bob@example.com"
        os.environ["EMAIL_MULTI_TRUST_CALLER_PARAM"] = "true"
        result = auth.get_caller_identity({"caller": "alice@example.com"})
        self.assertEqual(result, "bob@example.com")

    def test_no_identity_returns_none(self):
        result = auth.get_caller_identity({})
        self.assertIsNone(result)

    def test_empty_string_params_ignored(self):
        os.environ["EMAIL_MULTI_TRUST_CALLER_PARAM"] = "true"
        result = auth.get_caller_identity({"caller": "   "})
        self.assertIsNone(result)

    def test_empty_env_ignored(self):
        os.environ["EMAIL_MULTI_CALLER"] = "   "
        result = auth.get_caller_identity({})
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# 2. auth.is_account_accessible — allowlist x identity matrix (fail-closed)
# ---------------------------------------------------------------------------

class TestIsAccountAccessible(unittest.TestCase):
    def setUp(self):
        os.environ.pop("EMAIL_MULTI_CALLER", None)
        os.environ.pop("EMAIL_MULTI_TRUST_CALLER_PARAM", None)
        self._p = patch("email_multi.auth.get_account", side_effect=_fake_get_account)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        os.environ.pop("EMAIL_MULTI_CALLER", None)
        os.environ.pop("EMAIL_MULTI_TRUST_CALLER_PARAM", None)

    def test_allowlisted_user_granted(self):
        os.environ["EMAIL_MULTI_CALLER"] = "alice@example.com"
        self.assertTrue(auth.is_account_accessible("restricted", "alice@example.com"))

    def test_non_allowlisted_user_denied(self):
        self.assertFalse(auth.is_account_accessible("restricted", "bob@example.com"))

    def test_allow_all_true_anyone_granted(self):
        self.assertTrue(auth.is_account_accessible("allopen", "anyone@example.com"))

    def test_allow_all_true_no_identity_granted(self):
        self.assertTrue(auth.is_account_accessible("allopen", None))

    def test_no_caller_identity_with_allowlist_denied(self):
        self.assertFalse(auth.is_account_accessible("restricted", None))

    def test_no_allowlist_fail_closed_denies(self):
        """Empty allowed_users with no allow_all must deny (fail-closed)."""
        self.assertFalse(auth.is_account_accessible("no_allowlist", "anyone@example.com"))
        self.assertFalse(auth.is_account_accessible("no_allowlist", None))

    def test_unknown_account_denied(self):
        self.assertFalse(auth.is_account_accessible("nonexistent", "alice@example.com"))

    def test_case_insensitive_match(self):
        os.environ["EMAIL_MULTI_CALLER"] = "ALICE@EXAMPLE.COM"
        self.assertTrue(auth.is_account_accessible("restricted", "ALICE@EXAMPLE.COM"))


# ---------------------------------------------------------------------------
# 3. auth.assert_account_access — PermissionError messages
# ---------------------------------------------------------------------------

class TestAssertAccountAccess(unittest.TestCase):
    def setUp(self):
        os.environ.pop("EMAIL_MULTI_CALLER", None)
        os.environ.pop("EMAIL_MULTI_TRUST_CALLER_PARAM", None)
        self._p = patch("email_multi.auth.get_account", side_effect=_fake_get_account)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        os.environ.pop("EMAIL_MULTI_CALLER", None)
        os.environ.pop("EMAIL_MULTI_TRUST_CALLER_PARAM", None)

    def test_allowlisted_user_passes(self):
        auth.assert_account_access("restricted", "alice@example.com")  # no exception

    def test_non_allowlisted_raises_generic_message(self):
        with self.assertRaises(PermissionError) as ctx:
            auth.assert_account_access("restricted", "bob@example.com")
        msg = str(ctx.exception)
        self.assertIn("Access denied", msg)
        # Must not leak allowlist contents
        self.assertNotIn("alice@example.com", msg)

    def test_no_identity_with_allowlist_raises(self):
        with self.assertRaises(PermissionError) as ctx:
            auth.assert_account_access("restricted", None)
        msg = str(ctx.exception)
        self.assertIn("Access denied", msg)
        self.assertIn("identity unavailable", msg)

    def test_no_allowlist_raises_generic(self):
        """Empty allowed_users should deny with a generic message."""
        with self.assertRaises(PermissionError) as ctx:
            auth.assert_account_access("no_allowlist", "anyone@example.com")
        msg = str(ctx.exception)
        self.assertIn("Access denied", msg)
        self.assertIn("allowlist", msg)

    def test_allow_all_no_identity_passes(self):
        auth.assert_account_access("allopen", None)

    def test_unknown_account_passes(self):
        """Unknown account: let the service layer raise the 'Account not found' error."""
        auth.assert_account_access("nonexistent", "alice@example.com")


# ---------------------------------------------------------------------------
# 4. Tool handler integration — denied calls return JSON errors
# ---------------------------------------------------------------------------

class TestToolsAccessDenied(unittest.TestCase):
    """All single-account handlers must return Access denied when not authorised."""

    def setUp(self):
        os.environ.pop("EMAIL_MULTI_CALLER", None)
        os.environ.pop("EMAIL_MULTI_TRUST_CALLER_PARAM", None)
        self._p = patch("email_multi.auth.get_account", side_effect=_fake_get_account)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        os.environ.pop("EMAIL_MULTI_CALLER", None)
        os.environ.pop("EMAIL_MULTI_TRUST_CALLER_PARAM", None)

    def _denied(self, result_str):
        """Assert result is a JSON error containing 'Access denied'."""
        r = json.loads(result_str)
        self.assertFalse(r.get("success"), r)
        self.assertIn("Access denied", r.get("error", ""), r)

    # No identity, restricted account -> every handler must deny
    def test_list_messages_no_identity(self):
        self._denied(tools.email_multi_list_messages({"account_id": "restricted"}))

    def test_read_no_identity(self):
        self._denied(tools.email_multi_read({"account_id": "restricted", "message_id": "1"}))

    def test_download_attachment_no_identity(self):
        self._denied(tools.email_multi_download_attachment(
            {"account_id": "restricted", "message_id": "1", "attachment_id": "0"}
        ))

    def test_send_no_identity(self):
        self._denied(tools.email_multi_send(
            {"account_id": "restricted", "to": ["x@x.com"], "subject": "s", "body": "b"}
        ))

    def test_reply_no_identity(self):
        self._denied(tools.email_multi_reply(
            {"account_id": "restricted", "message_id": "1", "body": "b"}
        ))

    def test_list_folders_no_identity(self):
        self._denied(tools.email_multi_list_folders({"account_id": "restricted"}))

    def test_mark_seen_no_identity(self):
        self._denied(tools.email_multi_mark_seen({"account_id": "restricted", "message_id": "1"}))

    def test_delete_no_identity(self):
        self._denied(tools.email_multi_delete_message(
            {"account_id": "restricted", "message_id": "1"}
        ))

    # params["caller"] not trusted by default
    def test_params_caller_not_trusted_by_default(self):
        self._denied(tools.email_multi_list_messages(
            {"account_id": "restricted", "caller": "alice@example.com"}
        ))

    # Wrong caller via env -> denied
    def test_wrong_caller_via_env_denied(self):
        os.environ["EMAIL_MULTI_CALLER"] = "bob@example.com"
        self._denied(tools.email_multi_list_messages({"account_id": "restricted"}))

    # No allowlist account denies everyone
    def test_no_allowlist_denies_all(self):
        self._denied(tools.email_multi_list_messages({"account_id": "no_allowlist"}))


# ---------------------------------------------------------------------------
# 5. Tool handler integration — allowed calls proceed to service layer
# ---------------------------------------------------------------------------

class TestToolsAccessAllowed(unittest.TestCase):
    """Authorised callers must pass through to the service layer."""

    def setUp(self):
        os.environ.pop("EMAIL_MULTI_CALLER", None)
        os.environ.pop("EMAIL_MULTI_TRUST_CALLER_PARAM", None)
        self._auth_p = patch("email_multi.auth.get_account", side_effect=_fake_get_account)
        self._auth_p.start()

    def tearDown(self):
        self._auth_p.stop()
        os.environ.pop("EMAIL_MULTI_CALLER", None)
        os.environ.pop("EMAIL_MULTI_TRUST_CALLER_PARAM", None)

    def _ok(self, result_str):
        r = json.loads(result_str)
        self.assertTrue(r.get("success"), r)
        return r

    @patch("email_multi.service.search_messages", return_value=[])
    def test_valid_caller_via_env(self, _):
        os.environ["EMAIL_MULTI_CALLER"] = "alice@example.com"
        self._ok(tools.email_multi_list_messages({"account_id": "restricted"}))

    @patch("email_multi.service.search_messages", return_value=[])
    def test_valid_caller_in_params_when_trusted(self, _):
        os.environ["EMAIL_MULTI_TRUST_CALLER_PARAM"] = "true"
        result = self._ok(tools.email_multi_list_messages(
            {"account_id": "restricted", "caller": "alice@example.com"}
        ))
        self.assertEqual(result["count"], 0)

    @patch("email_multi.service.search_messages", return_value=[])
    def test_allow_all_account_no_identity_allowed(self, _):
        self._ok(tools.email_multi_list_messages({"account_id": "allopen"}))

    @patch("email_multi.service.search_messages", return_value=[])
    def test_allow_all_account_any_caller_allowed(self, _):
        self._ok(tools.email_multi_list_messages(
            {"account_id": "allopen", "caller": "anyone@anywhere.com"}
        ))


# ---------------------------------------------------------------------------
# 6. Multi-account operations filter inaccessible accounts
# ---------------------------------------------------------------------------

class TestMultiAccountFiltering(unittest.TestCase):
    """list_accounts / poll_inbox / search_messages filter by caller access."""

    def setUp(self):
        os.environ.pop("EMAIL_MULTI_CALLER", None)
        os.environ.pop("EMAIL_MULTI_TRUST_CALLER_PARAM", None)
        self._auth_p = patch("email_multi.auth.get_account", side_effect=_fake_get_account)
        self._auth_p.start()
        self._load_p = patch("email_multi.config.load_accounts", side_effect=_fake_load_accounts)
        self._load_p.start()
        self._ids_p = patch(
            "email_multi.config.list_account_ids",
            return_value=[a["account_id"] for a in _ALL_ACCOUNTS],
        )
        self._ids_p.start()

    def tearDown(self):
        self._auth_p.stop()
        self._load_p.stop()
        self._ids_p.stop()
        os.environ.pop("EMAIL_MULTI_CALLER", None)
        os.environ.pop("EMAIL_MULTI_TRUST_CALLER_PARAM", None)

    @patch("email_multi.service.check_account", return_value={"imap": True, "smtp": True})
    def test_list_accounts_hides_inaccessible_no_identity(self, _):
        result = json.loads(tools.email_multi_list_accounts({}))
        ids = [a["account_id"] for a in result["accounts"]]
        self.assertNotIn("restricted", ids, "restricted account must not appear without identity")
        self.assertNotIn("no_allowlist", ids, "no_allowlist must be denied (fail-closed)")
        self.assertIn("allopen", ids)

    @patch("email_multi.service.check_account", return_value={"imap": True, "smtp": True})
    def test_list_accounts_shows_accessible_with_valid_caller(self, _):
        os.environ["EMAIL_MULTI_CALLER"] = "alice@example.com"
        result = json.loads(tools.email_multi_list_accounts({}))
        ids = [a["account_id"] for a in result["accounts"]]
        self.assertIn("restricted", ids)
        self.assertNotIn("no_allowlist", ids)
        self.assertIn("allopen", ids)

    @patch("email_multi.service.search_messages", return_value=[])
    def test_poll_inbox_skips_inaccessible_no_identity(self, mock_search):
        tools.email_multi_poll_inbox({})
        called_ids = {call.kwargs.get("account_id") for call in mock_search.call_args_list}
        self.assertNotIn("restricted", called_ids)
        self.assertNotIn("no_allowlist", called_ids)
        self.assertIn("allopen", called_ids)

    @patch("email_multi.service.search_full_messages", return_value=[])
    def test_search_messages_skips_inaccessible_no_identity(self, mock_search):
        json.loads(tools.email_multi_search_messages({}))
        called_ids = {call.kwargs.get("account_id") for call in mock_search.call_args_list}
        self.assertNotIn("restricted", called_ids)
        self.assertNotIn("no_allowlist", called_ids)

    @patch("email_multi.service.search_full_messages", return_value=[])
    def test_search_messages_explicit_account_denied(self, _):
        result = json.loads(tools.email_multi_search_messages({"account_id": "restricted"}))
        self.assertFalse(result["success"])
        self.assertIn("Access denied", result["error"])


# ---------------------------------------------------------------------------
# 7. Error message sanitization — no allowlist leakage
# ---------------------------------------------------------------------------

class TestErrorSanitization(unittest.TestCase):
    """Error messages must not leak allowlists, passwords, or account details."""

    def setUp(self):
        os.environ.pop("EMAIL_MULTI_CALLER", None)
        os.environ.pop("EMAIL_MULTI_TRUST_CALLER_PARAM", None)
        self._p = patch("email_multi.auth.get_account", side_effect=_fake_get_account)
        self._p.start()

    def tearDown(self):
        self._p.stop()
        os.environ.pop("EMAIL_MULTI_CALLER", None)
        os.environ.pop("EMAIL_MULTI_TRUST_CALLER_PARAM", None)

    def test_denial_error_does_not_leak_allowlist(self):
        with self.assertRaises(PermissionError) as ctx:
            auth.assert_account_access("restricted", "bob@example.com")
        msg = str(ctx.exception)
        self.assertNotIn("alice@example.com", msg)
        self.assertNotIn("restricted@example.com", msg)

    def test_denial_error_does_not_leak_password(self):
        result = tools.email_multi_list_messages(
            {"account_id": "restricted", "caller": "bob@example.com"}
        )
        self.assertNotIn("secret", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
