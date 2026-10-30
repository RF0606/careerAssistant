# First use on a new computer

Open the downloaded project and say **帮我初始化信息**. The host performs the
checks and saves progress; examples below are for troubleshooting/maintainers.
No personal knowledge or role directions come with the download.

Select an existing Python 3.10+ from python, python3, py -3 or the host's local
runtime discovery. Use its absolute path if PATH selects an older interpreter.
If none exists, the assistant runs the native bootstrap to install managed CPython
privately in the selected workspace, using the official Astral distribution. If
runtime download/execution is denied, it explains the exact permission and asks
the user before resuming. No system Python, registry or PATH changes are made. Helpers
reject Python 3.8/3.9 specifically before writing career data or installing skills.
Do not claim saved progress until a helper actually succeeds.

Windows probes exchange interpreter paths as ASCII JSON, so a Chinese directory
also works when Python uses GBK stdout. The final absolute executable is checked
before success and before saving the runtime pointer. No console/global encoding
or shell policy change is needed.

Setup validates its full directory chain before creating state or locks, even
when environment.json is absent. Linked directories and ambiguous JSON (duplicate
keys, incorrect version types or incomplete/unknown steps) require review without
downloads or replacement. A missing/broken selected Python makes doctor report
runtime_required and leaves PDF import/render pending; rerun setup using a working
Python. Text/profile/source-only steps remain available.

The browser fallback requires Node 20+ and a working paired npm. Node 18 is never
treated as compatible with the tested MCP/Playwright dependencies; setup prepares
a private official LTS when allowed. MCP CLI and actual Chromium launch are both
verified before project registration. Existing Node installations are preserved.
Browser/search deferrals persist independently of capability inspection; resume
only the component the user authorizes. All writable dependency/cache destinations
are checked against the workspace, and retained private TeX resources are
rediscovered after installer-state recovery before requesting another download.

| Missing capability | Available now | Next action |
| --- | --- | --- |
| pypdf | Text/Markdown/DOCX, conversational facts, scoring | Setup installs the local official wheel when permitted |
| PyMuPDF | Profile, role skills, scoring, resume.tex | Setup installs and imports the QA package before compilation |
| Tectonic | Profile, scoring, source-only resume | Setup downloads and verifies the official local binary |
| TeX cache | Profile and source-only resume | Setup warms an anonymous canonical-template compile |
| Browser or Node CLI | Profile, scoring, available PDF tools | Inspect host APIs; install the private fallback only when missing |
| Writes denied | Discuss materials | Explain the denied step and ask permission; do not bypass denial |

The assistant first inspects the host's actual browser/search APIs, then normally
runs the installer automatically with the appropriate existing/missing/defer flags:

```text
python skills/career-assistant/scripts/career.py setup --host codex --browser existing --search existing
```

It installs missing PDF wheels/Tectonic, verifies a canonical template compilation,
and prepares a local Node/Playwright browser fallback only when required. State
is saved privately at setup/environment.json. After a denied operation, ask for
that specific permission; do not change host policy or use a different tool to
bypass rejection. Installation and project config do not establish host trust,
browser connection, site login or a verified personal resume. Recheck after reload.

The assistant can also run:

```text
python skills/career-assistant/scripts/career.py doctor --host codex --probe-writes
python skills/career-assistant/scripts/career.py doctor --pdf-smoke
```

Normal doctor is read-only. --probe-writes creates/removes small empty test files
in private data and selected host skill paths, reporting failed paths/error types.
It creates no routes, facts or preferences. OS checks cannot certify host command
policy. --pdf-smoke compiles a small non-personal probe with --only-cached, makes
no downloads and never marks a resume ready. Passing covers only the probe's TeX
resources; a real resume still needs full PDF/text/visual QA.

Use a project .venv and its Python directly. Activation is unnecessary, so changing
PowerShell execution policy is unnecessary. See the official
[venv guidance](https://docs.python.org/3/library/venv.html).

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe skills/career-assistant/scripts/career.py doctor
```

macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python skills/career-assistant/scripts/career.py doctor
```

Reuse an existing compatible .venv rather than recreating it. Use the same chosen
interpreter for later helpers. If venv/ensurepip is missing from an OS Python,
select a complete supported distribution; do not silently install globally or run
sudo. Doctor next_actions supplies interpreter/venv commands as argument arrays.

Use an official [Tectonic binary](https://tectonic-typesetting.github.io/en-US/install.html)
for the OS/architecture in a local tools directory, exposing it to the current
session PATH. Preserve global shell profiles. A binary on PATH proves neither a
working cache nor network access. Missing tools, downloads and timeouts leave
sources as draft. Browser setup can be deferred; use supported host APIs first.
See [Codex permissions](CODEX_SETUP.md) and [browser QA](HOST_BROWSER_VALIDATION.md).

Maintainer cold-start reproduction:

```text
python tests/cold_start.py --results test-results/cold-start
```

Use python3 on POSIX if needed. This creates a new fictional workspace and a venv
without pip/PDF packages or optional executables on PATH. It checks empty init,
role generation, scoring, drafts and informative PDF failures. Windows and Linux
ordinary-user checks passed. macOS has instructions and still needs a real Mac run.
