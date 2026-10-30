# v0.1.12 acceptance

**Development preview.** This version repairs the four reproduced first-use
issues: Windows Chinese-path probing, ambiguous setup JSON, writes through linked
setup directories and false readiness for a broken selected Python. Historical
evidence is retained in [VALIDATION_HISTORY.md](VALIDATION_HISTORY.md).

## Fixed behavior

- Windows runtime probes use ASCII JSON, round-trip GBK/Unicode paths in both
  Windows PowerShell 5 and PowerShell 7, and verify the returned executable before
  reporting success or saving its pointer. Official uv SHA-256 uses .NET directly,
  avoiding shell module-discovery differences. No global encoding/policy changes.
- Duplicate JSON keys (including nested keys), boolean/float versions, invalid
  numeric constants and incomplete/unknown steps require review before any
  installer or state replacement. Original bytes remain intact. Explicit recovery
  still backs up and hashes them before saving the actual defer/resume choice.
- Setup checks every existing path component before mkdir/lock/state/backup writes,
  even when environment.json is absent. Native bootstraps also reject linked or
  invalid setup paths. Missing files never hide a junction/symlink in a parent.
- Doctor probes the selected workspace Python, including a missing executable.
  Failure clears inherited PDF-package readiness and supplies runtime_required;
  execution denial remains approval_required. PDF import/render stay pending and
  fail before package changes. Text/profile/source-only work remains usable.

## Local verification

Windows Python 3.13.1: **177 Python tests passed**, including **58 environment
tests** and the previous application-artifact, duplicate, role recovery and private
maintenance regressions. **21 fictional Chromium browser scenarios passed.**
Windows executable checks compare file identity so short (8.3) and full path names
for the same file are accepted while Chinese directory names remain intact.

A real Windows PowerShell 5 first-use run hid Python/Node/Tectonic from PATH and
forced GBK output in a Chinese directory. It installed and verified private
CPython, returned an exact runnable path, automatically prepared PDF wheels,
Tectonic, Node, Chromium and both project MCP configs, and warmed an empty TeX
cache. An offline repeat reused completed tools and preserved config bytes. A
missing selected runtime was correctly reported, repaired by setup and rechecked.

Three actual one-page Letter PDFs passed extraction and visual PNG review:
Projects off by default, explicitly requested Projects below Work Experience,
and R&D/C#/percent/underscore characters. The canonical template hash remains
0fb02c175f5366a5f687fd65fd911f3b11ece8111cc273f000b25bf828591915.

Five fresh native Codex sessions started from a repository-external public copy
with no profile or preinstalled project skill. Initialization, source-backed facts,
restart recovery, both selected private role skills and personal-skill invocation
passed disk assertions and transcript/source review. Facts were preserved across
restarts, unknown requirements stayed unknown, source-only remained draft and no
application or submission grant was created in these conversation checks.

The actual Codex IAB (separate from headless tests) passed the loopback login,
real-PDF upload, success receipt, uncertain-outcome duplicate guards and original
receipt/hash reconciliation. Each fictional job had exactly one final POST and
one tracker attempt. A genuinely reopened context required a new sign-in; existing
receipts survived without another application click. Visible CAPTCHA stopped
before filling. Test credentials stayed in memory/private fixture files; artifact
scan passed. Created tabs and the loopback server were closed afterward.

The final public ZIP is extracted, its manifest verified, both generic host copies
installed and the Python/browser suites rerun before publication. Private logs,
runtime tools, credentials, profiles, backups and generated personal skills never
ship. Master and matching-tag CI repeat the five OS/Python combinations, browser
suite and verified four-file release bundle; live results remain in GitHub Actions.

## Remaining acceptance

Claude Code's first conversation was attempted but stopped on invalid host
authentication before any workspace change; it is **unverified, not passed**.
macOS desktop/model conversations and authorized live-employer portals were not
tested. Cloud cross-platform helper tests and fictional mock submissions cannot
replace them. Tool trust/reload, site login and real application authorization
remain separate. The release therefore remains a development preview.
