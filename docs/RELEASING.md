# Maintaining public releases

Only standard source is public. Personal backups and public distribution ZIPs are
different artifacts. Public builds use release.py's closed file/tree allowlist and
reject credential patterns, machine-specific user paths, bundled personal routes
or skills, unexpected files, and tracked paths outside the manifest. User data,
host copies/settings, caches, screenshots and private test evidence remain ignored.

## Review and local acceptance

1. Update VERSION, package.json, package-lock.json and storage.VERSION together.
   Document the final behavior and remaining limitations in README.md,
   docs/VALIDATION.md and docs/RELEASE_NOTES.md; retain older evidence in
   docs/VALIDATION_HISTORY.md.
2. Run `python -m unittest discover -s tests -v`, `npm ci --ignore-scripts`,
   `npx playwright install chromium` and `npm run test:browser`. Review real PDF
   output when its generation or data context changes. Actual model conversations
   and live employer sites remain separate acceptance scopes.
3. Review `git diff` and the exact intended public paths. Run
   `python release.py manifest`, then `python release.py verify`. Stage only those
   reviewed paths and run `python release.py check-git` before committing.
4. Run `python release.py pack --output outputs/career-assistant-v<VERSION>.zip`.
   Verify the generated ZIP, START_HERE.txt, .zip.sha256 and SHA256SUMS.txt. Extract
   into a fresh directory, verify its manifest and install the selected host copies.
   For the CI bundle helper, use a **new dedicated** output directory:
   `python tests/release_bundle.py --output <empty-directory>`; it rejects extra
   files. It requires Git, whereas ordinary downloaded users need only install.py
   and the career helpers. Public ZIP metadata/order and companion text are fixed
   for reproducible builds from identical source bytes.

## GitHub automation

CI runs for master pushes, pull requests, manual runs and reusable calls. It checks
the tracked allowlist and runs the Python suite on Linux/Windows Python 3.10 and
3.13 plus macOS Python 3.13. Linux also runs the fictional Playwright mock scenarios.
After all tests pass, the verified four-file public bundle is available as a
short-lived Actions artifact. Tests use no Codex/Claude credentials or real career
data. They do not log in to real Workday or submit to employers.

Actions are pinned to reviewed commit SHAs. Checkout leaves no Git credential in
the worktree, CI has contents:read, and only the final Release job gets contents:write.
No private test-results or local backup archives are uploaded. See the official
[reusable workflow guide](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows).

Once the reviewed master commit passes CI, create an annotated version tag
matching VERSION, then push that specific tag. Do not force or replace a tag:

```text
git tag -a v0.1.12 -m "Career Assistant v0.1.12 development preview"
git push origin v0.1.12
```

The Release workflow checks out that tag and runs the same CI against its exact
commit. It verifies tag/VERSION/HEAD agreement, rebuilds and checks the public ZIP
and companion hashes, then uses
[gh release create](https://cli.github.com/manual/gh_release_create) with
`--verify-tag --prerelease`. Only the ZIP, ZIP checksum, startup guide and aggregate
checksums are attached. All current releases remain development previews until
the current validation matrix demonstrates complete product acceptance.

For a transient failure, inspect the failing job and rerun it. Manual Release
dispatch accepts an existing matching tag. If a Release already exists, creation
stops; inspect its assets rather than silently overwriting or deleting a published
version. A tag/version mismatch, changed manifest, private tracked path or failed
test stops publication. Authentication must belong to the publishing owner;
ordinary onboarding never tags, commits, pushes or creates Releases.
