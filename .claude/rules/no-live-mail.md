Do not use live IMAP or live SMTP without explicit Hermes + user approval.
Do not send real mail, reply to real mail, or mutate real mailbox contents without explicit Hermes + user approval.
Do not mark messages seen, unseen, deleted, moved, or trashed against real accounts as part of default work.
Do not run runtime or mailserver tests that depend on real accounts, real mailbox state, `.env`, or `~/.hermes` unless explicitly approved.

Default verify must stay local, offline-safe, and repo-contained.
