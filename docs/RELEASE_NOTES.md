# Career Assistant v0.1.8 — Development preview

Users can ask the assistant to back up, restore and inspect changes to their local
career knowledge. Private backups include sources, facts, preferences, private
routes, resume packages and application evidence; credentials, browser sessions,
submission grants and installed host skills are excluded. Restores verify a plan,
save a prechange backup, preserve newer Submitted/uncertain attempts and support
rollback after interruption. Schema 1-to-2 migration preserves facts and source
references while adding workspace identity and preference revision metadata.

GitHub CI now tests the standard software across Windows, Linux and macOS, runs
fictional browser scenarios and verifies public bundle contents. Version tags run
the same checks before publishing the ZIP, startup guide and SHA-256 files.
Current and historical acceptance records are separated for easier review.

Validation: 95 Python tests passed in each of five hosted OS/Python combinations,
21 fictional browser scenarios passed, clean extraction and both generic skill
installations passed, and two real one-page PDFs were visually checked. The first
CI's four distribution files matched the corresponding local build byte for byte;
the tag workflow repeats checks before publishing this version.

This remains a development preview. Previous Codex conversation and supervised
local browser evidence is retained; this release's maintenance checks are helper
tests. Claude Code conversations remain deferred, macOS desktop conversations
and real Workday/employer submission behavior remain unverified. See
docs/VALIDATION.md for actual scope and evidence.

The public package contains reusable software, workflows, schemas, the unchanged
one-page template and clearly fictional test fixtures. Users provide their own
knowledge locally after download. Projects remain off by default and, when
requested with evidence, appear after Work Experience and before Education.
