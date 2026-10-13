# v0.1.6 acceptance — 2026-10-13 (America/New_York)

## Personal skill generation and recovery

Previously role-create saved a role and route before installing its host skills.
A folder/file conflict or denied write could leave a partial installation, while
checkpoint roles still accepted the route alone. Generation now persists pending
state before installation, requested hosts, expected paths/hashes and sanitized
failure types. Route/skill files use atomic replacement. All requested host files
must match their expected hashes before generation becomes ready or the roles
checkpoint passes. Automation/trial cannot bypass an incomplete selected role.

role-retry reads the saved configuration and host selection, repairs missing or
changed skill files, and preserves the private route and confirmed profile. A
changed role/route requires a reviewed role-create refresh instead. Status/init
rechecks completed installations and reports role_issues, invalidated_steps and
the effective next step without deleting historical checkpoints. Older roles
without a generation record require refresh; no personal data is reset.

Regression checks cover failure on either host, PermissionError, interrupted
pending state, removed/changed skills, legacy records, CLI JSON errors and retry
without an input JSON. Both folder-conflict cases recover the requested pair of
host files while preserving facts, preferences, sources and the private guide.
These are fictional helper tests, not new Claude Code conversation acceptance.

## Role and private-route freshness

Previously only profile/preferences were bound to an assessment. Changing role
focus/guidance or the private route could leave an old ready package usable.
Assessments now store role_context_hash from the role configuration and actual
route bytes. Creation timestamps and installation progress are excluded, so a
no-op regeneration or installation repair keeps unchanged context valid.

Changed context rejects rendering, visual review, application-add, prepare,
begin-submit and trial completion. Reassessment alone cannot validate an old
resume or prepared attempt: regenerate and actually review the PDF. Legacy
assessments without this fingerprint need refresh. Changes to another role do
not invalidate an unaffected package. Submitted/uncertain attempt history stays
intact, and an original uncertain click can still be reconciled with observed
confirmation evidence after the role changes; it cannot be clicked again.

## Current checks and evidence

- **66 Python tests passed**, including 15 new role-lifecycle regressions and all
  existing onboarding, installed-helper, application and release-boundary tests.
- **18 mock browser scenarios passed**, including in-memory fictional Workday
  login through confirmed submission. No real accounts or applications were used.
- Main skill frontmatter validation passed with Python UTF-8 mode. The validator's
  first default-encoding invocation failed under Windows GBK; no source was corrupt.
- A real Tectonic build from fictional Operations data passed one-page Letter,
  bounds, section and UTF-8 extraction checks. The generated PNG was opened and
  inspected: original layout, legible text, correct section order, no clipping or
  overlap, Projects absent. Visual review and the trial checkpoint passed before
  role modification. A subsequent role change rejected review of that actual PDF
  and returned onboarding to trial. Its PDF SHA-256 is
  `e7a2459d9e8cc447aced8c351b6e51d5a03abe02b231302641633ff559290a96`.
- Private evidence is under `test-results/v0.1.6-role-fixes/`; unit PDF stubs are
  explicitly labelled guard fixtures and are not PDF acceptance evidence.

The fixed template SHA-256 remains
`0fb02c175f5366a5f687fd65fd911f3b11ece8111cc273f000b25bf828591915`.
The release contains only standard software/workflows and fictional test material;
personal roles, routes, generated skills and acceptance workspaces stay ignored.

Final-bundle checks use a new extracted directory: verify the manifest, install
both host copies, rerun the Python/mock browser suites and compile/inspect the
requested Projects variant. Check the exact ZIP, startup file and SHA256SUMS.txt;
keep the local release-check results with the private evidence above.

This remains a **development preview**. Actual Codex conversation acceptance below
is prior evidence; this patch was tested through helpers/installed CLI copies and
real PDF checks, not another model conversation run. Claude Code conversations
remain deferred by the owner, and real website submissions remain unverified.

## Previous v0.1.5 acceptance — 2026-10-12

## Standard-only distribution boundary

The owner confirmed that this project distributes only standard reusable software,
workflows, empty schemas, the fixed template and clearly fictional test fixtures.
Users enrich their own knowledge locally after download. Personal facts, preferences,
routes and resume-tailor skills must not be promoted into shared source/references
or release ZIPs. This rule is recorded in AGENTS.md, CLAUDE.md, the main SKILL.md
and README.md. The release verifier rejects private route directories and generated
career-resume-* skills accidentally placed in the public skills tree.

Five release-boundary tests passed, including two added rejection cases for bundled
personal routes and personal skills. Earlier Codex conversation/PDF evidence below
is unchanged; there was no need to rerun it for this distribution-rule update.

