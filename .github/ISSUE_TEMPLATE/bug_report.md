---
name: Bug Report
about: Report a bug in hermes-multimail
title: ''
labels: bug
assignees: ''
---

## Summary

Brief description of the bug.

## Environment

- **Hermes core version**: (e.g., `hermes --version` output)
- **hermes-multimail version**: (git commit SHA or branch)
- **Python version**: (e.g., `python3 --version`)
- **OS**: (e.g., Ubuntu 24.04, macOS 15)
- **Mail providers affected**: (e.g., Gmail, Outlook, custom IMAP)

## Steps to Reproduce

1. Configure accounts.yaml with ...
2. Call tool `email_multi_XXX` with params: `{...}`
3. Observe error ...

## Expected Behavior

What should happen.

## Actual Behavior

What actually happened (include error messages).

## Error Logs

```
Paste relevant error output here
```

## Configuration

Share your `accounts.yaml` configuration (redact passwords/credentials):

```yaml
accounts:
  - account_id: ...
    email: ...
    imap_host: ...
    # (redact password_env values)
```

## Additional Context

Any other relevant information (e.g., specific IMAP server quirks, large message sizes, folder naming conventions).
