Review the current branch or the diff against `$ARGUMENTS` (default: `dev`).

Return:
- findings by severity
- missing tests
- safety gaps around secrets, auth, live mail, or mailbox mutation paths
- policy drift versus `AGENTS.md` / `CLAUDE.md`
- scope drift
- verify gaps
- recommendation: `ready`, `needs_changes`, or `split_issue`

Constraints:
- read-only review only
- do not edit files
- do not commit
- do not push
- do not mutate external systems
