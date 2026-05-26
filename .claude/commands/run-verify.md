Run the canonical local verify commands for this repo.

Rules:
1. Prefer commands declared in `.hermes/project.yaml` when that file is present.
2. Use `AGENTS.md` and `CLAUDE.md` only as adapter guidance and summaries.
3. Hermes Verify remains normative; this command is worker/adapter verify only.
4. If `.hermes/project.yaml`, `AGENTS.md`, and `CLAUDE.md` disagree, stop and report drift.
5. Report exact commands run, pass/fail status, and short failing excerpts.
6. If mutation happened and verify did not run, do not mark the task done.

Default local verify baseline for this repo:
- `python3 -m py_compile email_multi/*.py`
- `python3 -m unittest`

Targeted `python3 -m unittest tests/...` runs may be added when directly relevant.
Do not use live IMAP/SMTP, real mailbox state, `.env`, or `~/.hermes` as part of default verify.

Return:
- Commands run
- Result per command
- Files touched
- Final status: `pass`, `fail`, or `blocked`
