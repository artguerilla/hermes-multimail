# Contributing

## Development Setup

```bash
git clone https://github.com/artguerilla/hermes-multimail.git
cd hermes-multimail
pip install -e ".[dev]"
```

## Verification

Before submitting changes, run the full verification suite:

```bash
# Syntax check
python3 -m py_compile email_multi/*.py

# Unit tests
python3 -m unittest

# Linting
ruff check email_multi tests

# Build and package check
python -m build
twine check dist/*
```

## Public Sanitize Check

Before release, run your own private denylist scan outside the repository.
Do not commit private company names, customer names, internal project names,
credentials, local runtime files, or agent-workflow metadata to the public repo.

## Plugin Structure

The plugin must maintain these core files:

- `email_multi/plugin.yaml` — plugin metadata
- `email_multi/__init__.py` — `register(ctx)` entry point
- `email_multi/schemas.py` — tool schema definitions
- `email_multi/tools.py` — tool handler implementations
- `email_multi/skill/SKILL.md` — bundled skill documentation

Additional modules (`config.py`, `auth.py`, `service.py`, `parsing.py`, `attachments.py`)
are internal implementation details.

## Pull Requests

- Keep changes minimal and focused
- Include tests for new behavior
- Update docs for user-facing changes
- Pass all verification checks

## Code Style

- Follow existing conventions in the codebase
- Use `ruff` for linting
- Max line length: 100 characters
- Type hints where helpful
