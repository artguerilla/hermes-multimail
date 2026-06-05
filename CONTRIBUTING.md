# Contributing to hermes-multimail

Thank you for your interest in contributing! This document outlines how to set up your development environment, run tests, and submit Pull Requests.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)
- [Adding New Tools](#adding-new-tools)
- [Security](#security)

---

## Prerequisites

- **Python 3.10+** (3.11 recommended)
- **pip** or **uv** for dependency management
- **pytest** for running tests
- A basic understanding of [Hermes Agent plugin architecture](https://github.com/NousResearch/hermes-agent)

## Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/artguerilla/hermes-multimail.git
cd hermes-multimail
```

### 2. Install dependencies

```bash
# Option A: Standard pip (recommended for most contributors)
pip install -e ".[dev]"

# Option B: uv (faster, if you have it installed)
uv pip install -e ".[dev]"
```

### 3. Configure your local environment

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
# Edit .env with your IMAP/SMTP credentials
```

Then create your `accounts.yaml`:

```bash
mkdir -p ~/.hermes/plugins/email_multi
# Edit ~/.hermes/plugins/email_multi/accounts.yaml
```

### 4. Enable the plugin

In `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled:
    - email_multi
```

Restart Hermes:

```bash
hermes gateway restart
```

## Running Tests

```bash
# All tests (pytest)
python3 -m pytest tests/ -v

# Specific test file
python3 -m pytest tests/test_smoke.py -v

# Specific test class
python3 -m pytest tests/test_access_control.py::TestIsAccountAccessible -v
```

### Test categories

| File | Coverage |
|------|----------|
| `test_smoke.py` | Syntax checks, config resolution, plugin registration |
| `test_config_resolution.py` | Account YAML/JSON loading, env var fallback, defaults |
| `test_access_control.py` | Allowlists, caller identity, PermissionError paths |
| `test_attachments.py` | MIME classification, filename decoding, save-dir logic |
| `test_delete_semantics.py` | Trash/expunge behavior, copy-then-delete |
| `test_imap_search_performance.py` | Batch fetch, Gmail raw search, fallback criteria |
| `test_reply_address_parsing.py` | Reply-To, From, CC extraction and deduplication |

## Code Style

- **Formatting**: Follow PEP 8 with a line length of 120 characters
- **Imports**: Standard library first, third-party second, local last
- **Docstrings**: Use triple-quoted docstrings for all public functions
- **Type hints**: Add type hints to function signatures

We use **Ruff** for linting (configured in `pyproject.toml`):

```bash
pip install ruff
ruff check .
ruff format .
```

## Submitting Changes

### Branch naming

Use descriptive branch names:

```
feat/add-search-by-sender
fix/imap-timeout-handling
docs/update-schema-descriptions
```

### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add OAuth2 support for Gmail accounts
fix: handle IMAP connection timeout gracefully
docs: clarify account_id usage in tool schemas
test: add edge case for empty attachment filenames
```

### Pull Request checklist

- [ ] All tests pass (`python3 -m pytest tests/ -v`)
- [ ] No hardcoded credentials or secrets
- [ ] Docstrings updated for new/modified tools
- [ ] `accounts.yaml` sample updated if config changed
- [ ] README.md updated if user-facing behavior changed
- [ ] No `.env`, `.hermes`, or cache files committed

### Review process

1. Open a Draft PR for early feedback
2. Address all reviewer comments
3. Mark as "Ready for Review" when complete
4. At least one approval required for merge

## Adding New Tools

To add a new tool to the plugin:

1. **Define the schema** in `email_multi/schemas.py`:

```python
_add(
    "email_multi_new_tool",
    "Description of what this tool does.",
    {
        "account_id": {"type": "string", "description": "Account ID"},
    },
    ["account_id"],
)
```

2. **Implement the handler** in `email_multi/tools.py`:

```python
def email_multi_new_tool(params: dict) -> str:
    account_id = params["account_id"]
    auth.assert_account_access(account_id, auth.get_caller_identity(params))
    # ... implementation
    return _ok(success=True, ...)
```

3. **Add tests** in `tests/test_new_feature.py`

4. **Update the bundled skill** in `email_multi/skill/SKILL.md`

5. **Update the README.md** tools table

## Security

- **NEVER commit credentials** — use `password_env` for all secrets
- **NEVER commit `.env` files** — they are in `.gitignore`
- **Test with isolated accounts** — use dedicated mail accounts, not personal inboxes
- **App passwords only** — use provider-specific app passwords, never main account passwords
- **Access control** — always use `auth.assert_account_access()` in tool handlers
- **Fail closed** — if caller identity is unavailable and allowlist is active, deny access

If you discover a security vulnerability, please report it responsibly:
1. Do **not** open a public issue
2. Email: dev@dieartguerilla.de
3. Describe the vulnerability and reproduction steps
4. We will acknowledge within 48 hours and patch promptly

---

Questions? Open a [Discussion](https://github.com/artguerilla/hermes-multimail/discussions) or file a `feature_request` issue.
