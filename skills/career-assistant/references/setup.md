# Automatic dependency setup

On initialization/resume, inspect dependencies and the active host's browser/search
APIs. Reuse working installations. Install missing software automatically when
the current workspace/command/network permissions allow it. Do not make users
know commands or edit JSON. Briefly explain the environment preparation, then act.

## Python before Python helpers

1. Prefer an existing Python 3.10+ from a host-provided runtime discovery tool,
   the selected workspace .venv, python/python3, or Windows py -3. Probe the actual
   version. If a host exposes bundled runtime paths, discover them rather than
   assuming a machine-specific location.
2. If none works, run scripts/bootstrap-python.ps1 on Windows or
   scripts/bootstrap-python.sh on macOS/Linux. Pass the selected workspace and,
   when available, an explicit host Python. They reuse working Python first.
   Windows supports -CheckOnly; POSIX accepts --check-only as its second argument.
3. With no Python, the native bootstrap installs a private uv runtime manager from
   the official Astral distribution, then managed CPython 3.13 under
   .career-assistant/tools/python. Windows verifies the official uv asset SHA-256;
   POSIX uses Astral's HTTPS installer in unmanaged mode. No sudo, system Python
   replacement, Windows registry registration, PATH/profile edits or execution
   policy bypass is used. The returned Python is verified before use.
   Windows probes use ASCII JSON for paths, including under GBK output. Reuse the
   returned absolute executable; a successful result verifies that file exists.
4. A denied bootstrap/command requires user permission; do not work around a host
   denial with another executable, shell or write tool. If no runtime can run,
   discuss materials but do not claim saved career initialization.
   The bootstrap also respects a saved installation deferral. Use its explicit
   -ResumeInstallation (Windows) or --resume-installation third argument (POSIX)
   only after the user authorizes the previously deferred environment installation.

Native command shapes (the assistant supplies real paths and executes them):

```text
& <skill>/scripts/bootstrap-python.ps1 -Workspace <workspace> -Python <optional-host-python>
sh <skill>/scripts/bootstrap-python.sh <workspace> <optional-host-python>
```

## Inspect, install and verify

Use the supported Python with the self-contained helper:

```text
python <skill>/scripts/career.py --workspace <root> setup --host codex --browser existing --search existing
```

Set --host claude/both only for the selected hosts. The browser/search values come
from actual host tool inspection: existing, missing, defer (user requested), or
inspect (not established). CLI presence alone is not a browser/session check.
Normally omit --no-downloads; that flag is for explicit offline/deferred acceptance.

The helper runs a resumable installation flow:
- PDF Python packages: reuse a working environment or create/reuse a workspace
  .venv, then install official PyPI binary wheels for pypdf and PyMuPDF. It never
  runs global pip or activates a shell environment. Returned python_executable is
  used for later helpers; render/PDF import can delegate to that selected local
  runtime, so restarting through a different PATH Python does not lose packages.
  A partial venv with missing pip is repaired through local ensurepip first. If a
  minimal OS Python lacks venv/ensurepip, follow the prepared native managed-runtime
  bootstrap automatically when permitted, then resume setup with the new runtime.
  This is a missing runtime component, not permission to replace system Python.
- Tectonic: reuse a working binary or download the matching official GitHub release
  into .career-assistant/tools/tectonic, verify its vendor SHA-256 and test execution.
  Windows x64, macOS x64/arm64 and Linux x64/arm64 have mapped official assets.
- TeX resources: first compile an anonymous canonical-template probe offline.
  If resources are missing and downloads are allowed, warm them with a real
  compilation in a workspace cache, then verify a PDF exists. A successful
  environment probe does not mark any personal resume ready.
- Browser fallback, only when the host browser is missing: reuse Node/npm or install
  a checksum-verified official Node LTS archive locally; install Microsoft's
  @playwright/mcp from the official npm registry, download Chromium and test a
  headless launch. Add only a project career_browser server, preserving existing
  settings. It uses a separate private browser profile and no debugging port.
  No global model, approval, trust or browser configuration is overwritten.
  Conflicting project configuration is preserved for review. Server detection uses
  a TOML parser rather than a text marker: quoted, dotted and inline definitions
  are recognized, and equivalent entries remain byte-unchanged. Candidate TOML
  and every requested host are checked before any write. Python 3.10 uses the
  conditional local tomli dependency; Python 3.11+ uses its standard parser.
  Existing configuration content is never logged.
  Node 20+ and its paired npm must actually execute. This release installs the
  tested @playwright/mcp@0.0.83 package; the MCP CLI must run as well as Chromium
  before any server registration. Node 18 is preserved and skipped. A compatible
  local LTS can coexist under tools/browser-node if tools/node is occupied.
