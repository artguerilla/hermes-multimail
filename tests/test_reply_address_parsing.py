"""Tests for reply-address parsing fixes (issue #3).

Covers:
- bare addresses (no angle brackets)
- display-name format ("Name <addr>")
- multi-recipient reply-all (To + Cc)
- duplicate elimination
- Reply-To precedence over From
- sender exclusion
- ValueError when no valid recipients remain
"""
import sys
import unittest
from email.message import Message
from pathlib import Path

# Allow running from repo root without installation
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from email_multi.parsing import extract_email_address, parse_address_list
from email_multi.service import extract_all_reply_addresses


def _msg(**headers):
    """Build a minimal email.message.Message from keyword header args."""
    m = Message()
    for key, value in headers.items():
        m[key.replace("_", "-")] = value
    return m


class TestParseAddressList(unittest.TestCase):
    def test_bare_address(self):
        self.assertEqual(parse_address_list("alice@example.com"), ["alice@example.com"])

    def test_display_name_format(self):
        self.assertEqual(
            parse_address_list("Alice Smith <alice@example.com>"),
            ["alice@example.com"],
        )

    def test_multiple_bare_addresses(self):
        result = parse_address_list("alice@example.com, bob@example.com")
        self.assertEqual(result, ["alice@example.com", "bob@example.com"])

    def test_mixed_bare_and_display_name(self):
        result = parse_address_list("Alice <alice@example.com>, bob@example.com")
        self.assertEqual(result, ["alice@example.com", "bob@example.com"])

    def test_empty_string(self):
        self.assertEqual(parse_address_list(""), [])

    def test_case_normalised_to_lower(self):
        self.assertEqual(parse_address_list("Alice@Example.COM"), ["alice@example.com"])


class TestExtractEmailAddress(unittest.TestCase):
    def test_bare_address(self):
        self.assertEqual(extract_email_address("alice@example.com"), "alice@example.com")

    def test_display_name_format(self):
        self.assertEqual(
            extract_email_address("Alice Smith <alice@example.com>"),
            "alice@example.com",
        )

    def test_empty_string(self):
        self.assertEqual(extract_email_address(""), "")


class TestExtractAllReplyAddresses(unittest.TestCase):
    def test_bare_from_address(self):
        msg = _msg(From="alice@example.com")
        result = extract_all_reply_addresses(msg, exclude="me@example.com")
        self.assertEqual(result, ["alice@example.com"])

    def test_display_name_from(self):
        msg = _msg(From="Alice Smith <alice@example.com>")
        result = extract_all_reply_addresses(msg, exclude="me@example.com")
        self.assertEqual(result, ["alice@example.com"])

    def test_reply_to_takes_precedence_over_from(self):
        msg = _msg(From="alice@example.com", Reply_To="support@example.com")
        result = extract_all_reply_addresses(msg, exclude="me@example.com")
        self.assertIn("support@example.com", result)
        self.assertNotIn("alice@example.com", result)

    def test_reply_to_bare_address(self):
        msg = _msg(From="Alice <alice@example.com>", Reply_To="support@example.com")
        result = extract_all_reply_addresses(msg, exclude="me@example.com")
        self.assertEqual(result[0], "support@example.com")

    def test_sender_excluded_from_results(self):
        msg = _msg(
            From="alice@example.com",
            To="me@example.com, bob@example.com",
            Cc="carol@example.com",
        )
        result = extract_all_reply_addresses(msg, exclude="me@example.com")
        self.assertNotIn("me@example.com", result)

    def test_reply_all_includes_to_and_cc(self):
        msg = _msg(
            From="alice@example.com",
            To="me@example.com, bob@example.com",
            Cc="carol@example.com, dave@example.com",
        )
        result = extract_all_reply_addresses(msg, exclude="me@example.com")
        self.assertIn("alice@example.com", result)
        self.assertIn("bob@example.com", result)
        self.assertIn("carol@example.com", result)
        self.assertIn("dave@example.com", result)

    def test_duplicate_elimination(self):
        msg = _msg(
            From="alice@example.com",
            To="alice@example.com, bob@example.com",
            Cc="alice@example.com",
        )
        result = extract_all_reply_addresses(msg, exclude="me@example.com")
        self.assertEqual(result.count("alice@example.com"), 1)

    def test_duplicate_elimination_case_insensitive(self):
        msg = _msg(
            From="Alice@Example.com",
            Cc="alice@example.com",
        )
        result = extract_all_reply_addresses(msg, exclude="me@example.com")
        self.assertEqual(len(result), 1)

    def test_no_valid_recipients_raises_value_error(self):
        msg = _msg(From="me@example.com")
        with self.assertRaises(ValueError):
            extract_all_reply_addresses(msg, exclude="me@example.com")

    def test_no_from_raises_value_error(self):
        msg = _msg(Subject="test")
        with self.assertRaises(ValueError):
            extract_all_reply_addresses(msg, exclude="me@example.com")

    def test_stable_order_from_first(self):
        msg = _msg(
            From="alice@example.com",
            Cc="carol@example.com",
        )
        result = extract_all_reply_addresses(msg, exclude="me@example.com")
        self.assertEqual(result[0], "alice@example.com")
        self.assertEqual(result[1], "carol@example.com")


if __name__ == "__main__":
    unittest.main()