## Previous v0.1.4 acceptance evidence

## Codex permission diagnosis and runner repair

The earlier statement that this machine simply needed more Python/workspace
permission was incomplete. The saved user config already permitted full access
and selected the native Windows elevated sandbox. The test used the older npm
CLI 0.135.0 with --ignore-user-config, losing the Windows selection; its recorded
effective sandbox was read-only. That older CLI also could not load the current
app config. The app-bundled 0.162.0-alpha.17.2 CLI loaded it successfully.

Two controlled local probes verified the correction: restoring the Windows
selection enabled Python writes; using the compatible app CLI with retained
configuration and explicit workspace-write enabled writes AND external readback
in the project. A separate test-directory ACL issue was reproduced: owner-only
mkdtemp directories could deny the external verifier access to files made by
the dedicated sandbox account. Test workspaces now inherit the project's ACLs.
No global permissions, PowerShell policy, login or personal data were changed.

The host runner now retains the user's model, Windows sandbox AND selected
permissions rather than silently narrowing them. Explicit workspace-write was
adequate for profile facts but blocked publishing skills into protected .agents;
continuation used the user's already-selected Full access, without changing it.
The runner supports --executable for installations
where PATH selects an older client, and does not misclassify optional MCP 401
startup warnings as host login failure after successful model execution. See
[Codex setup](CODEX_SETUP.md) for desktop/CLI instructions and official references.

Current actual conversation evidence is under
`test-results/codex-fixed/career-host-codex-f21c2a1964e3/`:
initialization, source-backed fact persistence and a separate-session recovery
passed disk assertions. No facts or checkpoint bytes changed during recovery;
no default routes or applications were created. Continuation under
`test-results/codex-fixed/continued-f21c2a1964e3/` passed personal route/skill creation
and actual skill invocation, assessment and source-only rendering. The transcript
shows reads of the generated SKILL.md and private route and successful assess/render
commands. The five conversation scenarios passed; the earlier protected-directory
attempt timed out and remains retained as failed evidence. The 49 Python tests
passed after the runner changes.

The Windows runner now prefers an available codex.exe over an older npm shim.
Consolidated reviewed results are in `test-results/codex-fixed/verified-summary.json`.
The original source-only prompt correctly left the package draft and trial incomplete.
A subsequent explicit PDF trial used the normal helper and existing default Tectonic
cache: one Letter page, extractable UTF-8 text, ready validation and completed trial.
The rendered PNG and text were also independently inspected by the maintainer;
no clipping or overlap, original layout, Projects absent, facts/draft unchanged.
The PDF SHA-256 is `a540bc7ec98a43de5d84b40a4b5a39b631e0b7f7b3c40f7e6f162a14ac597ede`.
An earlier deliberately empty offline cache failed and was honestly retained as
draft; no false PDF success was recorded. Under the earlier workspace-only mode,
doctor could not access pypdf/fitz; the retained user permissions exposed the already
installed dependencies. No new packages or global permissions were required.

Claude Code was skipped at the user's request; its prior OAuth failure remains
unverified. This remains a development preview for the promised dual-host scope.
The current fictional Codex conversation workflow is accepted through the PDF trial;
real websites remain unverified. Earlier PDF/mock acceptance below is separate evidence.

## Previous v0.1.3 acceptance evidence

The clarified initialization flow now generates personal routes on demand. The
download, installation and init command contain/create no preset directions.
During onboarding the host asks for target roles and preferences; role-create only
accepts a direction matching the user's saved targets. It then creates the private
`.career-assistant/routes/<id>.md` document and both selected hosts' personal skills
pointing to that document. Role configs record the path and file hash. The roles
checkpoint requires a generated guide for every selected target. Reopening init
preserves guides, and different users cannot share a guide through the main skill.
Private routes are excluded from public ZIPs.

Current checks: **49 Python tests and 18 mock browser scenarios passed**. Added coverage verifies no creation
before user selection, rejection of an unselected direction, guide persistence and
user isolation, and complete generation for all selected roles before checkpointing.
The fixed template remains unchanged; earlier PDF acceptance and real-host blockers below remain applicable;
this change does not establish real conversation acceptance. New delivery files
are under outputs/; the main skill and generated-skill formats are validated there.

## Previous v0.1.2 acceptance evidence

The fixed career-route directory has been removed at the user's request.
It contained generic guidance, not candidate identity or employment facts, but the
public product no longer encodes that finite set of career directions. Each user
chooses a title and focus; optional tailoring_guidance and JD source references
live in the private role config. Generated personal skills read those values and
the common resume rules. Old schema-1 roles remain readable; legacy route input is
ignored when refreshing skills. A role without linked JD sources is provisional.

