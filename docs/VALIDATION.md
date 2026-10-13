# v0.1.8 acceptance — 2026-10-13 (America/New_York)

**Development preview.** Standard-only software can be distributed with these
limits; complete dual-host/live-platform acceptance is still pending. Historical
v0.1.0–v0.1.7 evidence remains in [VALIDATION_HISTORY.md](VALIDATION_HISTORY.md).
No real user profile, credential, private route or personal skill is bundled.

## Current scope

| Area | Evidence/status |
|---|---|
| Local profile, preferences, onboarding and role skill lifecycle | Helper tests plus five current v0.1.8 native Codex CLI conversations; confirmed fictional facts, recovery, Codex-only personal skill creation and invocation passed |
| Private backup, restore, history and schema 1→2 migration | Local fictional regression suite; credential/browser exclusion, newer application history, stale plans, tampering, interruption and rollback covered |
| Python portability | 95 tests passed locally and in all five hosted combinations: Linux/Windows 3.10/3.13 and macOS 3.13 |
| Browser/application guards | 21 automated scenarios passed again locally; earlier actual Codex IAB mock evidence retained |
| PDF | Two real Tectonic PDFs passed one-page Letter, extraction/bounds and visual review; default Projects absent and requested Projects order correct |
| Public bundle/Release | First CI's 61-file public bundle verified; all four cloud/local assets byte-identical. Version tags repeat CI before gated prerelease publication |
| Actual Codex conversations | 10 independent CLI conversations passed disk assertions and transcript review, covering onboarding and new maintenance; another blank trial-workspace environment conversation passed |
| Actual Codex browser | Earlier local login/upload/confirmed and unknown-result recovery passed; no live employer application |
| Claude Code | Actual conversations deferred by owner; earlier OAuth 401 unresolved |
| macOS desktop / real Workday | Unverified; hosted helper tests cannot certify a desktop model conversation or employer portal |

## Local knowledge maintenance

Schema 2 adds a persistent workspace UUID and helper-owned preference revision/time.
Schema 1 is preserved and requires a reviewed migration plan; unsupported versions
stop without resetting facts. Active core/role/job/package schemas migrate together.
Old assessments become stale; immutable historical snapshots keep their original
schema. New/resumed initialization never mixes old data with empty new defaults.

Backups use a private allowlist and per-file hashes. Excluded directories are
skipped before reading: tests patch the file reader to fail if credentials/browser
contents are touched. Grants and generated host skills are excluded too. Private
backups remain ignored plaintext career data, distinct from the public ZIP.

Restores verify the archive and current fingerprint, list changed/removed paths,
save a prechange backup and journal writes with undo objects. Populated different
workspace identities, stale plans, traversal/duplicate paths and content tampering
are rejected. Newer current application history, evidence and packages survive
restoring older knowledge; Submitted/unknown attempts remain, grants are cleared,
and prepared attempts are paused. Original uncertain attempts can still reconcile.
Missing personal host skills regenerate through saved role configurations.

Regression coverage includes a denied write followed by complete rollback, a
simulated process interruption that blocks normal operations until recovery, and
preservation of external edits rather than partial rollback. These use fictional
fixtures and guard stubs, not real employer submissions or PDF acceptance evidence.

Two separate fictional default/Projects workspaces produced real PDFs; both PNG
previews were opened and checked for legibility, alignment, clipping and overlap.
The shared template remains SHA-256
`0fb02c175f5366a5f687fd65fd911f3b11ece8111cc273f000b25bf828591915`.
Default PDF SHA-256:
`df31f3d68f7cf42b75c373abecb9a48699566764c642d2565bbc46fbbfafde9a`.
Requested Projects PDF SHA-256:
`881dae18c5d18ee4076399ffcecc72698a14c90028c62052879ba92bb328e9ab`.
A real-PDF private backup restored into a third empty fictional workspace with
identical facts and PDF bytes, no grants, and both personal host skills successfully
regenerated. Skill frontmatter validation and workflow YAML syntax checks passed.

## Executed acceptance

- Windows Python 3.13.1: **95 tests passed**; clean extracted ZIP plus both generic
  host installations also passed **95 tests**. Both local source and extracted
  bundle passed **21 mock browser scenarios**. Core requires only the standard
  library; PDF acceptance used the available local Tectonic/PyMuPDF runtime.
