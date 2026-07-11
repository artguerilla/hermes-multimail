# AGENTS.md

Repo-canonical worker contract for `hermes-multimail`.

## Canonical precedence

When these layers are present, follow them in this order:
1. `.hermes/project.yaml`
2. `AGENTS.md`
3. `CLAUDE.md` (only if Claude is enabled)
4. agent runtime / local settings

If a higher-precedence layer is missing, do not invent it. Follow the next present layer and report the gap when it matters.

## Repo purpose

- Repo name: `hermes-multimail`
- Purpose: Multi-account IMAP/SMTP email plugin for Hermes Agent
- Primary stack: Python 3.9+, PyYAML, setuptools
- Package: `email_multi` — Hermes agent plugin via entry point

## Control plane and truth model

- Hermes is the orchestrator and normative control plane.
- This repo is a Hermes plugin; `email_multi/plugin.yaml` and `email_multi/__init__.py` are the plugin entry points.
- Global auth, secrets, and MCP state stay outside this repo unless explicitly approved.

## Allowed worker actions by default

Default-safe work in this repo is limited to:
- reading repo files
- reviewing diffs
- writing approved repo-local files
- running local verification declared below
- reporting risks, drift, and verify outcomes

Without explicit approval, workers must not:
- read `.env`, `.env.*`, secret files, auth material, or `~/.hermes`
- install dependencies (use `scripts/setup.sh`)
- mutate external systems (GitHub, mail servers, cloud, etc.)
- push directly to `dev`, `main`, or `staging`
- widen an approved scope

## Verify contract

Run these commands before submitting changes:

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

## Mutation policy

- Mutating jobs require an isolated worktree.
- Work branches follow `agent/<issue>-<slug>` naming.
- PRs target the `dev` branch.
- Direct push to `dev` or `main` is not allowed.

## Escalation rules

Escalate back to Hermes or the user instead of guessing when:
- the task requires `.env`, secrets, auth material, or `~/.hermes`
- the task requires installs or toolchain bootstrap
- the task requires MCP, plugin, auth, cloud, database, or mail setup
- the task requires push, PR creation, or other external mutation without explicit approval
- higher-precedence contract layers drift or conflict
