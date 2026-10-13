# Workday local credential file

When Workday login is needed, run `career.py --workspace <root> workday-init`.
It creates `.career-assistant/credentials/workday/accounts.txt` if absent and never
overwrites it. The user edits this file locally. Format exactly one pair per line:

```text
username: <your username>, password: <your password>
```

Multiple exact pairs are supported. Never mix a username from one row with a
password from another. The file and all browser state stay inside the ignored
private directory. Do not sync credentials through Git, release ZIPs, email or chat.
Explain local plaintext storage to the user; do not solicit values in a message.

`node scripts/local_credentials.mjs <workspace>` validates only counts and emits
sanitized errors. Never use cat/Get-Content/Read or console.log on this file or the
loader return value. For filling, import createWorkdayLoginSession into the
approved local browser runtime and keep ONE returned session object for the run.
Call session.fill with the live page, workspace, exact verified HTTPS
Workday origin, zero-based pair index and selectors just observed in the UI. The
helper uses variables in memory and sanitizes browser exceptions. After the host
clicks Sign in once and inspects the result, call session.observe(origin, outcome).
Outcomes: rejected, success, captcha, 2fa, sso, locked, network, unknown. Only an
explicit rejected observation enables the next unused pair; all others stop.
Do not recreate the session to retry a stopped tenant. Do not place
literal secrets in tool calls, command arguments, environment variables or scripts.
Disable tracing/debug logging/video that could capture fill values before loading
credentials. If the runtime cannot guarantee this, let the user log in manually.

If the host's browser runtime cannot read local files/import the helper safely,
report that precise capability gap and hand the login to the user. Never create
an unsupported connection to a browser just to bypass that limitation.

Verify employer/tenant and intended account. If already authenticated correctly,
reuse the session. Keep a run-local in-memory ledger keyed by exact tenant/site:
each supplied pair once, at most eight login submissions total, honoring any lower
visible site limit. Advance to the next pair only after explicit credential
rejection. Stop on success, CAPTCHA, 2FA, SSO, lockout/rate warnings, network errors,
pending results or ambiguous state. Preserve ledger across jobs at that tenant in
the same run. Never print usernames/passwords or screenshot an unmasked password.

The helper fills but does not click Sign in. The authorized host clicks once and
inspects the visible result. File access is not permission to register an account,
accept new terms, reset a password or read mail. If supplied pairs fail, ask the
user to establish the account; this version does not inherit any other person's
standing account-registration authorization. Login is not a submitted application.