- [First complete GitHub CI run](https://github.com/RF0606/careerAssistant/actions/runs/38433713858)
  at source commit `8010b5571162d5b7417177016f0551a94bf3c6c5` passed every job:
  **95 tests each** on Ubuntu Python 3.10/3.13, Windows Python 3.10/3.13 and macOS
  Python 3.13, **21 browser scenarios**, and independently verified public bundling.
- Downloaded the CI distribution artifact and compared all four files byte for
  byte with the corresponding local build; ZIP, checksum, startup text and
  aggregate checksums matched. The ZIP contains exactly 60 allowlisted source
  files plus the manifest. It contains no local profile, routes, personal skills,
  private backups, credentials or test-results.

This record describes pre-publication source acceptance. Final tagged runs and
published assets can be inspected in
[Actions](https://github.com/RF0606/careerAssistant/actions) and
[Releases](https://github.com/RF0606/careerAssistant/releases); the tag workflow
rechecks the exact final commit, including documentation and manifest updates.

## Post-release real-data preflight

The unchanged v0.1.8 software was tested again through the installed native Codex
CLI 0.162.0-alpha.17.2, retaining the user's existing model and permissions. The
older npm shim was not selected. Every conversation used a new ephemeral session;
this validates disk-based conversational recovery, not a desktop GUI restart.

- Five fictional-user sessions passed initialization, source-backed fact saving,
  unchanged-state recovery, preference selection before private route/skill
  generation, and personal-skill invocation against a complete supplied JD.
  Only the Codex personal skill was requested/generated. Missing communication
  evidence remained unknown; employer/school locations and metrics were not invented.
  Source-only rendering remained draft until a separate actual PDF review.
- Five additional conversations passed backup/history, a preference correction
  that made the old assessment stale, authorized same-workspace restore, schema
  1-to-2 migration, and interrupted-operation recovery. The maintainer explicitly
  converted this fictional fixture's active files to schema 1 and later injected
  interruption after journaling; these are labelled test setups, not real-user
  migration or a desktop process-kill test. The interrupted writer released its
  lock, and the host used maintenance-recover. All original facts/source references
  remained; rollback restored operation-before data byte-for-byte. No grants,
  applications, credentials, browser state or shared source were introduced.
- A separate real Codex CLI environment session in the future trial workspace
  used its project .venv Python, ran filesystem and offline TeX probes, read status
  and saved only the environment checkpoint. The five career core files were
  byte-unchanged, with zero facts, sources, targets, routes, personal skills and
  applications. That workspace was extracted from the checksum-verified public ZIP.
- Fresh project dependencies were pypdf 6.20.1 and PyMuPDF 1.28.2. Actual PDF import
  extracted text, and the same .venv compiled both a separate fictional smoke
  resume and the native conversation's draft. Both one-page Letter images were
  opened and inspected; original template unchanged and Projects absent. The
  native-draft PDF SHA-256 was
  `bda3879f72fbcd6d85e2384533347155bf6646cff4bdd3c3468229d5432cca29`.

All 11 final responses were reviewed along with command-result summaries. Four
nonzero command results were expected schema/interruption guards or optional
searches for absent paths, with successful follow-up; no policy/authentication
failure occurred and no MCP tool call was made. Logs, fictional data, derived
skills and private archives remain under ignored
`test-results/v0.1.8-real-data-preflight/`. An operator-local first-trial plan defines
one user, one selected direction and one full JD, including fact/PDF review and
reopening a session; it stops before submission. No real user data was imported.

This documentation adds post-release evidence; the previously published v0.1.8
ZIP, tag and checksums remain the original immutable release. Actual real-user
acceptance and live Workday behavior are still future work.

## Publishing automation

CI checks the public manifest against actual tracked paths, runs five Python
OS/version combinations and Linux's fictional browser suite, then builds and
independently verifies the four public assets. Release tags repeat the same checks
at the tagged ref, require tag/VERSION/HEAD agreement and publish as prerelease.
Actions are pinned, checkouts do not persist credentials, and contents:write is
limited to the publication job. No model/Workday secrets are used and no private
test evidence is uploaded. See [RELEASING.md](RELEASING.md).

Private acceptance artifacts for this release belong under
`test-results/v0.1.8-maintenance-release/`; no private logs or test workspaces are
published. Hosted macOS helper/cold-start success is new evidence, and does not
replace the still-unverified macOS desktop conversation or live ATS acceptance.