- Search and site authentication are host/account capabilities. Search can use
  existing search tools or the connected browser. No account, paid service, API
  credentials, CAPTCHA/2FA exception or submission permission is installed.

Installed files and operational state stay private under .career-assistant and
the ignored .venv/project host config. Setup writes no career facts, preferences,
routes or application grants. Its state persists at setup/environment.json.
Completed steps are rechecked and reused; installation is not repeated merely
because the user says initialize again.
If the user declines or postpones installation, run setup --defer-installation
to persist that choice. Ordinary later setup calls honor it without downloads.
Use --resume-installation only after the user's later installation authorization;
this flag does not grant OS/host permission or bypass any denial.
Browser/search choices also persist in component_policies, including older saved
deferred steps. Ordinary inspect/missing observations do not revoke them. After
the user explicitly resumes just the browser, use --resume-browser-installation;
it does not authorize PDF downloads. Use --resume-search for that explicit choice.
--resume-installation resumes all components only when that broader authorization
was actually given. Existing host browser availability is separate from permission
to install a fallback later.

Every writable tool, venv, npm/pip cache, Chromium engine/profile and TeX cache
destination must resolve inside the selected workspace. Existing dependency trees
are checked before installer commands. A complete external runtime can be reused
without changes; an incomplete linked venv uses a safe local fallback rather than
external pip. Normal POSIX interpreter links remain valid. Unsafe paths require
configuration review, not a security-policy change.

An existing state file that is damaged, unreadable, structurally invalid or has an
unknown version never becomes a first run and never authorizes downloads. Doctor
reports the review/permission requirement while text/profile/source-only work can
continue. Preserve the file and ask which installation choice the user wants.
After that explicit choice, run recover-setup --choice defer|resume --confirmation
<actual-user-request>. It backs up and hashes the original bytes before writing
fresh operational metadata; it installs nothing and resets no career facts/tools.
Then resume normal setup. A generic --resume-installation cannot silently repair
a broken state. If no Python can run, a separately authorized native bootstrap
may install only that runtime, leaving the old state untouched for this recovery.
The native bootstraps conservatively require this explicit runtime-only choice
when existing JSON cannot be fully validated without Python; they never infer
automatic installation from a last duplicate key. Duplicate keys, non-integer
versions and incomplete/unknown steps are rejected by the helper before writes.
Every existing setup-path component is checked even if the state file is absent;
linked directories cannot redirect state, locks or recovery backups elsewhere.
If doctor reports runtime_required for a missing/broken selected Python, rerun
setup with a working runtime before PDF import/render. Parent Python packages do
not make the failed selected runtime ready. Keep independent profile work moving.
Recovering metadata does not discard reusable TeX resources: the helper discovers
the known private cache and tests it offline even when steps/cache_scope was lost.
Only a failed offline probe can request resource download. The original user
deferral remains in force.

## Actual permission and connection requests

approval_required means explain the named component, installation destination and
specific denied permission, then ask whether the user allows that installation.
For example: “生成 PDF 还缺 Tectonic。当前宿主拒绝了工作区下载/执行；是否允许我在
这个工作区安装它？” Use the host's normal approval mechanism where available.
Once approved, resume the same command. If the user declines, record the deferral
and continue independent profile work. Never change security policy to make it pass.

A network outage, checksum mismatch, unsupported platform, stale installer lock or
configuration conflict is a different result. Follow its exact recovery action;
permission alone does not repair all failures. Preserve active locks until no
installer is running. A denied state write is reported as unsaved, never ready.
If Chromium reports missing OS libraries, inspect the current system-package
permission. Run its prepared system_dependency_command automatically when that
scope is already permitted; otherwise ask the user for the concrete OS-library
installation permission. Never use sudo or weaken policy to gain access.

host_reload_required means binaries/config are prepared, but the host must reload
and expose the server. Codex project config loads only in trusted projects; Claude
may require a project server approval. Ask for that actual trust/tool action when
needed; do not grant it programmatically or assume connection. Check the live API
after reload. Login remains a separate, site-specific user action.

After setup, run init idempotently, doctor --host <active-host> --probe-writes,
inspect actual results, and save the environment checkpoint. Missing optional
tools can leave PDF/browser work pending while facts and preferences continue.
A real resume still requires full compilation, text and actual visual review.

Official references:
- https://docs.astral.sh/uv/reference/installer/
- https://docs.astral.sh/uv/reference/cli/
- https://tectonic-typesetting.github.io/en-US/install.html
- https://tectonic-typesetting.github.io/book/latest/getting-started/first-document.html
- https://github.com/microsoft/playwright-mcp
- https://learn.chatgpt.com/docs/extend/mcp
- https://code.claude.com/docs/en/mcp
