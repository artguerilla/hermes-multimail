"""Access-control enforcement for email-multi plugin.

Caller identity resolution (fail-closed by default):
  1. EMAIL_MULTI_CALLER env var — trusted runtime identity set by the gateway
  2. params["caller"] — ONLY when EMAIL_MULTI_TRUST_CALLER_PARAM=true

By default params["caller"] is NOT trusted. Set EMAIL_MULTI_TRUST_CALLER_PARAM=true
if your Hermes gateway injects a verified caller identity into tool call params.

When an account has a non-empty allowed_users list and allow_all is False,
access is denied if the caller is not on the list.  If caller identity is
unavailable in that configuration the plugin fails closed (denies access).

Accounts with an empty allowed_users list (the default) also fail closed —
explicit allowlists or allow_all=true are required for any access.
"""

import os
from typing import Optional

from .config import get_account

CALLER_ENV = "EMAIL_MULTI_CALLER"
TRUST_CALLER_PARAM_ENV = "EMAIL_MULTI_TRUST_CALLER_PARAM"


def get_caller_identity(params: dict) -> Optional[str]:
    """Return the caller's email address (lowercased) or None if unavailable.

    Identity sources (in priority order):
      1. EMAIL_MULTI_CALLER env var — always trusted
      2. params["caller"] — only when EMAIL_MULTI_TRUST_CALLER_PARAM=true
    """
    env_caller = os.getenv(CALLER_ENV, "").strip()
    if env_caller:
        return env_caller.lower()

    if os.getenv(TRUST_CALLER_PARAM_ENV, "").lower() == "true":
        caller = (params.get("caller") or "").strip()
        if caller:
            return caller.lower()

    return None


def _account_allows(acc: dict, caller: Optional[str]) -> bool:
    if acc.get("allow_all", False):
        return True
    allowed = [a.lower() for a in acc.get("allowed_users", [])]
    if not allowed:
        return False  # fail-closed: no allowlist configured
    if caller is None:
        return False  # fail-closed: allowlist present but identity unavailable
    return caller.lower() in allowed


def is_account_accessible(account_id: str, caller: Optional[str]) -> bool:
    """Return True if caller may access account_id."""
    acc = get_account(account_id)
    if not acc:
        return False
    return _account_allows(acc, caller)


def assert_account_access(account_id: str, caller: Optional[str]) -> None:
    """Raise PermissionError if caller may not access account_id.

    Passes silently when the account does not exist so the service layer can
    return its own "Account not found" error.
    """
    acc = get_account(account_id)
    if not acc:
        return
    if acc.get("allow_all", False):
        return
    allowed = [a.lower() for a in acc.get("allowed_users", [])]
    if not allowed:
        raise PermissionError("Access denied: account requires allowlist configuration")
    if caller is None:
        raise PermissionError("Access denied: caller identity unavailable")
    if caller.lower() not in allowed:
        raise PermissionError("Access denied: caller not authorized for this account")
