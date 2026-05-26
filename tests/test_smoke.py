"""Smoke tests for email_multi plugin.

Checks without network or extra dependencies:
  1. All Python source files in email_multi/ parse cleanly (syntax check).
  2. The _DateTimeEncoder handles datetime/date objects (JSON hardening fix).
  3. HERMES_HOME-aware path resolution for config and attachment cache.

Run with:
    python tests/test_smoke.py
or:
    python -m pytest tests/test_smoke.py -v
"""
import ast
import importlib.util
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "email_multi"


def _load_config():
    """Load config.py directly (bypasses __init__.py) for isolated runtime tests."""
    spec = importlib.util.spec_from_file_location("_test_email_multi_config", PLUGIN_DIR / "config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_syntax():
    """All .py files in email_multi/ must parse without syntax errors."""
    errors = []
    for py_file in sorted(PLUGIN_DIR.glob("*.py")):
        try:
            ast.parse(py_file.read_text(), filename=str(py_file))
        except SyntaxError as exc:
            errors.append(f"{py_file.name}: {exc}")
    assert not errors, "Syntax errors found:\n" + "\n".join(errors)


class _DateTimeEncoder(json.JSONEncoder):
    """Inline mirror of the encoder in tools.py — tested here without full import."""

    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def test_datetime_encoder_datetime():
    dt = datetime(2024, 6, 1, 9, 30, 0)
    result = json.loads(json.dumps({"dt": dt}, cls=_DateTimeEncoder))
    assert result["dt"] == "2024-06-01T09:30:00", result["dt"]


def test_datetime_encoder_date():
    d = date(2024, 6, 1)
    result = json.loads(json.dumps({"d": d}, cls=_DateTimeEncoder))
    assert result["d"] == "2024-06-01", result["d"]


def test_datetime_encoder_nested():
    payload = {"messages": [{"date": datetime(2024, 6, 1)}]}
    result = json.loads(json.dumps(payload, cls=_DateTimeEncoder))
    assert result["messages"][0]["date"] == "2024-06-01T00:00:00"


def test_hermes_home_in_config():
    """config.py must define hermes_home() reading HERMES_HOME env var, using email_multi path."""
    source = (PLUGIN_DIR / "config.py").read_text()
    assert "def hermes_home" in source, "config.py must define hermes_home() function"
    assert "HERMES_HOME" in source, "config.py must reference HERMES_HOME env var"
    assert "email_multi" in source, "config.py must use email_multi (underscore) in path"
    assert "email-multi" not in source, "config.py must not use email-multi (hyphen)"


def test_attachment_cache_uses_hermes_home():
    """tools.py must route attachment cache through hermes_home(), not ~/.cache."""
    source = (PLUGIN_DIR / "tools.py").read_text()
    assert "hermes_home" in source, "tools.py must use hermes_home() for cache path"
    assert ".cache" not in source, "tools.py must not hardcode ~/.cache"
    assert "email_multi" in source, "tools.py must use email_multi (underscore) in path"
    assert "email-multi" not in source, "tools.py must not use email-multi (hyphen)"


def test_hermes_home_default():
    """hermes_home() returns ~/.hermes when HERMES_HOME is not set."""
    env_backup = os.environ.pop("HERMES_HOME", None)
    try:
        cfg = _load_config()
        assert cfg.hermes_home() == Path.home() / ".hermes", (
            f"Expected {Path.home() / '.hermes'}, got {cfg.hermes_home()}"
        )
    finally:
        if env_backup is not None:
            os.environ["HERMES_HOME"] = env_backup


def test_hermes_home_custom():
    """hermes_home() returns the HERMES_HOME value when the env var is set."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HERMES_HOME"] = tmp
        try:
            cfg = _load_config()
            assert cfg.hermes_home() == Path(tmp), (
                f"Expected {tmp}, got {cfg.hermes_home()}"
            )
        finally:
            os.environ.pop("HERMES_HOME", None)


def test_load_accounts_uses_hermes_home():
    """load_accounts() reads accounts.yaml under hermes_home(); returns [] when absent."""
    env_accounts_backup = os.environ.pop("EMAIL_MULTI_ACCOUNTS", None)
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HERMES_HOME"] = tmp
        try:
            cfg = _load_config()
            result = cfg.load_accounts()
            assert result == [], f"Expected [] with no accounts.yaml, got {result}"
        finally:
            os.environ.pop("HERMES_HOME", None)
            if env_accounts_backup is not None:
                os.environ["EMAIL_MULTI_ACCOUNTS"] = env_accounts_backup


def test_no_module_level_mkdir_in_tools():
    """tools.py must not call mkdir at module level (no import-time side effects)."""
    source = (PLUGIN_DIR / "tools.py").read_text()
    lines = source.splitlines()
    in_function = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("def ") or stripped.startswith("class "):
            in_function = True
        if not in_function and "mkdir" in stripped:
            raise AssertionError(
                f"tools.py calls mkdir at module level (outside any function): {line!r}"
            )


def test_tools_has_datetime_encoder():
    """tools.py must define a _DateTimeEncoder class."""
    source = (PLUGIN_DIR / "tools.py").read_text()
    assert "_DateTimeEncoder" in source, "tools.py must define _DateTimeEncoder"
    assert "isoformat" in source, "tools.py encoder must call .isoformat()"


if __name__ == "__main__":
    tests = [
        test_syntax,
        test_datetime_encoder_datetime,
        test_datetime_encoder_date,
        test_datetime_encoder_nested,
        test_hermes_home_in_config,
        test_attachment_cache_uses_hermes_home,
        test_hermes_home_default,
        test_hermes_home_custom,
        test_load_accounts_uses_hermes_home,
        test_no_module_level_mkdir_in_tools,
        test_tools_has_datetime_encoder,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as exc:
            print(f"  FAIL  {t.__name__}: {exc}")
            failed += 1
    if failed:
        print(f"\n{failed} test(s) failed.")
        sys.exit(1)
    print(f"\nAll {len(tests)} smoke tests passed.")
