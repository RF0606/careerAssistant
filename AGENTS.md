# Career Assistant project

## Standard distribution boundary

Ship only standard reusable software, workflows, schemas and the shared resume
template. Do not bundle any person's career knowledge, populated profile,
preferences, job-specific routes or generated personal resume-tailor skills.
After downloading, each user supplies and confirms their own knowledge locally;
initialization asks about their goals and preferences before generating private
routes and personal skills. Keep user-specific knowledge in `.career-assistant`
and ignored generated host skills, never in shared source/references or releases.
Fictional fixtures are test material only; they must never seed a real profile.

For “帮我初始化信息”, “初始化职业档案”, or “initialize my career profile”,
read `skills/career-assistant/SKILL.md` and its onboarding reference, then guide the
user through initialization in this workspace. Use the bundled helpers and save
progress. If needed, install project skills with `python install.py --host codex`.
Do not require the user to know command names or hand-edit JSON.

For resume and job requests, use that same skill and its routed references.
Use only this workspace's `.career-assistant` data. Examples are fictional.
Projects are excluded by default; include a separate Projects block below Work
Experience only when the user requests it and has supporting project facts.

Only when asked to maintain/build/release this software, read `START_HERE_CODEX.md`.
Ordinary onboarding never creates a GitHub repository, commits, or publishes data.
Never read Workday credential contents into model-visible tool output.
