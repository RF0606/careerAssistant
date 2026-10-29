# v0.1.11 acceptance

**Development preview.** This release protects saved installation choices and
registers browser MCP configuration by TOML semantics. It also publishes the
previously local environment/bootstrap and application-artifact repairs.
Historical evidence remains in [VALIDATION_HISTORY.md](VALIDATION_HISTORY.md).

## Fixed behavior

- A missing setup-state file is distinct from one that is damaged, unreadable,
  linked, structurally invalid or on an unsupported version. The latter stops
  downloads, preserves the original and reports the required review/permission.
  Ordinary resume flags cannot silently replace it.
- recover-setup requires an explicit defer/resume choice and actual confirmation,
  verifies a raw-byte backup before replacing operational metadata, installs no
  software and resets no career facts, tools or application history. Recovery
  checks the installer lock and concurrent edits. Core text/source-only work can
  continue while PDF tooling remains pending.
- Existing MCP servers are identified using a real TOML parser. Quoted, dotted and
  inline equivalents remain unchanged; conflicting/invalid/unappendable config is
  preserved. Every requested host and candidate document is checked before writes.
  Linked host files cannot modify global/outside-workspace settings. Python 3.10
  has a conditional local tomli dependency; parser worker results contain only
  boolean metadata, never existing configuration contents.
- Windows PowerShell 5 native-runtime handling reads uv stdout/stderr separately
  and checks its exit code, so successful progress output is not a false failure.
  It does not change shell execution policy, global PATH or registry settings.

## Local acceptance

Windows Python 3.13.1: **167 source tests passed**, including 48 environment tests
and the prior application/role/maintenance regressions. **21 fictional browser
scenarios passed.** Coverage includes corrupt/missing-version/unreadable state,
no install even with a generic resume flag, explicit raw-byte recovery, structured
doctor/PDF errors, equivalent quoted/dotted/inline TOML, candidate validation,
multi-host preflight and linked/global config preservation. Python 3.10 parser
compatibility is included in the CI matrix with its conditional dependency.

A real fictional PDF passed one-page Letter, text extraction and actual PNG
inspection. The canonical template hash remains
0fb02c175f5366a5f687fd65fd911f3b11ece8111cc273f000b25bf828591915.
Final ZIP extraction, both host installations and the Python/browser suites are
rechecked before publication; exact private run results remain local.

Two actual Codex conversations verified that broken state remains unchanged
until a user choice, then exact original bytes are backed up and continued
deferral is saved without software installation. A Windows PowerShell 5 run
also prepared only the private Python runtime after explicit authorization,
left damaged state untouched until recover-setup, and restored deferral with an
exact backup. These use isolated fictional workspaces, not real career data.

## Public release checks

Public source, manifest and four handoff assets use the closed allowlist.
Private setup state/tools, host settings, backups, browser data, generated personal
skills and test evidence never ship. CI runs its five OS/Python combinations,
browser mocks and verified bundle for master and again for the matching version
tag. Publication stays a prerelease until the separate product acceptance gates
are satisfied; actual run status is available in GitHub Actions.

## Remaining acceptance

Cloud helper tests do not replace a macOS desktop/model conversation, Claude Code
conversation or authorized live-employer portal acceptance. Prior Windows PDF,
native first-use, dependency installation and browser evidence is retained with
its original version scope. No real credentials or employer application are used.
