# v0.1.8 acceptance — 2026-10-13 (America/New_York)

**Development preview.** Standard-only software can be distributed with these
limits; complete dual-host/live-platform acceptance is still pending. Historical
v0.1.0–v0.1.7 evidence remains in [VALIDATION_HISTORY.md](VALIDATION_HISTORY.md).
No real user profile, credential, private route or personal skill is bundled.

## Current scope

| Area | Evidence/status |
|---|---|
| Local profile, preferences, onboarding and role skill lifecycle | Fictional Python helper tests; previously observed Codex conversation evidence retained in history |
| Private backup, restore, history and schema 1→2 migration | Local fictional regression suite; credential/browser exclusion, newer application history, stale plans, tampering, interruption and rollback covered |
| Python portability | 95 tests passed locally on Windows Python 3.13.1; GitHub's Linux/Windows 3.10/3.13 and macOS 3.13 matrix awaiting first run |
| Browser/application guards | 21 automated scenarios passed again locally; earlier actual Codex IAB mock evidence retained |
| PDF | Two real Tectonic PDFs passed one-page Letter, extraction/bounds and visual review; default Projects absent and requested Projects order correct |
| Public bundle/Release | Pinned read-only CI and gated prerelease workflow added; cloud execution and final ZIP checks pending |
| Actual Codex conversations | Earlier initialize/facts/resume/role creation and invocation passed; no new maintenance conversation acceptance run |
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

## Publishing automation

CI checks the public manifest against actual tracked paths, runs five Python
OS/version combinations and Linux's fictional browser suite, then builds and
independently verifies the four public assets. Release tags repeat the same checks
at the tagged ref, require tag/VERSION/HEAD agreement and publish as prerelease.
Actions are pinned, checkouts do not persist credentials, and contents:write is
limited to the publication job. No model/Workday secrets are used and no private
test evidence is uploaded. See [RELEASING.md](RELEASING.md).

Private acceptance artifacts for this release belong under
`test-results/v0.1.8-maintenance-release/`. Update this record with actual local and
cloud results before tagging; do not replace an unverified row with assumptions.
