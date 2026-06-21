"""Multi-account email configuration.

Reads accounts from EMAIL_MULTI_ACCOUNTS env var (JSON) or
from a config file at $HERMES_HOME/plugins/email_multi/accounts.yaml
(defaults to ~/.hermes when HERMES_HOME is unset).

Each account:
  account_id: gmail
  email: user@gmail.com
  imap_host: imap.gmail.com
  imap_port: 993
  smtp_host: smtp.gmail.com
  smtp_port: 587
  password_env: EMAIL_GMAIL_PASSWORD  # resolved from env (required)
  allowed_users: [user@example.com]
  allow_all: false
  skip_attachments: false
  folders:
    inbox: INBOX
    sent: "[Gmail]/Sent Mail"
    drafts: "[Gmail]/Drafts"
    trash: "[Gmail]/Trash"

Security:
  - Plaintext "password" in config is rejected; use "password_env" only.
  - password_env must resolve to a non-empty value at runtime.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ACCOUNTS_ENV = "EMAIL_MULTI_ACCOUNTS"
HERMES_HOME_ENV = "HERMES_HOME"

_accounts_cache: Optional[List[Dict[str, Any]]] = None
_accounts_cache_time: float = 0
_ACCOUNTS_CACHE_TTL = 60  # seconds


def _clear_accounts_cache() -> None:
    global _accounts_cache, _accounts_cache_time
    _accounts_cache = None
    _accounts_cache_time = 0


def _plugin_dir() -> Path:
    """Return this plugin's own directory."""
    return Path(__file__).resolve().parent


def hermes_home() -> Path:
    """Return the active Hermes home directory.

    Uses HERMES_HOME env var when set; defaults to ~/.hermes.
    """
    env = os.getenv(HERMES_HOME_ENV)
    return Path(env) if env else Path.home() / ".hermes"


def load_accounts() -> List[Dict[str, Any]]:
    """Load account configs from YAML file or env var (cached up to TTL)."""
    global _accounts_cache, _accounts_cache_time
    now = time.time()
    if _accounts_cache is not None and (now - _accounts_cache_time) < _ACCOUNTS_CACHE_TTL:
        return _accounts_cache

    accounts_yaml = _plugin_dir() / "accounts.yaml"
    # Try YAML file first
    if accounts_yaml.exists():
        with open(accounts_yaml) as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and "accounts" in data:
            result = _resolve_accounts(data["accounts"])
            _accounts_cache, _accounts_cache_time = result, time.time()
            return result
        if isinstance(data, list):
            result = _resolve_accounts(data)
            _accounts_cache, _accounts_cache_time = result, time.time()
            return result

    # Fall back to env var (JSON)
    raw = os.getenv(ACCOUNTS_ENV, "")
    if raw.strip():
        data = json.loads(raw)
        if isinstance(data, list):
            result = _resolve_accounts(data)
            _accounts_cache, _accounts_cache_time = result, time.time()
            return result
        if isinstance(data, dict) and "accounts" in data:
            result = _resolve_accounts(data["accounts"])
            _accounts_cache, _accounts_cache_time = result, time.time()
            return result

    _accounts_cache, _accounts_cache_time = [], time.time()
    return []


def _resolve_accounts(accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Resolve password_env references and apply defaults.

    Security: rejects plaintext "password" field; requires "password_env".
    """
    resolved = []
    for acc in accounts:
        resolved_acc = dict(acc)

        # Reject plaintext passwords
        if "password" in resolved_acc:
            raise ValueError(
                "Plaintext 'password' is not allowed. "
                "Use 'password_env' to reference an environment variable."
            )

        # Require password_env
        password_env = resolved_acc.pop("password_env", None)
        if not password_env:
            raise ValueError(
                f"Account '{resolved_acc.get('account_id', '?')}' is missing required 'password_env' field. "
                "Store credentials in environment variables and reference them via password_env."
            )
        password_value = os.environ.get(password_env, "")
        if not password_value:
            raise ValueError(
                f"Environment variable '{password_env}' referenced by account "
                f"'{resolved_acc.get('account_id', '?')}' is not set or empty."
            )
        resolved_acc["password"] = password_value

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
