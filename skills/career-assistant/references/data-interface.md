# Local helper interface (schema 2, rubric 1.0)

Resolve `career.py` relative to this skill. All commands accept a leading
`--workspace <path>`; the current directory is the default. JSON input files belong
inside the user's private folder. Helpers print non-secret results; never use
profile inputs to hold passwords or sensitive identity numbers.

```text
python <skill>/scripts/career.py --workspace <root> init
python <skill>/scripts/career.py --workspace <root> doctor --host codex --probe-writes
python <skill>/scripts/career.py --workspace <root> doctor --pdf-smoke
python <skill>/scripts/career.py --workspace <root> setup --host codex --browser existing --search existing
python <skill>/scripts/career.py --workspace <root> recover-setup --choice defer --confirmation <actual-user-request>
python <skill>/scripts/career.py --workspace <root> import-source <file> --kind document
python <skill>/scripts/career.py --workspace <root> profile-update --input <private-json>
python <skill>/scripts/career.py --workspace <root> preferences-update --input <private-json>
python <skill>/scripts/career.py --workspace <root> checkpoint <stage> --note <brief-note>
python <skill>/scripts/career.py --workspace <root> role-create --input <private-json> --host both
python <skill>/scripts/career.py --workspace <root> role-retry <role-id>
python <skill>/scripts/career.py --workspace <root> assess --input <private-json>
python <skill>/scripts/career.py --workspace <root> render <job-id> --input <private-draft-json>
python <skill>/scripts/career.py --workspace <root> visual-review <job-id> --input <private-review-json>
```

## Sources and facts

Setup is a separate operational workflow with no career facts or grants. Its
resumable state is private at setup/environment.json and is excluded from career
backups. Browser/search values must reflect the host's actual tool inspection;
missing installs the private browser fallback, while defer records the user's
choice. Omit --no-downloads during normal permitted installation. Statuses include
ready, partial, approval_required, host_reload_required and setup_in_progress.
Check each step, state_saved and next_action; neither CLI presence nor software
installation is proof of site login or a ready personal PDF. See setup.md for
native no-Python bootstrapping and the user permission flow.

Import returns a generated source_id. Profile update shape:

```json
{"facts":{"name":{"text":"A fictional example name","category":"identity","status":"user_confirmed","source_ids":["source-id-returned-by-import"],"confirmation":"Actual user confirmation wording"}}}
```

Statuses: documented, user_confirmed, estimated, unconfirmed. IDs use lowercase ASCII
letters/digits/hyphens, at most 64 characters. Correcting confirmed facts needs
top-level change_confirmation. Updates merge into existing facts, never replace
the entire profile. Source content is stored separately with hashes and import time.

## Preferences and roles

Preferences-update accepts a partial object with only known keys:
targets (ordered objects/strings), locations, work_authorization, compensation,
work_modes, commute, contracts, travel, start_date, exclusions, include_projects
(boolean, default false), submission_policy (per-application or per-batch, initially null).
Lists must remain arrays: unknown targets/locations/authorization/work modes/
contracts/exclusions use []. Targets are nonempty strings or objects with a
nonempty id/title; id uses the normal ID rules and optional priority is a positive
integer. Compensation uses an object ({} when unknown); optional commute/travel
answers and start_date may be null. Invalid changes are rejected before any write.
If an older version saved a malformed field, status reports the field and
preferences-update can correct it without resetting other values or facts.
The host records the user's actual choice.

Role-create requires id, title and a nonempty focus list for any user-selected
direction. Optional tailoring_guidance is a list of direction-specific writing
priorities derived by the host from that user's facts and full JDs. Optional
jd_source_ids link to imported JD sources. No linked JD means provisional true.
There is no fixed direction enum or bundled role guide. Legacy route fields are
accepted but ignored; schema-1 files need the explicit migration below. The direction
must match a user-selected ID or title in preferences.targets. After that selection,
role-create writes routes/<id>.md inside `.career-assistant`, stores its relative
route_path and route_sha256 in the role config, and creates each requested host's
personal skill pointing to the guide. It never writes user routes into the shared
installed skill. Init/install alone create no routes. Regenerate an old personal
skill with role-create from its selected config if it has no private guide.
Generated skills read the current private route, preferences and facts; guidance
does not serve as factual evidence or grant submission permission.

The role's generation record stores status pending/ready, requested hosts, each
skill's relative path/SHA-256, context_hash and sanitized failures (path and error
type only). Writes are atomic per file; interrupted generation stays pending.
Without --host, a refresh preserves that saved host list. New directions infer
the installed host (.claude or .agents); the canonical source defaults to Codex.
An explicit --host overrides that selection. Doctor infers the same active host.
role-retry reads the saved role and host selection, repairs installation only,
and returns ready after verifying every file. It rejects changed role/route context
and unselected directions. Resolve write permissions/path conflicts before retrying.
Checkpoint roles, automation and trial require complete selected-role installations.
Status reports role_issues and invalidated_steps for previously completed steps;
these are computed from current files without deleting historical checkpoints.

## Assessment

Input has job, requirements, eligibility, preference_matches:

```json
{
  "job":{"id":"example-job","company":"Fictional employer","title":"Example role","role_id":"chosen-role","url":"https://example.invalid/jobs/123","captured_at":"2026-01-01T00:00:00Z","full_jd":true,"text":"The full captured JD, not a title or invented summary."},
  "requirements":[{"requirement":"A real JD requirement","must_have":true,"match":"direct","evidence_ids":["confirmed-fact-id"],"rationale":"Explain actual evidence","keywords":["exact supported JD term"]}],
  "eligibility":[{"criterion":"Required work authorization","result":"yes","reason":"Explain the confirmed fact and JD requirement"}],
  "preference_matches":[{"criterion":"Work mode","result":"unknown","reason":"Posting does not specify"}]
}
```

