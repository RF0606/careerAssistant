# Setup and capability detection

Core helpers require Python 3.10+. They use the standard library for storage,
DOCX/text import and scoring. PDF import needs pypdf; PDF verification/rendering
needs PyMuPDF; generation needs the Tectonic executable on PATH. In the project
use `python -m pip install -r requirements.txt`. When only the skill folder was
installed use `python -m pip install "pypdf>=5,<7" "PyMuPDF>=1.25,<2"`.
Find Tectonic setup at https://tectonic-typesetting.github.io/en-US/install.html.
Tectonic may download its TeX bundle on first compilation. Do not silently claim
offline PDF generation before that cache exists. Missing tools leave sources as drafts.

`python install.py --host codex|claude|both --workspace <root>` installs the project
skill copies. `--scope user` uses the user's skill folders. No system/global config
is changed. It preflights both targets, detects differing versions and backs up
explicit replacements outside discovery directories. Use one canonical source
folder for development, then refresh installed copies. Do not edit copies independently.

The host must inspect its available search/browser tools. A doctor report listing
node or a CLI does not prove browser access. Use the native supported browser tool
first and its documented APIs. If absent, explain Playwright MCP as an optional
dependency: https://github.com/microsoft/playwright-mcp. Its standard setup is
`npx @playwright/mcp@latest`; follow that project's current host-specific configuration
instructions and choose a dedicated local user-data directory under
`.career-assistant/browser`. Configure only with the user's requested environment
scope. Do not silently change all projects' browser settings.

For project browser tests or a trusted Node runtime using the Workday helper:
`npm ci` and `npx playwright install chromium`. These are optional and not required
for profile setup. The browser helper accepts the host's live approved Playwright
page; it does not launch/connect to arbitrary debug ports. If the host runtime
cannot use local module imports safely, ask the user to handle login visibly.

Persist no browser profile outside the ignored private data directory for this
workflow. No CAPTCHA bypass, account-recovery automation or harvested site cookies.
Missing authentication, tools or permissions are specific blockers, not evidence
that an application was submitted. Do not promise a site's continued automation
compatibility from its generic guide.