Current checks: **45 Python tests passed; 18 mock browser scenarios passed; main
skill validation passed.** New tests exercise an arbitrary non-software direction,
honest unknown eligibility, JD-linked role guidance, and regeneration of old
personal skills without changing profile facts. The fixed one-page template hash
is unchanged. No real-host conversation gate was rerun: the v0.1.1 authentication
and execution-policy blockers below remain unresolved. This version is a development
preview. The latest ZIP and checksums are generated under outputs/.

## Previous v0.1.1 acceptance evidence

**Release decision: development preview only. Not yet accepted as a fully verified
Codex + Claude Code public release.** Both actual host conversation gates remain
blocked by this machine's permissions/authentication. A distributable, privacy-checked
ZIP is not evidence that those conversations passed.

All candidate facts and credentials used in tests were fictional. No live job
applications, registrations, recovery operations or real Workday password reads
were performed. Runtime logs, private fixtures and PDF previews are excluded from
the release. This directory was not a Git repository; no remote, commit or public
publication was created as part of acceptance.

## Existing capabilities and changes validated

The baseline v0.1.0 manifest verified and its 32 core tests and 9 browser scenarios
passed before modifications. Existing source-backed facts, preference storage,
resumable checkpoints, scoring, fixed resume template and application grants were
retained. Version 0.1.1 adds these repairs:

- The main skill explicitly routes resume work into the matching personal skill.
  The v0.1.1 generated skills resolved the main skill, a then-bundled route and current local role
  focus; they contain no candidate identity or employment facts. Role creation
  rejects malformed focus lists and nonexistent source references.
- Source import rejects resolved credential/browser paths before reading them,
  including the otherwise innocently named Workday `accounts.txt`.
- Workday login has a run-local memory ledger shared across jobs at each origin.
  Each exact pair can be used once; only observed rejection permits another pair.
  Pending, success, CAPTCHA, 2FA, SSO, lockout, network and uncertain outcomes stop
  retries. Browser errors and CLI validation return no values. Tracing/logging that
  captures fill values is prohibited; unsupported runtimes require manual login.
- A pre-click user handoff invalidates preparation. Another preparation is needed
  after the blocker is resolved. Outcomes require the latest attempt ID; delayed
  observations cannot mutate a later attempt. Unknown outcomes require a persisted
  click intent. `status` now reports application counts and outstanding next actions.
- The host test starts EMPTY, not from a seeded profile. It uses five separate
  conversations: initialization, confirmed facts, reopening and recovery, role
  generation, and personal-skill scoring/source rendering. Assertions inspect disk
  state and preserve the original profile hash on reopening. Transcript review is
  still required to verify actual skill use and question quality. A host exit code
  or preexisting file alone is never a pass.
- Release packaging produces the ZIP, ZIP checksum, startup instructions and
  SHA256SUMS together. Tests verify private-data exclusion, clean extraction, hashes,
  credential-pattern rejection and refusal to pack changed/unreviewed source.

## Results from this maintenance run

| Check | Actual result |
|---|---|
| Python suite | 43 tests passed, including fresh workspace commands through both installed host copies, checkpoint recovery, source-backed scoring/rendering, stale attempt rejection, uncertain-attempt recovery and release boundaries |
| Browser suite | 18 scenarios passed with Playwright Chromium; all forms and credentials fictional |
| Mock application lifecycle | Upload, final authorization, click intent, visible receipt and Submitted update; missing inputs, CAPTCHA, rejection, unknown response and duplicates also covered |
| Mock Workday chain | Local file initialization preserved contents; memory fill, mock login, upload, authorized submit, receipt and tracker closure passed; tracker contains neither login value |
| Both host installations | Source hashes matched; explicit replacement retained backups outside skill discovery |
| PDF default layout | Operations fixture compiled to one US Letter page; UTF-8 extraction and actual preview inspection passed; no Projects |
| PDF requested Projects | Software fixture compiled to one page; preview/text checked; Projects below Work Experience and above Education |
| PDF special characters | A three-entry layout stress fixture rendered &, #, %, underscore and braces correctly; preview checked with no clipping or overlap |
| Overflow | Excessive fixture produced three pages and failed the readiness gate; template was not shrunk |
| Trial completion | Visually reviewed Operations and Software fixtures reached the completed trial checkpoint through helpers |
| Template preservation | SHA-256 remains `0fb02c175f5366a5f687fd65fd911f3b11ece8111cc273f000b25bf828591915`, identical to the incoming manifest |
| Clean release extraction | Manifest verified at the extracted root; both host installs, all 43 Python tests and all 18 browser scenarios passed; a fresh one-page Software PDF with Projects compiled and was visually/text checked |
| Codex actual conversation | Correct skill/onboarding read; init rejected by execution policy; NO profile/checkpoint written; blocked |
| Claude Code actual conversation | HTTP 401: OAuth access token invalid; NO profile/checkpoint written; blocked |

