# AGENTS.md

Repo-canonical worker contract for `hermes-multimail`.

This file is the canonical repo-local policy layer for agent work in this repository.
If `.hermes/project.yaml` is present, it outranks this file. Otherwise, this file is the canonical repo contract.

## Canonical precedence

When these layers are present, follow them in this order:
1. `.hermes/project.yaml`
2. `AGENTS.md`
3. `CLAUDE.md`
4. agent runtime / local settings

If a higher-precedence layer is missing, do not invent it. Follow the next present layer and report the missing contract when it matters.

## Repo purpose

`hermes-multimail` is a Python-based Hermes mail plugin.
It exposes multi-account IMAP/SMTP mail tools from the `email_multi/` package and is verified locally with tests under `tests/`.

Because this repo can affect real mail accounts, mailbox contents, and auth-backed Hermes plugin state, the default safety posture must be stricter than a normal local utility repo.

## Control plane and truth model

- Hermes remains the orchestrator and normative control plane.
- Repo-local docs and Claude files are worker guidance, not a replacement for Hermes policy.
- Global Hermes config, auth, accounts, and live plugin enablement stay outside this repo unless explicit Hermes + user approval is given.
- Do not treat Claude guidance as a second source of truth.

## Default safe posture

Default-safe work in this repo is limited to:
- reading repo files
- reviewing diffs
- writing approved repo-local files
- running local syntax and unit-test verification
- reporting risks, drift, and verify outcomes

Without explicit Hermes + user approval, do not:
- open live IMAP connections
- open live SMTP connections
- send real emails
- reply to real emails
- mark real messages seen or unseen
- delete, move, or otherwise mutate real mailbox contents
- read `.env`, `.env.*`, secret files, auth material, or `~/.hermes`
- modify live Hermes plugin configuration
- install dependencies
- modify global Claude or Codex configuration
- push directly to `dev`, `main`, or `staging`

## Verify contract

Hermes Verify is normative.
Worker-run verify is supportive only and does **not** replace Hermes Verify.

When `.hermes/project.yaml` is present, use it as the canonical verify contract.
When it is absent, use this repo-safe local baseline:
- `python3 -m py_compile email_multi/*.py`
- `python3 -m unittest`

Targeted `python3 -m unittest tests/...` runs may be added when directly relevant to the changed scope.
Default verify must remain local and must not require live accounts, real mailbox state, or mailserver connectivity.

## Review and implementation posture

- Prefer the smallest safe diff.
- Keep changes repo-local and reversible.
- Prefer unit tests, mocks, and local parsing checks over runtime or live-service checks.
- Distinguish clearly between local verification and live runtime validation.
- Do not add hidden automation, hidden hooks, or undocumented side effects.
- Re-read changed files before reporting completion.

## Branch and mutation rules

- Use scoped branches for work.
- Never push directly to `dev`, `main`, or `staging`.
- Do not commit, push, open PRs, or mutate external systems without explicit Hermes + user approval.
- Do not broaden an approved file scope without a new approval step.

## Escalation rules

Escalate back to Hermes or the user instead of guessing when:
- the task requires `.env`, secrets, auth material, or `~/.hermes`
- the task would use live IMAP or SMTP
- the task would mutate a real mailbox or send real mail
- the task requires dependency installation
- the task requires push, PR creation, or other external mutation without explicit approval
- higher-precedence contract layers drift or conflict
- the required verification appears to depend on live runtime state rather than local tests
