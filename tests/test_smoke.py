"""Smoke tests for email_multi plugin.

Checks two things without network or extra dependencies:
  1. All Python source files in email_multi/ parse cleanly (syntax check).
  2. The _DateTimeEncoder handles datetime/date objects (JSON hardening fix).

Run with:
    python tests/test_smoke.py
or:
    python -m pytest tests/test_smoke.py -v
"""
import ast
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "email_multi"


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


def test_cache_dir_path_uses_underscore():
    """ATTACHMENT_CACHE_DIR in tools.py must reference email_multi (underscore)."""
    source = (PLUGIN_DIR / "tools.py").read_text()
    match = re.search(r"ATTACHMENT_CACHE_DIR\s*=.*", source)
    assert match, "ATTACHMENT_CACHE_DIR not found in tools.py"
    line = match.group(0)
    assert "email_multi" in line, f"ATTACHMENT_CACHE_DIR should use email_multi: {line}"
    assert "email-multi" not in line, f"ATTACHMENT_CACHE_DIR must not use email-multi: {line}"


def test_accounts_yaml_path_uses_underscore():
    """ACCOUNTS_YAML in config.py must reference email_multi (underscore)."""
    source = (PLUGIN_DIR / "config.py").read_text()
    match = re.search(r"ACCOUNTS_YAML\s*=.*", source)
    assert match, "ACCOUNTS_YAML not found in config.py"
    line = match.group(0)
    assert "email_multi" in line, f"ACCOUNTS_YAML should use email_multi: {line}"
    assert "email-multi" not in line, f"ACCOUNTS_YAML must not use email-multi: {line}"


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
        test_cache_dir_path_uses_underscore,
        test_accounts_yaml_path_uses_underscore,
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
