"""Access-control enforcement for email-multi plugin.

Caller identity is resolved in priority order:
  1. params["caller"] — explicit identity in the tool call
  2. EMAIL_MULTI_CALLER env var — set by the gateway/operator

When an account has a non-empty allowed_users list and allow_all is False,
access is denied if the caller is not on the list.  If caller identity is
unavailable in that configuration the plugin fails closed (denies access).

Accounts with an empty allowed_users list (the default) are treated as
unrestricted — this preserves backward compatibility for direct/operator use.
"""

import os
from typing import Optional

from .config import get_account

CALLER_ENV = "EMAIL_MULTI_CALLER"


def get_caller_identity(params: dict) -> Optional[str]:
    """Return the caller's email address (lowercased) or None if unavailable."""
    caller = (params.get("caller") or "").strip()
    if caller:
        return caller.lower()
    env_caller = os.getenv(CALLER_ENV, "").strip()
    if env_caller:
        return env_caller.lower()
    return None


def _account_allows(acc: dict, caller: Optional[str]) -> bool:
    if acc.get("allow_all", False):
        return True
    allowed = [a.lower() for a in acc.get("allowed_users", [])]
    if not allowed:
        return True  # no allowlist configured — unrestricted by default
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
        return
    if caller is None:
        raise PermissionError(
            "Access denied: caller identity unavailable and account has allowlist"
        )
    if caller.lower() not in allowed:
        raise PermissionError(
            f"Access denied: account '{account_id}' restricted to {acc['allowed_users']}"
        )