No direct match without usable evidence IDs. Eligibility/preference results are
yes/no/unknown. Full JD is required for scores. The host is responsible for truthful
mapping and full capture; scripts cannot independently certify a webpage.

Assessments bind profile_hash, preferences_hash and role_context_hash. The latter
includes the role configuration and actual private route bytes; timestamps and
installation progress are excluded. Legacy assessments without it require refresh.
Changed context blocks rendering, visual review, application-add, prepare, final
click preparation and trial completion. Reassess, regenerate and actually review
the PDF; reassessment alone cannot validate an old package. Changes to another
role do not invalidate this role's assessment. After a final click, reconciliation
of that original attempt remains available even if the role has since changed.

## Draft and PDF review

Every claim is `{ "text": "...", "evidence_ids": ["fact-id"] }`.
Draft fields: evidence_review, header.name, optional header.headline, header.contacts,
summary, skills (label + items of claims), experience, education. Entries contain
organization, dates, title, optional location (all claims), optional bullets (claims).
Optional projects use the same entry shape. include_projects true requires either
the saved preference or project_section_request for this one resume. The generated
section goes below Work Experience and above Education. Actual fictional examples
are generated by tests/fixtures.py; never copy their facts into real profiles.

Visual-review input: passed true, reviewer and notes, after actually opening all
previews and checking extracted text. Renderer stores source/PDF hashes, page count,
sections and bounds; status stays needs-visual-review until that observation.

## Application lifecycle

```text
career.py application-add <job-id>
career.py application-add <job-id> --review-input <private-duplicate-review-json>
career.py grant --input <grant-json>
career.py prepare <application-id> --input <review-json>
career.py begin-submit <application-id>
career.py outcome <application-id> --input <observation-json>
```

Different verified requisition IDs at one employer remain separate despite matching
titles. Matching canonical URLs or employer/requisition IDs cannot be overridden.
For a title-only match without distinct known IDs, duplicate-review JSON requires
job_id, application_ids (all current ambiguous IDs), user_confirmation (actual human
wording), and evidence explaining the separate postings. Review is saved on the
new record and cannot bypass an original unknown submission.

Grant JSON: job_ids, max_submissions, user_request (actual human request).
Prepare JSON: grant_id, all_required_fields_reviewed true, unresolved_fields [],
review_evidence, answers [{field,value,fact_ids,high_impact}]. User-confirmed evidence
is required for high-impact answers. Browser controls, attachment and all required
questions must be inspected even if answers is empty for a simple form.

Prepare saves immutable materials at packages/<job-id>/attempts/<attempt-id>/.
Its resume_path points to that exact PDF; draft_resume_path is the mutable draft
used to check that pre-click inputs have not changed. snapshot.json records hashes
for the PDF, available source/report files and the assessed facts/preferences.
Begin-submit returns resume_path and pdf_sha256 as well as attempt_id. Subsequent
rendering preserves these snapshots. Legacy clicked attempts are moved to a frozen
PDF only when its original hash verifies; missing/mismatched originals stop before
the live package is overwritten. Recover the original from a verified local backup.

Begin-submit persists an unknown attempt before the host clicks once. Outcome
JSON: result confirmed/failed/unknown/needs-user, detail, next_action. Include the
latest attempt_id returned by prepare/begin-submit whenever an attempt exists;
late observations for older attempts are rejected. A needs-user observation before
clicking pauses preparation; review and prepare again after resolving the blocker.
Unknown is only valid after begin-submit. Confirmed
additionally requires observed_confirmation true, confirmation_text, confirmation_url,
evidence_path relative to `.career-assistant`. Evidence must already exist and be
nonempty. After an uncertain click, failed requires verified_not_submitted true
based on actual observations. Do not fabricate evidence files from a desired result.

Tracker statuses are Pending, Needs user, Blocked, Submitted. The root records count
matches the list length. Writes use an exclusive lock and atomic replacement. A
stale lock is not automatically stolen: inspect processes and the last attempt
before manually removing it. Unknown schema versions are preserved and rejected.
Atomic replacement briefly retries Windows sharing/access conflicts. Persistent
denials still fail while preserving the original; host policy is never bypassed.

## Knowledge maintenance

Read [data maintenance](data-maintenance.md) for conversational decisions. New
workspaces use schema 2 and a persistent UUID in workspace.json; preferences have
helper-owned revision/updated_at fields. Normal commands preserve and reject schema
1 until migration; no mixed-version defaults are written. Immutable history
snapshots retain their original schema, separate from active files.

```text
career.py backup --label manual
career.py backup-verify <private-backup.zip>
career.py history --limit 20 --path profile.json
career.py restore-plan <private-backup.zip>
career.py restore --plan <returned-plan-id> --confirmation <actual-user-request>
career.py migrate-plan
career.py migrate --plan <returned-plan-id> --confirmation <actual-user-request>
career.py maintenance-recover
```

Backup returns path/hash/count and exclusions. History returns metadata and hashes,
without profile values. Plan returns changed/removed paths, source/target schema
and whether existing knowledge is affected; it never returns backup contents.
Restore/migrate recheck the archive and current fingerprint, save a prechange
backup and journal atomic file writes with undo objects. Changed/stale plans stop.
Restore into a populated different-UUID workspace is rejected; use a separate empty
workspace rather than mixing people. The same workspace's newer application history
and associated artifacts remain; contradictions stop for review. All old grants
are cleared, prepared attempts paused, and Submitted/unknown attempts preserved.
Maintenance-recover rolls back an interrupted operation after hash checks. Files
changed outside that operation are preserved for manual review, never overwritten.
