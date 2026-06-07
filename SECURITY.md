# Security

## Threat Model

This plugin connects to live IMAP/SMTP mail servers and can read, send, and delete
emails. The security model assumes the plugin runs in an untrusted agent environment
where tool call parameters may be manipulated.

## Default Security Posture

### Fail-Closed Access Control

The plugin denies access by default. To access an account, one of the following must
be satisfied:

1. The account has `allow_all: true`, or
2. The account has a non-empty `allowed_users` list AND a verified caller identity
   matches an entry in that list.

If no caller identity can be established, all accounts with allowlists are denied.
Accounts with neither `allowed_users` nor `allow_all` are also denied.

### Caller Identity

Caller identity is resolved in strict priority order:

1. **`EMAIL_MULTI_CALLER`** environment variable — always trusted. Set this in your
   runtime environment to the authorized email address.
2. **`params["caller"]`** — only trusted when `EMAIL_MULTI_TRUST_CALLER_PARAM=true`.
   By default this parameter is **not** trusted, as tool call parameters can be
   manipulated by the agent.

### Password Handling

- **Plaintext passwords are rejected.** The `password` field in accounts config will
  cause a `ValueError` at load time.
- **`password_env` is required.** Each account must specify a `password_env` field
  referencing an environment variable containing the actual credential.
- The environment variable must be set and non-empty at runtime.

### Error Messages

Error messages are sanitized to prevent information leakage:

- Passwords are never included in error output
- Allowlist contents are not exposed in denial messages
- Account existence checks do not leak which accounts are configured

## Recommendations

- Use dedicated mail accounts, not personal inboxes
- Use app-specific passwords (especially Gmail with 2FA)
- Set `skip_attachments: true` for accounts that should not download files
- Restrict `.env` file permissions: `chmod 600 ~/.hermes/.env`
- Set `EMAIL_MULTI_CALLER` in your gateway environment for access control
- Only enable `EMAIL_MULTI_TRUST_CALLER_PARAM` if your Hermes gateway verifies caller identity

## Reporting Vulnerabilities

Please do **not** open a public GitHub issue for security vulnerabilities.

Report vulnerabilities by email: **info@dieartguerilla.de**

Include affected version or commit SHA, reproduction steps, and expected vs. actual
behavior.
