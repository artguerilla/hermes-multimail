"""Tool handlers for email-multi plugin.

Thin wrapper around config/service/parsing/attachments modules.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import attachments, auth, config, service

def _attachment_cache_dir() -> Path:
    """Return the attachment cache dir under the active Hermes home."""
    cache = config.hermes_home() / "cache" / "email_multi"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


class _DateTimeEncoder(json.JSONEncoder):
    """Serialize datetime/date values as ISO 8601 strings."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def _json(data: Any) -> str:
    return json.dumps(data, cls=_DateTimeEncoder, indent=2, ensure_ascii=False)


def _ok(**kwargs) -> str:
    return _json(kwargs)


def _err(message: str, **kwargs) -> str:
    payload = {"success": False, "error": message}
    payload.update(kwargs)
    return _json(payload)


def _normalize_attachments(values: Optional[List[str]]) -> List[str]:
    paths: List[str] = []
    for value in values or []:
        if not value:
            continue
        converted = attachments.media_path_to_attachment(value)
        if converted and converted.get("path"):
            paths.append(converted["path"])
        else:
            paths.append(value)
    return paths


def _imap_date(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d-%b-%Y")


def _quote_imap_search_value(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _can_use_portable_text_search(value: str) -> bool:
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        return False
    return bool(value)


def _build_imap_criteria(params: dict, include_keyword: bool = True) -> str:
    parts: List[str] = []

    if params.get("unseen_only"):
        parts.append("UNSEEN")
    if params.get("subject"):
        parts.append(f'SUBJECT {_quote_imap_search_value(params["subject"])}')
    if params.get("from"):
        parts.append(f'FROM {_quote_imap_search_value(params["from"])}')
    if params.get("date_since"):
        parts.append(f'SINCE {_imap_date(params["date_since"])}')
    if params.get("date_until"):
        until = datetime.strptime(params["date_until"], "%Y-%m-%d") + timedelta(days=1)
        parts.append(f'BEFORE {until.strftime("%d-%b-%Y")}')
    keyword = (params.get("keyword") or "").strip()
    if include_keyword and _can_use_portable_text_search(keyword):
        # TEXT is the portable IMAP SEARCH key that covers headers and body. The
        # decoded client-side filter below remains the final behavior check.
        parts.append(f"TEXT {_quote_imap_search_value(keyword)}")
    if params.get("has_attachment"):
        # broad server-side prefilter; exact attachment truth comes from fetched message
        parts.append('OR HEADER Content-Type "multipart/mixed" HEADER Content-Disposition "attachment"')

    query = (params.get("query") or params.get("criteria") or "").strip()
    if query:
        upper = query.upper()
        if any(tok in upper for tok in ["UNSEEN", "SEEN", "SINCE", "BEFORE", "FROM", "SUBJECT", "BODY", "TEXT", "HEADER", "FLAGGED", "ALL"]):
            parts.append(query)

    return " ".join(parts) if parts else "ALL"


def _filter_messages(messages: List[Dict[str, Any]], params: dict) -> List[Dict[str, Any]]:
    keyword = (params.get("keyword") or "").strip().lower()
    has_attachment = params.get("has_attachment")
    if not keyword and not has_attachment:
        return messages

    filtered: List[Dict[str, Any]] = []
    for msg in messages:
        if keyword:
            haystack = "\n".join([
                msg.get("subject", ""),
                msg.get("from", ""),
                msg.get("body_text", ""),
            ]).lower()
            if keyword not in haystack:
                continue
        if has_attachment and not msg.get("attachments"):
            continue
        filtered.append(msg)
    return filtered


def email_multi_list_accounts(params: dict) -> str:
    caller = auth.get_caller_identity(params)
    accounts = []
    for acc in config.load_accounts():
        if not auth.is_account_accessible(acc["account_id"], caller):
            continue
        health = service.check_account(acc["account_id"])
        accounts.append({
            "account_id": acc["account_id"],
            "email": acc["email"],
            "imap_host": acc["imap_host"],
            "smtp_host": acc["smtp_host"],
            "password_configured": bool(acc.get("password")),
            "allowed_users": acc.get("allowed_users", []),
            "allow_all": acc.get("allow_all", False),
            "skip_attachments": acc.get("skip_attachments", False),
            "health": health,
        })
    return _ok(success=True, count=len(accounts), accounts=accounts)


def email_multi_poll_inbox(params: dict) -> str:
    caller = auth.get_caller_identity(params)
    account_ids = [params["account_id"]] if params.get("account_id") else config.list_account_ids()
    account_ids = [aid for aid in account_ids if auth.is_account_accessible(aid, caller)]
    limit = int(params.get("limit", 20))
    messages: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for account_id in account_ids:
        try:
            found = service.search_messages(account_id=account_id, criteria="UNSEEN", limit=limit)
            for item in found:
                item["account_id"] = account_id
            messages.extend(found)
        except Exception as e:
            errors.append({"account_id": account_id, "error": str(e)})

    return _ok(success=True, count=len(messages), messages=messages, errors=errors)


def email_multi_list_messages(params: dict) -> str:
    try:
        account_id = params["account_id"]
        auth.assert_account_access(account_id, auth.get_caller_identity(params))
        folder = params.get("folder")
        criteria = _build_imap_criteria(params)
        fallback_criteria = _build_imap_criteria(params, include_keyword=False) if params.get("keyword") else None
        limit = int(params.get("limit", 50))
        messages = service.search_messages(
            account_id=account_id,
            folder=folder,
            criteria=criteria,
            limit=limit,
            fallback_criteria=fallback_criteria,
        )
        for item in messages:
            item["account_id"] = account_id
        return _ok(success=True, count=len(messages), messages=messages)
    except Exception as e:
        return _err(str(e))


def email_multi_search_messages(params: dict) -> str:
    caller = auth.get_caller_identity(params)
    if params.get("account_id"):
        # Single explicit account: enforce strictly
        try:
            auth.assert_account_access(params["account_id"], caller)
        except PermissionError as e:
            return _err(str(e))
        account_ids = [params["account_id"]]
    else:
        # All accounts: silently skip inaccessible ones
        account_ids = [
            aid for aid in config.list_account_ids()
            if auth.is_account_accessible(aid, caller)
        ]
    limit = int(params.get("limit", 50))
    folder = params.get("folder")
    criteria = _build_imap_criteria(params)
    fallback_criteria = _build_imap_criteria(params, include_keyword=False) if params.get("keyword") else None
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for account_id in account_ids:
        try:
            messages = service.search_full_messages(
                account_id=account_id,
                folder=folder,
                criteria=criteria,
                limit=limit,
                fallback_criteria=fallback_criteria,
                include_body=True,
                include_attachments=True,
                save_dir=None,
            )
            for full in messages:
                full["account_id"] = account_id
                if len(full.get("body_text", "")) > 500:
                    full["body_text"] = full["body_text"][:500] + "..."
                results.append(full)
        except Exception as e:
            errors.append({"account_id": account_id, "error": str(e)})

    results = _filter_messages(results, params)
    return _ok(success=True, count=len(results), messages=results[:limit], errors=errors)


def email_multi_search(params: dict) -> str:
    return email_multi_search_messages(params)


def email_multi_read(params: dict) -> str:
    try:
        account_id = params["account_id"]
        auth.assert_account_access(account_id, auth.get_caller_identity(params))
        message_id = params["message_id"]
        folder = params.get("folder")
        include_html = bool(params.get("include_html", False))
        download = bool(params.get("download_attachments", False))
        save_dir = str(_attachment_cache_dir() / account_id / message_id) if download else None

        msg = service.get_message(
            account_id=account_id,
            message_uid=message_id,
            folder=folder,
            include_body=True,
            include_attachments=True,
            save_dir=save_dir,
        )
        if not include_html:
            msg.pop("body_html", None)
        msg["account_id"] = account_id
        return _ok(success=True, **msg)
    except Exception as e:
        return _err(str(e), account_id=params.get("account_id"), message_id=params.get("message_id"))


def email_multi_download_attachment(params: dict) -> str:
    try:
        account_id = params["account_id"]
        auth.assert_account_access(account_id, auth.get_caller_identity(params))
        message_id = params["message_id"]
        attachment_id = str(params["attachment_id"])
        folder = params.get("folder")
        save_dir = _attachment_cache_dir() / account_id / message_id

        msg = service.get_message(
            account_id=account_id,
            message_uid=message_id,
            folder=folder,
            include_body=False,
            include_attachments=True,
            save_dir=str(save_dir),
        )
        attachments_list = msg.get("attachments", [])
        if not attachments_list:
            return _err("No attachments found", account_id=account_id, message_id=message_id)

        selected = None
        if attachment_id.isdigit():
            idx = int(attachment_id)
            if 0 <= idx < len(attachments_list):
                selected = attachments_list[idx]
        else:
            for att in attachments_list:
                if att.get("filename") == attachment_id:
                    selected = att
                    break

        if not selected:
            return _err("Attachment not found", available=[a.get("filename") for a in attachments_list])
        if not selected.get("path"):
            return _err("Attachment metadata found but file was not saved", attachment=selected)
        return _ok(success=True, account_id=account_id, message_id=message_id, attachment=selected, local_path=selected["path"])
    except Exception as e:
        return _err(str(e), account_id=params.get("account_id"), message_id=params.get("message_id"))


def email_multi_send(params: dict) -> str:
    try:
        auth.assert_account_access(params["account_id"], auth.get_caller_identity(params))
        attachments_list = _normalize_attachments(params.get("attachments"))
        msg_id = service.send_email(
            account_id=params["account_id"],
            to=params["to"],
            cc=params.get("cc"),
            bcc=params.get("bcc"),
            subject=params["subject"],
            body_text=params["body"],
            body_html=params.get("html_body"),
            attachments=attachments_list,
        )
        return _ok(success=True, sent=True, account_id=params["account_id"], to=params["to"], subject=params["subject"], message_id=msg_id)
    except Exception as e:
        return _err(str(e), account_id=params.get("account_id"))


def email_multi_reply(params: dict) -> str:
    try:
        auth.assert_account_access(params["account_id"], auth.get_caller_identity(params))
        attachments_list = _normalize_attachments(params.get("attachments"))
        msg_id = service.reply_email(
            account_id=params["account_id"],
            original_uid=params["message_id"],
            body_text=params["body"],
            body_html=params.get("html_body"),
            reply_all=bool(params.get("reply_all", False)),
            attachments=attachments_list,
            folder=params.get("folder"),
        )
        return _ok(success=True, replied=True, account_id=params["account_id"], original_uid=params["message_id"], message_id=msg_id)
    except Exception as e:
        return _err(str(e), account_id=params.get("account_id"), message_id=params.get("message_id"))


def email_multi_list_folders(params: dict) -> str:
    try:
        auth.assert_account_access(params["account_id"], auth.get_caller_identity(params))
        folders = service.list_folders(params["account_id"])
        return _ok(success=True, account_id=params["account_id"], count=len(folders), folders=folders)
    except Exception as e:
        return _err(str(e), account_id=params.get("account_id"))


def email_multi_mark_seen(params: dict) -> str:
    try:
        auth.assert_account_access(params["account_id"], auth.get_caller_identity(params))
        ok = service.mark_seen(params["account_id"], params["message_id"], params.get("folder"))
        return _ok(success=ok, account_id=params["account_id"], message_id=params["message_id"], marked_seen=ok)
    except Exception as e:
        return _err(str(e), account_id=params.get("account_id"), message_id=params.get("message_id"))


def email_multi_delete_message(params: dict) -> str:
    try:
        auth.assert_account_access(params["account_id"], auth.get_caller_identity(params))
        ok = service.delete_message(params["account_id"], params["message_id"], params.get("folder"))
        return _ok(success=ok, account_id=params["account_id"], message_id=params["message_id"], deleted=ok)
    except Exception as e:
        return _err(str(e), account_id=params.get("account_id"), message_id=params.get("message_id"))
