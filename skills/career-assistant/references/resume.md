# Evidence-based resume tailoring

Read the active role configuration, its personal routes/<id>.md guide in
`.career-assistant`, current profile, relevant source text and the full JD.
Draft claims against evidence IDs; every identity,
date, employer, role, education, skill and bullet must reference usable facts.
The renderer checks references, not the truth of paraphrases: the host must review
whether each claim accurately represents the source and record evidence_review.
Resolve unsupported numbers, certifications, authorship and seniority first.

Build role-specific guidance from the user's target and actual JD responsibilities,
tools, qualifications and deliverables. After the user selects their direction and
preferences, use role-create to save its private role configuration and route document;
do not select a fixed career category. Where domain licences, operating outcomes
or ownership depth matter, seek direct evidence and distinguish transferable work
from direct experience. Without a JD the role configuration remains provisional.

Use only assets/resume-template.tex. Preserve its fonts, US Letter geometry,
headings, spacing, bullet macros and one-page constraint. All external-facing text
is English. The layout is heading, Summary, Skills, Work Experience, Education.
Default Projects is absent. If requested and supported, add a separate Projects
block after Work Experience and before Education. Do not hide project entries in
employment. A standing request sets preferences.include_projects; a one-off request
sets draft.include_projects and project_section_request without changing preferences.

Keep factual titles and dates; never invent a more impressive role. Select the
most relevant strong evidence, trim repetition and weaker bullets before adding
space pressure. Put certifications under Skills, not a new top-level block.
Do not add unsolicited cover letters. The canonical section names stay English.

Produce a structured draft (see data-interface.md and examples), invoke render,
then inspect every generated preview PNG and resume.txt. Verify name/contact
details, section order, line breaks, clipping, overlap, balance and exact source
meaning. One-page/text checks alone do not prove visual quality. Record
visual-review with reviewer and concrete findings only after opening the preview.
If overflow occurs, shorten the draft and regenerate; do not reduce typography,
scale the page or change margins. Missing education/experience requires factual
input, not invented credentials or decorative placeholders.

The package stores JD_snapshot.md, resume.tex, resume.pdf, draft.json, matching
report and validation.json under the private workspace. Only status ready means
automated and visual QA passed against the current profile/assessment. A failed
or source-only build remains draft and is never uploaded automatically.

