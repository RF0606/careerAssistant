# Job discovery and scoring

For discovery, read target directions, preferences and relevant profile evidence.
Use the host's available search/browser tools. Prefer the employer's full current
posting. Save title, employer, location, URL, requisition ID if present, captured
time and the complete JD. Closed listings and duplicates are not new applications.
If tools are unavailable, accept pasted JD text and report that live search is
unavailable. Do not substitute title-only summaries for the full JD.

Map each requirement to fact IDs, explanation and match: direct, transferable,
none, unknown. Positive matches require documented or user-confirmed sources.
Distinguish missing information from actual incompatibility. Classify dominant
work before selecting a role; hybrid titles do not override responsibilities.

Rubric 1.0 uses must-have weight 3 and other requirements weight 1. Direct evidence
earns 1, transferable evidence .5, none/unknown 0. Show unknown weight alongside
the numerical fit score, not as confirmed lack of ability. Eligibility is a separate
yes/no/unknown assessment covering the posting's mandatory authorization, location,
credential and other non-negotiable gates. If a gate is unknown, ask before applying.
Preference score is the percentage of known preference criteria satisfied; list
unknown criteria separately. Do not hide an eligibility failure behind a high score.

`assess` stores the mapping with profile/preference hashes and rubric version.
After a resume exists, the renderer separately checks specified JD keywords in its
actual text. Missing keyword definitions are unmeasured, not automatically covered.
Use truthful keywords in context; never add unsupported terms for points. Explain
that semantic fit and exact string coverage measure different things and neither
predicts the employer's actual screening decision.

No universal score threshold blocks a user's explicit resume request. User-chosen
application exclusions control which jobs enter a batch. Do not inherit sample
salary floors, posting-age caps, role allocations or career-level assumptions.
For every recommendation provide the strongest evidence, material gaps, unknowns,
and one useful next action. Refresh source hashes before reusing old analyses.
