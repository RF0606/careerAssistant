# Career Assistant maintainer handoff

## Ordinary user entry

“帮我初始化信息” means start/resume the user's profile workflow, following
AGENTS.md and skills/career-assistant/SKILL.md. It does not mean improve this software,
initialize Git, create a remote repository or upload anything. README.md is the user guide.

## Maintainer entry

Suggested prompt after extracting this ZIP into a new career-assistant directory:

> 请按 START_HERE_CODEX.md 检查并完善这个项目。先阅读 README、VERSION 和验收记录，
> 检查解压与安装是否完整，运行测试并修复真实问题。使用虚构用户验证初始化、岗位
> skills、PDF 和模拟申请。最后报告公开发布是否就绪、剩余缺口以及可以上传的文件。

1. Read VERSION, README.md, docs/VALIDATION.md and the release manifest. Confirm
   ZIP extracted directly into the project root, without nested project folders.
2. Run `python release.py verify`, the Python unit tests, then install project skills
   for the available host(s). Run `career.py doctor` from the canonical skill scripts.
3. Review the self-contained main skill, structured data interface and private-role generation.
   Confirm init/install create no preset routes; user-selected preferences precede
   generation of private routes/<id>.md documents and matching personal skills.
   Exercise onboarding with fictional users in separate temporary workspaces. Never
   import a real person's private data merely to test functionality.
4. If Node/Playwright is available, `npm ci`, then `npx playwright install chromium`
   and `npm run test:browser`. The mock server is loopback only. Never turn this test
   into a live application. Install PDF requirements and Tectonic for resume QA.
   Run tests/cold_start.py in an ordinary-user environment, including an empty
   dependency venv/PATH and empty offline TeX cache. Follow docs/COLD_START.md.
   Run the supported host browser against docs/HOST_BROWSER_VALIDATION.md's
   fictional fixture; do not substitute headless tests for host browser evidence.
5. Exercise both host natural-language entrypoints and personal role routing where
   accounts are usable. Clearly record permission/auth failures as unverified, not passed.
   `tests/host_smoke.py` starts with NO profile or preinstalled project skill,
   outside the source repo, and runs five fresh sessions:
   initialization, confirmed facts, checkpoint recovery, role creation and invocation.
   Require disk checks AND manual transcript review. Stop on a denied helper;
   explain which permission/login the user must fix. Do not bypass host policy.
   See docs/CODEX_SETUP.md for Windows CLI/config compatibility. Preserve native
   sandbox configuration and use --executable if PATH selects an incompatible CLI.
6. Inspect generated PDF images and text, including optional Projects and special
   characters. Do not replace actual visual inspection with a success assertion.
7. Exercise private backup/restore/history and explicit schema 1-to-2 migration in
   fictional workspaces. Verify excluded credentials/browser files are not read,
   Submitted/unknown attempts survive and interrupted operations can roll back.
   Fix demonstrated failures, update tests and docs/VALIDATION.md with the actual
   result. Keep real-user state, credentials, logs and generated personal skills out
   of tracked files. Regenerate the release manifest after changes.
   Include frozen Submitted/unknown materials across rerender and restore,
   distinct requisitions/title-only user review, invalid preference updates,
   bounded Windows file-sharing retry, interrupted role generation/retry and verification of every requested
   host's skill, and stale role/route context across resume and submission steps.
8. Run `python release.py pack --output outputs/career-assistant-v0.1.12.zip`.
   The pack command also writes startup instructions and SHA256SUMS.txt. Extract
   the final ZIP, verify its manifest, install both host copies and rerun tests there.

## Publishing after maintainer acceptance

The owner's repository name is careerAssistant and its branch is master. Before publishing, run the
release verifier and review `git status`/the actual staged paths. Publish only the
release allowlist; never use a personal data directory as repository content.
The project .gitignore excludes runtime data and installed/generated skill copies.

When the human asks to publish the reviewed result, create their public GitHub
repository and push the clean source. Typical commands, issued separately:

```text
git init -b master
git add README.md LICENSE VERSION AGENTS.md CLAUDE.md START_HERE_CODEX.md .gitignore .gitattributes .github install.py release.py requirements.txt package.json package-lock.json skills tests examples docs release_manifest.json
git commit -m "fix: release Career Assistant v0.1.12"
gh repo create careerAssistant --public --source . --remote origin --push
```

Adjust the version and exact allowlisted paths to the current manifest. Authentication
must belong to the publishing user. Existing remotes/repos must be inspected, not
overwritten. Ordinary user onboarding never runs these commands.

The existing repository uses `.github/workflows/ci.yml` for cross-platform tests
and a verified public bundle. `.github/workflows/release.yml` repeats that workflow
for a version tag, then publishes development-preview assets with repository-scoped
permissions. Read docs/RELEASING.md; a preview Release is not dual-host acceptance.
Keep docs/VALIDATION.md current and move older evidence into VALIDATION_HISTORY.md.

## Maintenance priorities

Keep the public project standard-only: reusable programs, workflows, schemas and
the shared template. Knowledge enrichment happens in each user's local workspace
after download. Do not copy maintainer/user profiles, preferences, routes or
personal skills into shared references to make an onboarding demo appear complete.

Preserve Projects OFF by default, with an optional separate block after Work Experience.
Preserve locally stored Workday username/password pairs and sanitized in-memory filling.
Do not inherit any other user's standing registration or submission permission.
Actual platform support is host-driven; prioritize verified form changes and concise
blocked explanations. v0.1.12 has no hosted model backend or background scheduler.
Current acceptance is development-preview only until both real-host conversation
gates pass. See docs/VALIDATION.md; a safe ZIP alone is not full product acceptance.
