"""Tests for delete/trash IMAP command semantics."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from email_multi import service, tools  # noqa: E402


class FakeIMAP:
    def __init__(self, statuses=None):
        self.statuses = statuses or {}
        self.commands = []
        self.logged_out = False

    def select(self, folder):
        self.commands.append(("select", folder))
        return "OK", []

    def uid(self, command, *args):
        self.commands.append(("uid", command, args))
        return self.statuses.get(command, ("OK", []))

    def expunge(self):
        self.commands.append(("expunge",))
        return "OK", []

    def logout(self):
        self.commands.append(("logout",))
        self.logged_out = True


class DeleteSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.account = {
            "account_id": "acct",
            "email": "acct@example.com",
            "folders": {"inbox": "INBOX", "trash": "Trash"},
        }

    def test_delete_from_non_trash_copies_to_trash_then_removes_from_origin(self):
        fake = FakeIMAP()

        with patch.object(service, "get_account", return_value=self.account), patch.object(
            service,
            "_get_imap",
            return_value=fake,
        ):
            ok = service.delete_message("acct", "123", folder="INBOX")

        self.assertTrue(ok)
        self.assertEqual(
            fake.commands,
            [
                ("select", "INBOX"),
                ("uid", "copy", ("123", "Trash")),
                ("uid", "store", ("123", "+FLAGS", "\\Deleted")),
                ("expunge",),
                ("logout",),
            ],
        )
        self.assertTrue(fake.logged_out)

    def test_delete_from_default_inbox_uses_configured_inbox_folder(self):
        fake = FakeIMAP()

        with patch.object(service, "get_account", return_value=self.account), patch.object(
            service,
            "_get_imap",
            return_value=fake,
        ):
            ok = service.delete_message("acct", "123")

        self.assertTrue(ok)
        self.assertEqual(fake.commands[0], ("select", "INBOX"))
        self.assertEqual(fake.commands[1], ("uid", "copy", ("123", "Trash")))

    def test_delete_when_already_in_trash_sets_deleted_flag_and_expunges(self):
        fake = FakeIMAP()

        with patch.object(service, "get_account", return_value=self.account), patch.object(
            service,
            "_get_imap",
            return_value=fake,
        ):
            ok = service.delete_message("acct", "123", folder="Trash")

        self.assertTrue(ok)
        self.assertEqual(
            fake.commands,
            [
                ("select", "Trash"),
                ("uid", "store", ("123", "+FLAGS", "\\Deleted")),
                ("expunge",),
                ("logout",),
            ],
        )

    def test_copy_failure_does_not_remove_origin_message(self):
        fake = FakeIMAP(statuses={"copy": ("NO", [b"copy failed"])})

        with patch.object(service, "get_account", return_value=self.account), patch.object(
            service,
            "_get_imap",
            return_value=fake,
        ):
            ok = service.delete_message("acct", "123", folder="INBOX")

        self.assertFalse(ok)
        self.assertEqual(
            fake.commands,
            [
                ("select", "INBOX"),
                ("uid", "copy", ("123", "Trash")),
                ("logout",),
            ],
        )

    def test_tool_wrapper_returns_delete_result_json(self):
        with patch.object(service, "delete_message", return_value=True) as delete_message:
            payload = tools.email_multi_delete_message(
                {"account_id": "acct", "message_id": "123", "folder": "INBOX"}
            )

        delete_message.assert_called_once_with("acct", "123", "INBOX")
        self.assertEqual(
            json.loads(payload),
            {
                "success": True,
                "account_id": "acct",
                "message_id": "123",
                "deleted": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
