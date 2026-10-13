# Browser guides (inspect the current UI; controls vary)

These guides are starting procedures, not a claim of live certification. Use the
supported browser's own documented tools, observed labels/locators and screenshots.
Do not replay stale coordinates, infer hidden API endpoints or bypass site controls.

| Platform | Key checks | Confirmation to observe |
|---|---|---|
| LinkedIn Easy Apply | Verify actual job ID; review every modal step, selected resume, screening answers and follow-company choice. Do not confuse Save with Apply. | Visible application-sent/submitted state for the selected job. |
| Greenhouse | Follow employer board link, check requisition and all required questions; attachment uploads can finish asynchronously. | Explicit application-received/thank-you result tied to this application. |
| Lever | Verify employer posting, contact fields, attachment, custom questions and location eligibility. | Explicit submitted/thank-you result; URL alone is insufficient without page content. |
| Ashby | Check location/team, multipart form, resume upload, consent and screening fields. | Explicit successful application message for the selected role. |
| Workday | Read workday-login.md. Verify exact tenant; upload resume then review every parsed field, employment/education date and section before final review. | Explicit application confirmation or matching submitted entry in Candidate Home. |
| Other/custom | Identify required sections from rendered UI. Reuse read-before-write, review and confirmation rules. | Unambiguous platform confirmation; otherwise Needs user. |

When site behavior differs, inspect the new state and use one targeted repair.
Do not interpret a timeout as rejection or repeat final submission. Stop after two
non-submitting repair attempts on the same control and save a clear blocker.
Login has its separate bounded ledger. Never run browser traces around credentials.