Environment: Windows, Python 3.13.1, Node 23.6.1, Playwright 1.64.0,
Tectonic 0.17.0, Codex CLI 0.135.0, Claude Code 2.1.140.
Browser ledger tests use clearly labelled PDF stubs. Actual PDF acceptance is the
separate Tectonic run described above; a stub upload is not PDF-layout evidence.
The mock Workday login redirects into the loopback application fixture. It does
not certify any employer's real Workday login or form.

## Host blockers and exact user actions

**Codex:** the fresh run requested `--sandbox workspace-write`, but its helper
execution was rejected and the conversation reported a read-only environment.
The runner correctly failed the file/checkpoint assertions even though Codex
returned exit code 0. Open a trusted test workspace in a Codex session with
workspace writing and Python command execution enabled. If administrator policy
enforces read-only access, its owner must authorize the workspace. Do not bypass
the denial or claim the checkpoint was saved. Rerun the five-stage test there.
The chosen flag follows the [official non-interactive guidance](https://developers.openai.com/codex/noninteractive).

**Claude Code:** run `claude auth login` locally, complete the browser sign-in,
then rerun the five-stage test. Do not paste tokens or passwords into chat.

Neither host reached the later fresh-dialogue stages in this run. Consequently,
full conversational checkpoint recovery, personal-skill generation and actual
personal-skill invocation remain UNVERIFIED in both hosts. Direct helper and
installation tests passed; they are explicitly not substitutes for those gates.
The initial Codex transcript also bundled too many preference topics into one
question; onboarding guidance now explicitly separates those into later turns.
That wording improvement still needs host revalidation once execution is enabled.

Local evidence (ignored, not included in the ZIP):

- `test-results/acceptance/career-host-codex-nq1zgle2/result.json` and its prompt,
  answer and event log: fresh initialization blocked, no files changed.
- `test-results/acceptance/career-host-claude-hdi7dllh/result.json` and event log:
  OAuth 401 before initialization, no files changed.
- `test-results/pdf/`: generated source, text, validation and inspected PNGs for
  operations, software and stress; deliberately failed overflow remains labelled.
- `test-results/extracted-results.json` and `extracted-0.txt` through `extracted-5.txt`:
  commands and results from the independently extracted source.

## Repeatable acceptance

```text
python -m unittest discover -s tests -v
npm ci
npx playwright install chromium
npm run test:browser
python tests/fixtures.py <temporary-directory> --persona operations --compile
python tests/fixtures.py <different-temporary-directory> --persona software --projects --compile
python tests/host_smoke.py codex --results test-results/hosts
python tests/host_smoke.py claude --results test-results/hosts
python release.py verify
```

Host tests retain a unique temporary workspace and private result directory for
inspection. They stop on the first failed stage. A successful five-stage disk test
still says `disk-checks-passed-needs-transcript-review`: inspect commands to confirm
the generated SKILL.md and private role guidance were actually read, facts preserved,
question groups reasonable, no source text treated as permission and no phantom
PDF/submission claimed. For actual PDF output, open every preview before recording
`visual-review`. Do not seed profiles to bypass an initialization failure.

After source review, update the manifest and create the delivery files:

```text
python release.py manifest
python release.py verify
python release.py pack --output outputs/career-assistant-v0.1.6.zip
```

Extract the final ZIP into a new folder. Verify the manifest there, install both
host copies, run the Python/browser tests and compile/inspect a PDF from that
extracted source. Check SHA256SUMS.txt against the exact files being handed over.

## Public release gates

1. Unblock and pass the five fresh-conversation stages in Codex.
2. Restore Claude authentication and pass the same stages there.
3. Review both transcripts and at least one host-driven complete PDF trial.
4. Regenerate acceptance records and the final bundle after those results.

Live LinkedIn, Greenhouse, Lever, Ashby and Workday behavior remains host-, account-
and form-dependent. Validate only during the user's explicitly authorized work;
mock acceptance never certifies real-site submissions. There is no hosted backend
or background scheduler. Preview distribution must retain these limitations.
