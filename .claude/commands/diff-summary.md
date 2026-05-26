Summarize the current diff against `$ARGUMENTS` (default: `dev`).

Include:
- changed files
- affected Python/plugin areas
- risks around secrets, auth, live mail, or mailbox mutation paths
- likely review focus
- test impact
- possible scope drift
- whether the change looks ready for verify

Constraints:
- read-only only
- do not modify files
- do not change git state
- do not mutate external systems
