# CLAUDE.md

Repo-local Claude adapter guidance for `hermes-multimail`.
This file is a thin execution adapter for Claude Code. It is **not** the canonical source of truth for the repo.

## Canonical precedence

When these layers are present, follow them in this order:
1. `.hermes/project.yaml`
2. `AGENTS.md`
3. `CLAUDE.md`
4. Claude runtime / local settings

If a higher-precedence layer is missing, do not invent it. Follow the next present layer and report the missing contract when it matters.

## Repo purpose

Use this repo to develop and review the Python Hermes mail plugin in `email_multi/`.
The repo can affect IMAP/SMTP behavior, message parsing, attachments, and mailbox mutation paths, so Claude must stay conservative.

## Claude role

Claude is especially useful here for:
- repo review
- implementation inside an approved file scope
- verification planning
- test-gap analysis
- safety review for mail, secrets, and auth boundaries
- documentation and change summaries

Claude must not:
- become a second source of truth
- override `AGENTS.md`
- treat live mail connectivity as a default verify path
- read `.env`, `.env.*`, secret files, auth material, or `~/.hermes`
- mutate live Hermes mail configuration
- enable MCPs, plugins, or global Claude config from this repo

## Operating pattern

1. Inspect the relevant repo files and tests.
2. Reduce ambiguity before writing code or docs.
3. Work only inside the approved local file scope.
4. Use the smallest repo-safe local verify packet that proves the change.
5. Stop and escalate if the task appears to need secrets, live mail access, installs, or external mutation.

## Verify contract

Hermes Verify is normative.
Claude-run verify is worker/adapter verify only and does **not** replace Hermes Verify.

Use `.hermes/project.yaml` as the canonical verify contract when it is present.
Use `AGENTS.md` and known repo-safe local checks only as adapter guidance when the canonical contract is absent or incomplete.
If `.hermes/project.yaml`, `AGENTS.md`, and `CLAUDE.md` drift, stop and report the drift instead of choosing silently.

Default local verify for this repo:
- `python3 -m py_compile email_multi/*.py`
- `python3 -m unittest`

Targeted `python3 -m unittest tests/...` runs may be added when directly relevant.
Do not require live IMAP/SMTP connections, live mailbox state, or auth-backed Hermes runtime state for default verify.

## Git and external mutation policy

Without explicit Hermes + user approval, do not:
- commit
- push
- open PRs
- mutate external systems
- install dependencies
- read or modify `.env`, `.env.*`, secret files, or `~/.hermes`
- run live mailserver tests
- send, reply, delete, move, or mark messages against real accounts

## Escalation rules

Escalate back to Hermes or the user instead of guessing when:
- the task requires secrets or auth material
- the task would use live IMAP/SMTP or real mailbox state
- the task needs dependency installation
- the task needs push or PR actions without approval
- higher-precedence policy layers are missing or conflicting in a way that blocks safe execution
