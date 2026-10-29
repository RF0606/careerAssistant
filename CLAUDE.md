# Career Assistant project

Read `AGENTS.md` for the shared project workflow. For “帮我初始化信息” or
“initialize my career profile”, read `skills/career-assistant/SKILL.md` and begin
the resumable onboarding workflow. If project skill discovery is needed, run
`python install.py --host claude`; reopen the session if the skill list is stale.
Follow the setup reference first: detect/reuse dependencies and automatically
install missing workspace-local components when permitted. Ask only for a required
permission, preserving the user's deferral. Tool trust/reload and site login remain
separate user actions; never modify global approval or security settings.

The distribution is standard-only. Build this user's knowledge, preferences and
personal routes/skills locally after their answers; never add those materials to
shared source or treat fictional fixtures as default user knowledge.

Use the skill's portable Python helpers and the current user's local workspace.
Do not depend on Codex-specific APIs. Browser capability is discovered at runtime.
For private backups/restores/history or schema upgrades, follow the skill's
data-maintenance reference; never publish personal backup ZIPs.
Read `START_HERE_CODEX.md` only for explicit software maintenance/release requests.
