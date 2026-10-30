# v0.1.13 acceptance

**Development preview.** This version repairs the four v0.1.12 reassessment
findings: incompatible Node reuse, lost browser deferral, dependency writes through
external directory links and unusable retained TeX cache after state recovery.
Historical evidence remains in [VALIDATION_HISTORY.md](VALIDATION_HISTORY.md).

## Fixed behavior

- Browser preparation requires Node 20+, paired npm that can run, the tested
  @playwright/mcp@0.0.83 CLI and a real Chromium launch. Existing Node 18 is preserved
  while a compatible private LTS is prepared. A native runtime crash can retry once
  with a verified local runtime; policy/execution denials never trigger fallback.
- Browser/search choices persist separately from capability inspection. Legacy
  deferred steps are retained, ordinary inspect/missing calls cannot revoke them,
  and explicit component resume does not permit unrelated PDF downloads.
- Installer-managed tools, venv/package destinations and pip/npm/TeX/Chromium
  caches/profiles are checked against the actual selected workspace before writes.
  Complete external runtimes are reused without installation into them; incomplete
  linked environments use a local fallback. Normal POSIX interpreter links and
  explicit workspace aliases remain supported. Resolved prefixes prevent recursive
  delegation when a shared runtime is already in use.
- Retained private TeX resources are rediscovered even after recovery clears
  operational steps. An offline anonymous compile validates the actual heading,
  italic, large-header and bullet/special-character fonts before downloads. Failed
  cached compilation remains pending; user deferral is never silently revoked.
- Verified runtime archives move to their stable locations before execution,
  avoiding Windows executable-handle contention during directory renaming.

## Local verification

Windows Python 3.13.1: **197 Python tests passed**, including **78 environment and
setup/recovery tests**. The POSIX-specific venv-link test is skipped on Windows and
executed by Linux/macOS CI. **21 fictional browser scenarios passed** using the
verified managed Node LTS. Earlier Windows sharing, immutable application artifacts,
duplicate identity, role recovery, backups and data migration regressions remain.

A real Chinese/GBK first-use workspace began without Python/PDF dependencies and
with official Node 18 already present. Native bootstrap returned a runnable private
Python. Setup prepared the PDF stack and an empty TeX cache while browser/search
were deferred. Ordinary missing-capability inspection performed no browser install;
only explicit browser resume prepared a separate compatible LTS/MCP/Chromium and
both project configs. Node 18 bytes were unchanged. Offline repetition preserved
config bytes and search deferral remained intact.

Real damaged-state recovery preserved an exact raw-byte backup and continued
deferral. With a deliberately empty global TeX cache, setup rediscovered the
retained private resources, and actual resume compilation succeeded offline both
before and after recovery. The real test also exposed the previously incomplete
anonymous font probe and Windows post-execution directory move; both were repaired
and the affected checks repeated before packaging.

Three actual one-page Letter resumes (default, requested Projects, special
characters) passed extraction and visual PNG review. Projects remain off by
default and appear below Work Experience when requested. The shared template hash
is unchanged: 0fb02c175f5366a5f687fd65fd911f3b11ece8111cc273f000b25bf828591915.

Five fresh native Codex sessions from a repository-external uninstalled public copy
passed initialization, confirmed facts, restart recovery, both private role skills
and invocation. Disk assertions, final answers, actual personal-skill/guide reads,
stored fictional facts and English source-only draft were reviewed. The exercised entry/source-only paths were fingerprint-checked; the later PDF
delegation guard was separately checked by an actual read-only executable-alias
render. No application/grant was created there.

Actual Codex IAB loopback acceptance, separate from headless mocks, passed private
in-memory test login, real-PDF upload, success, uncertain-result duplicate guards,
original receipt/hash reconciliation, fresh-context reauthentication and CAPTCHA
stop. Each fictional job had one POST and one tracker attempt. Artifact credential
scan passed; created tabs and server were closed. No real account/employer was used.

Final publication requires clean ZIP extraction, manifest and both generic skill
copies, the complete Python/browser suites in that extraction, public-data checks,
and successful master/tag CI across five OS/Python combinations. Public assets are
downloaded again and compared byte for byte. Only allowlisted reusable source and
fictional tests ship; private profiles, credentials, caches and evidence do not.

## Remaining acceptance

Claude Code's first conversation was attempted but invalid host authentication
blocked it before any workspace change; it is unverified. macOS desktop/model
conversations and authorized real-employer portals were not exercised. Cloud helper
CI and fictional mock submissions do not replace those scopes. Host trust/reload,
site login and submission authorization remain separate, so this remains a preview.
