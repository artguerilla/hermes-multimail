# AGENTS.md — hermes-multimail

## Project overview

Multi-account IMAP/SMTP email plugin for Hermes Agent. Python 3.9+, entry-point based.

## Key paths

- `email_multi/` — plugin source (service, tools, auth, config)
- `tests/` — unit tests (`python -m unittest`)
- `pyproject.toml` — build config, dev dependencies (ruff, build, twine)
- `accounts.example.yaml` — account config template

## Conventions

- Lint: `ruff check email_multi tests`
- Tests: `python -m unittest`
- Syntax check: `python -m py_compile email_multi/*.py`
- No secrets committed; only `.env.example` allowed
- PRs into `main` must come from `dev` only

## Setup

```bash
python -m pip install -e ".[dev]"
```

## CI

GitHub Actions: CI workflow on `dev` and `main` pushes/PRs.
Runs flow guard, dependabot check, sanitize, tests (3.9–3.12), and package build.
