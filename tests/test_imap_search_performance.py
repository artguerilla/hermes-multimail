import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "email_multi"
spec = importlib.util.spec_from_file_location(
    "email_multi",
    PLUGIN_DIR / "__init__.py",
    submodule_search_locations=[str(PLUGIN_DIR)],
)
email_multi = importlib.util.module_from_spec(spec)
sys.modules["email_multi"] = email_multi
spec.loader.exec_module(email_multi)

from email_multi import service, tools  # noqa: E402


def _raw_message(uid: int, body: str = "hello keyword") -> bytes:
    return (
        f"Subject: Test {uid}\r\n"
        "From: Sender <sender@example.com>\r\n"
        "To: Reader <reader@example.com>\r\n"
        f"Message-ID: <{uid}@example.com>\r\n"
        "\r\n"
        f"{body}\r\n"
    ).encode()


class FakeIMAP:
    def __init__(self, count=3, search_responses=None, reject_batch_fetch=False):
        self.messages = {str(uid): _raw_message(uid) for uid in range(1, count + 1)}
        self.search_responses = search_responses or [
            ("OK", [b" ".join(str(uid).encode() for uid in range(1, count + 1))])
        ]
        self.reject_batch_fetch = reject_batch_fetch
        self.commands = []
        self.selected = []
        self.logged_out = False

    def select(self, folder, readonly=False):
        self.selected.append((folder, readonly))
        return "OK", []

    def uid(self, command, *args):
        self.commands.append((command, args))
        if command == "search":
            return self.search_responses.pop(0)
        if command == "fetch":
            uid_set, spec = args
            if self.reject_batch_fetch and "," in str(uid_set):
                return "BAD", [b"multi uid fetch unsupported"]
            uids = str(uid_set).split(",")
            rows = []
            for uid in uids:
                raw = self.messages[uid]
                payload = raw.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n" if "RFC822.HEADER" in spec else raw
                meta = f'1 (UID {uid} FLAGS (\\Seen) RFC822.SIZE {len(raw)} RFC822'.encode()
                rows.append((meta, payload))
            return "OK", rows
        raise AssertionError(f"unexpected command: {command}")

    def logout(self):
        self.logged_out = True


class ImapSearchPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.account = {
            "account_id": "acct",
            "folders": {"inbox": "INBOX"},
            "skip_attachments": False,
        }

    def test_keyword_uses_portable_text_search_when_ascii(self):
        criteria = tools._build_imap_criteria({"keyword": 'paid "invoice"', "subject": "Billing"})
        fallback = tools._build_imap_criteria(
            {"keyword": 'paid "invoice"', "subject": "Billing"},
            include_keyword=False,
        )

        self.assertIn('SUBJECT "Billing"', criteria)
        self.assertIn('TEXT "paid \\"invoice\\""', criteria)
        self.assertEqual(fallback, 'SUBJECT "Billing"')

    def test_non_ascii_keyword_stays_on_client_side_fallback_path(self):
        criteria = tools._build_imap_criteria({"keyword": "café"})

        self.assertEqual(criteria, "ALL")

    def test_search_messages_batches_header_fetches_and_preserves_metadata(self):
        fake = FakeIMAP(count=150)
        with patch.object(service, "get_account", return_value=self.account), patch.object(
            service,
            "_get_imap",
            return_value=fake,
        ):
            result = service.search_messages("acct", criteria="ALL", limit=150)

        fetches = [args for command, args in fake.commands if command == "fetch"]
        self.assertEqual(len(fetches), 2)
        self.assertEqual(result[0]["uid"], "150")
        self.assertEqual(result[0]["flags"], ["\\Seen"])
        self.assertGreater(result[0]["size"], 0)
        self.assertTrue(fake.logged_out)

    def test_full_search_uses_one_session_and_batched_full_fetch(self):
        fake = FakeIMAP(count=3)
        with patch.object(service, "get_account", return_value=self.account), patch.object(
            service,
            "_get_imap",
            return_value=fake,
        ) as get_imap:
            result = service.search_full_messages("acct", criteria='TEXT "keyword"', limit=2)

        get_imap.assert_called_once()
        fetches = [args for command, args in fake.commands if command == "fetch"]
        self.assertEqual(fetches[0][0], "2,3")
        self.assertEqual([msg["uid"] for msg in result], ["3", "2"])
        self.assertIn("keyword", result[0]["body_text"])

    def test_batch_fetch_rejection_retries_individual_uids_in_same_session(self):
        fake = FakeIMAP(count=3, reject_batch_fetch=True)
        with patch.object(service, "get_account", return_value=self.account), patch.object(
            service,
            "_get_imap",
            return_value=fake,
        ) as get_imap:
            result = service.search_full_messages("acct", criteria="ALL", limit=3)

        fetch_uid_sets = [args[0] for command, args in fake.commands if command == "fetch"]
        self.assertEqual(fetch_uid_sets, ["1,2,3", "1", "2", "3"])
        get_imap.assert_called_once()
        self.assertEqual([msg["uid"] for msg in result], ["3", "2", "1"])

    def test_retries_fallback_criteria_when_server_rejects_text_search(self):
        fake = FakeIMAP(
            count=1,
            search_responses=[
                ("BAD", [b"unsupported search key"]),
                ("OK", [b"1"]),
            ],
        )
        with patch.object(service, "get_account", return_value=self.account), patch.object(
            service,
            "_get_imap",
            return_value=fake,
        ):
            result = service.search_messages(
                "acct",
                criteria='TEXT "keyword"',
                fallback_criteria="ALL",
                limit=1,
            )

        searches = [args[1] for command, args in fake.commands if command == "search"]
        self.assertEqual(searches, ['TEXT "keyword"', "ALL"])
        self.assertEqual(result[0]["uid"], "1")


if __name__ == "__main__":
    unittest.main()
