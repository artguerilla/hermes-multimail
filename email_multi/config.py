"""Multi-account email configuration.

Reads accounts from EMAIL_MULTI_ACCOUNTS env var (JSON) or
from a config file at ~/.hermes/plugins/email_multi/accounts.yaml.

Each account:
  account_id: gmail
  email: falk.mp@gmail.com
  imap_host: imap.gmail.com
  imap_port: 993
  smtp_host: smtp.gmail.com
  smtp_port: 587
  password_env: EMAIL_GMAIL_PASSWORD  # resolved from env
  allowed_users: [falk.mp@gmail.com]
  allow_all: false
  skip_attachments: false
  folders:
    inbox: INBOX
    sent: "[Gmail]/Sent Mail"
    drafts: "[Gmail]/Drafts"
    trash: "[Gmail]/Trash"
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


ACCOUNTS_YAML = Path.home() / ".hermes" / "plugins" / "email_multi" / "accounts.yaml"
ACCOUNTS_ENV = "EMAIL_MULTI_ACCOUNTS"


def load_accounts() -> List[Dict[str, Any]]:
    """Load account configs from YAML file or env var."""
    # Try YAML file first
    if ACCOUNTS_YAML.exists():
        with open(ACCOUNTS_YAML) as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and "accounts" in data:
            return _resolve_accounts(data["accounts"])
        if isinstance(data, list):
            return _resolve_accounts(data)

    # Fall back to env var (JSON)
    raw = os.getenv(ACCOUNTS_ENV, "")
    if raw.strip():
        data = json.loads(raw)
        if isinstance(data, list):
            return _resolve_accounts(data)
        if isinstance(data, dict) and "accounts" in data:
            return _resolve_accounts(data["accounts"])

    return []


def _resolve_accounts(accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Resolve password_env references and apply defaults."""
    resolved = []
    for acc in accounts:
        resolved_acc = dict(acc)
        password_env = resolved_acc.pop("password_env", None)
        if password_env:
            resolved_acc["password"] = os.environ.get(password_env, "")
        # Defaults
        resolved_acc.setdefault("imap_port", 993)
        resolved_acc.setdefault("smtp_port", 587)
        resolved_acc.setdefault("allowed_users", [])
        resolved_acc.setdefault("allow_all", False)
        resolved_acc.setdefault("skip_attachments", False)
        resolved_acc.setdefault("poll_interval", 15)
        folders = resolved_acc.setdefault("folders", {})
        folders.setdefault("inbox", "INBOX")
        folders.setdefault("sent", "Sent")
        folders.setdefault("drafts", "Drafts")
        folders.setdefault("trash", "Trash")
        resolved.append(resolved_acc)
    return resolved


def get_account(account_id: str) -> Optional[Dict[str, Any]]:
    """Get a single account config by ID."""
    for acc in load_accounts():
        if acc["account_id"] == account_id:
            return acc
    return None


def list_account_ids() -> List[str]:
    """Return all configured account IDs."""
    return [a["account_id"] for a in load_accounts()]
