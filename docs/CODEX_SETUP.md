# Codex initialization permissions

Career Assistant needs Python execution and writes in the chosen career workspace.
It does not require unrestricted access to the entire computer.

## Desktop app

Open the extracted project root, then use the permissions control below the
composer. Choose a profile that permits workspace writes and local commands,
such as Ask for approval or an available workspace profile. If this session already
has Full access, no additional permission change is needed for initialization.
Then say “帮我初始化信息”.

If an organization enforces read-only access, ask its administrator to authorize
the workspace. Changing PowerShell's script execution policy does not resolve a
Codex `rejected: blocked by policy` decision.

See the [official sandbox and approval guidance](https://learn.chatgpt.com/docs/sandboxing).

## Windows CLI

Check which installation is actually being invoked:

```powershell
Get-Command codex -All
codex --version
codex.exe --version
codex doctor --summary
```

An older npm shim can take precedence over the desktop app's CLI. If it cannot
load the app's current config, choose the compatible installed executable by its
full path, or update the standalone CLI through its normal supported installer.
If `codex.exe` resolves to the compatible app CLI while `codex` selects an older
npm shim, use `codex.exe -C .` to retain your existing settings. The Windows test
runner also prefers an available codex.exe before falling back to the shim.
Do not change global permissions just to hide a config-version mismatch.

For a verified CLI path, start an interactive project session:

```powershell
$careerCodex = '<full path to your verified codex.exe>'
& $careerCodex -C . --sandbox workspace-write --ask-for-approval on-request
```

In that session, say “帮我初始化信息”. `workspace-write` allows ordinary local
commands and project writes; requests beyond that boundary can ask for approval.
Creating personal skills in the protected `.agents/skills` directory can require
an additional approval. In a trusted project where the user already selected
Full access, preserve that existing selection rather than narrowing it silently.

Retain the native Windows sandbox configuration. For a device using the legacy
elevated implementation, its user config contains:

```toml
[windows]
sandbox = "elevated"
```

The desktop app manages the applicable Windows setup. On a new device, finish
its setup prompt if required. The sandboxed commands themselves run without
administrator privileges. See [Windows sandbox setup](https://learn.chatgpt.com/docs/windows/windows-sandbox).

## Maintainer acceptance runner

The runner now retains user configuration, so the chosen model, native Windows
sandbox setup and selected permissions remain available. It does not increase
the user's configured access. A --sandbox override is available when explicitly
needed. If PATH selects an older CLI, specify the verified
one without changing the user's global configuration:

```powershell
python tests/host_smoke.py codex --results test-results/hosts --executable $careerCodex
```

The runner now copies the complete public download into a new directory outside
the source repo and starts with no profile or installed project skills. This covers
the actual Download ZIP entry and avoids discovering an ancestor repo's skills.
The default parent is career-assistant-host-tests in the local temp directory;
--workspace-parent selects another trusted writable parent. Directories inherit
that parent's Windows permissions, avoiding owner-only mkdtemp ACLs. Logs remain
under the requested ignored results directory; fictional workspaces stay local.
Use --preinstall-skill only for a separate installed-skill check. It is not the
default first-use acceptance. No fixture seeds a real profile.
Optional MCP warnings do not count as host authentication failure when the model
and required local commands succeeded. Passing the runner still requires disk
assertions and transcript review; a successful response alone is insufficient.
