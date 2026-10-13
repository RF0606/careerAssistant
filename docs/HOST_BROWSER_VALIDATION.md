# Codex host-browser mock acceptance

This maintainer test uses a new fictional workspace and loopback server. It never
opens a real tenant, reads real credentials or certifies live Workday behavior.
Ordinary onboarding never runs these generators.

```text
python tests/host_browser_fixture.py --results test-results/host-browser
python tests/host_browser_server.py --workspace <returned-fictional-workspace>
```

Preparation creates random test-only credentials, two full JD assessments and
actual one-page PDFs. Open every preview and check text before visual-review;
status starts needs-visual-review. The server checks the exact credential pair
in memory, disables request logging, binds only 127.0.0.1 and verifies uploaded
PDF SHA-256. JSON contains no passwords or session tokens. Unit byte stubs test
guards only and are never PDF acceptance evidence.

Read the host's current browser documentation, open the returned URL in a work
tab and inspect the real controls. For this fixture only, import
tests/host_browser_fixture.mjs into the approved runtime. Its
createMockHostLoginSession uses the production credential reader and a separate
strictly loopback adapter. It cannot handle real accounts or weaken production
HTTPS/tenant guards. Never print the file/loader result or capture filled values;
save screenshots after login. Use the same login object throughout each run.

Use actual host APIs, not a separately launched headless browser. The npm suite
is complementary evidence. Current Codex uploads use a chooser:

```javascript
const choice = tab.playwright.waitForEvent('filechooser', {timeoutMs: 10000});
await tab.playwright.getByLabel('Resume', {exact: true}).click();
await (await choice).setFiles([verifiedAbsolutePdfPath]);
```

Inspect employer, job, supported fictional answers and the exact ready PDF. Record
the human's actual authorization for these jobs with grant. Review required fields,
prepare, then begin-submit before one click. For host-success observe confirmation
and upload hash, save a screenshot and call outcome confirmed with the latest ID.

For host-unknown the server accepts but deliberately returns an ambiguous result.
Record unknown, reopen a helper process and verify prepare/begin-submit reject
repeats. Close/reopen the browser, inspect auth and reauthenticate in the genuinely
new mock context if required. Do not recreate a stopped login object within a run
to evade its limits. Open Candidate Home through its visible link; match job ID,
original receipt and original PDF hash. Save observed evidence and reconcile the
original attempt. Require one final POST and one tracker attempt per job.
On a visible CAPTCHA stop before filling credentials or clicking Sign in.

The current IAB test found a new tab did not inherit the prior tab's login. This is
an observed host behavior, not a promise for every version/browser. Preserve the
work tab across batches and inspect authentication in new contexts. A login gap
never authorizes another click on an uncertain application.

Keep screenshots, observations and results private. mock-observations.json is
simulated platform evidence; tracker.json is the sole application authority.
Check profile hashes and scan artifacts for the random fixture password in memory,
printing only pass/fail. Preserve failures; never publish test workspaces.
Close created tabs and stop the server when finished.

Production hostBrowserPage(tab) supports async tab.url() and the tab.playwright
locator surface. Real Workday still requires the exact verified HTTPS origin,
safe local imports/file access and guarantees against value logging. Missing any
capability requires manual login, without another connection or debugging port.
Report actual host mock, automated mock and unverified live-platform scope separately.
