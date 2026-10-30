# Native first-use fallback when no Python 3.10+ or host runtime is available.
# No elevation, registry registration, PATH/profile edits or policy bypass.
param(
    [string]$Workspace = (Get-Location).Path,
    [string]$Python = '',
    [switch]$CheckOnly,
    [switch]$ManagedPython,
    [switch]$ResumeInstallation
)
$ErrorActionPreference = 'Stop'
$selected = $null
$workspaceRoot = [System.IO.Path]::GetFullPath($Workspace)
function Write-SetupJson([object]$Value) {
    $json = $Value | ConvertTo-Json -Compress
    $ascii = [System.Text.RegularExpressions.Regex]::Replace($json, '[^\x00-\x7F]', [System.Text.RegularExpressions.MatchEvaluator]{ param($match) '\u' + ([int][char]$match.Value).ToString('x4') })
    Write-Output $ascii
}
function Assert-LocalBootstrapPath([string]$RelativePath, [bool]$Directory = $false) {
    $prefix = $workspaceRoot.TrimEnd('\') + '\'
    $target = [System.IO.Path]::GetFullPath((Join-Path $workspaceRoot $RelativePath))
    if (-not $target.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw [System.IO.InvalidDataException]::new('Path escapes workspace') }
    $parts = $target.Substring($prefix.Length).Split('\')
    $current = $workspaceRoot
    for ($i = 0; $i -lt $parts.Length; $i++) {
        $current = Join-Path $current $parts[$i]
        try { $attributes = [System.IO.File]::GetAttributes($current) }
        catch [System.IO.FileNotFoundException] { break }
        catch [System.IO.DirectoryNotFoundException] { break }
        if (($attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw [System.IO.InvalidDataException]::new('Linked bootstrap path') }
        $isDirectory = ($attributes -band [System.IO.FileAttributes]::Directory) -ne 0
        if (($i -lt $parts.Length - 1 -or $Directory) -and -not $isDirectory) { throw [System.IO.InvalidDataException]::new('Invalid bootstrap directory') }
        if ($i -eq $parts.Length - 1 -and -not $Directory -and $isDirectory) { throw [System.IO.InvalidDataException]::new('Invalid bootstrap file') }
    }
}
try {
    Assert-LocalBootstrapPath '.career-assistant\setup\environment.json'
    Assert-LocalBootstrapPath '.career-assistant\setup\python-executable.txt'
    Assert-LocalBootstrapPath '.career-assistant\tools\uv\uv.exe'
    Assert-LocalBootstrapPath '.career-assistant\tools\python' $true
} catch [System.UnauthorizedAccessException] {
    Write-SetupJson @{status='approval_required';next_action='Allow inspection of the workspace setup path before continuing; no installation was attempted.'}
    exit 2
} catch {
    Write-SetupJson @{status='configuration_review_required';next_action='Review linked or invalid setup paths. No runtime, state or lock was written through them.'}
    exit 2
}
function Invoke-PrivateUv([string]$Executable, [string]$Arguments, [string]$InstallDir, [string]$CacheDir) {
    # Windows PowerShell 5 treats native stderr progress as an error record.
    # Read both streams directly and use the native exit code, without policy changes.
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $Executable
    $start.Arguments = $Arguments
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.StandardOutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $start.StandardErrorEncoding = New-Object System.Text.UTF8Encoding($false)
    $start.EnvironmentVariables['UV_PYTHON_INSTALL_DIR'] = $InstallDir
    $start.EnvironmentVariables['UV_CACHE_DIR'] = $CacheDir
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $start
    try {
        $null = $process.Start()
        $output = $process.StandardOutput.ReadToEndAsync()
        $errors = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(240000)) { $process.Kill(); throw 'Managed runtime operation timed out' }
        return @{ExitCode=$process.ExitCode;Output=$output.GetAwaiter().GetResult();Errors=$errors.GetAwaiter().GetResult()}
    } finally { $process.Dispose() }
}
function Probe-Python([string]$Executable, [string[]]$Prefix = @()) {
    if (-not $Executable) { return $null }
    try {
        # ASCII JSON survives GBK/UTF-8 pipe decoding in both Windows shells.
        $value = & $Executable @Prefix -c 'import json,sys; assert sys.version_info >= (3,10); print(json.dumps(sys.executable,ensure_ascii=True))' 2>$null
        if ($LASTEXITCODE -eq 0 -and $value) {
            $decoded = ([string]($value | Select-Object -Last 1)) | ConvertFrom-Json
            if ($decoded -is [string] -and [System.IO.Path]::IsPathRooted($decoded) -and [System.IO.File]::Exists($decoded)) {
                return [System.IO.Path]::GetFullPath($decoded)
            }
        }
    } catch {
        if ($_.CategoryInfo.Category -eq 'PermissionDenied' -or $_.Exception -is [System.UnauthorizedAccessException]) { return '__CAREER_PERMISSION_DENIED__' }
    }
    return $null
}
if (-not $ManagedPython) {
    if ($Python) { $selected = Probe-Python $Python }
    if (-not $selected) { $selected = Probe-Python (Join-Path $workspaceRoot '.venv\Scripts\python.exe') }
    $savedRuntime = Join-Path $workspaceRoot '.career-assistant\setup\python-executable.txt'
    if (-not $selected -and (Test-Path -LiteralPath $savedRuntime)) {
        $savedPython = [System.IO.File]::ReadAllText($savedRuntime).Trim()
        $managedRoot = Join-Path $workspaceRoot '.career-assistant\tools\python\'
        if ($savedPython.StartsWith($managedRoot, [System.StringComparison]::OrdinalIgnoreCase)) { $selected = Probe-Python $savedPython }
    }
    foreach ($name in @('python','python3')) {
        if ($selected) { break }
        foreach ($command in @(Get-Command $name -All -ErrorAction SilentlyContinue)) {
            if ($command.Source -and $command.Source -notmatch '\\WindowsApps\\') {
                $selected = Probe-Python $command.Source
                if ($selected) { break }
            }
        }
    }
    if (-not $selected) {
        $launcher = Get-Command py -ErrorAction SilentlyContinue
        if ($launcher) { $selected = Probe-Python $launcher.Source @('-3') }
    }
}
if ($selected) {
    if ($selected -eq '__CAREER_PERMISSION_DENIED__') {
        Write-SetupJson @{status='approval_required';next_action='Ask the user to allow the denied Python executable. Do not install another runtime to bypass a host denial.'}
        exit 2
    }
    Write-SetupJson @{status='available';python_executable=$selected;installed=$false}
    exit 0
}
if ($CheckOnly) {
    Write-SetupJson @{status='python_missing';next_action='Allow workspace-local runtime installation, then rerun this bootstrap.'}
    exit 2
}
$policyPath = Join-Path $workspaceRoot '.career-assistant\setup\environment.json'
if (Test-Path -LiteralPath $policyPath) {
    try { $policyText = [System.IO.File]::ReadAllText($policyPath) } catch {
        Write-SetupJson @{status='approval_required';next_action='Allow reading the saved installation choice before continuing. It was not reset.'}
        exit 2
    }
    try { $policy = $policyText | ConvertFrom-Json } catch {
        if (-not $ResumeInstallation) {
            Write-SetupJson @{status='configuration_review_required';next_action='Review the saved installation choice before downloading another runtime.'}
            exit 2
        }
        $policy = $null  # Explicit runtime-only authorization; the damaged state remains untouched.
    }
    if ($policy.installation_policy -eq 'deferred' -and -not $ResumeInstallation) {
        Write-SetupJson @{status='installation_deferred';next_action='The user deferred installation. Do not download or ask again; resume only after explicit user authorization.'}
        exit 2
    }
    if (-not $ResumeInstallation) {
        # ConvertFrom-Json cannot establish uniqueness of keys. Leave full consent
        # validation to the Python helper instead of guessing from an ambiguous file.
        Write-SetupJson @{status='configuration_review_required';next_action='Without a working Python the saved JSON cannot be fully validated. Preserve it and explicitly authorize runtime-only bootstrap before downloading; then review/recover its installation choice with the helper.'}
        exit 2
    }
}
try {
    $setupPath = Join-Path $workspaceRoot '.career-assistant\setup'
    $toolsPath = Join-Path $workspaceRoot '.career-assistant\tools'
    New-Item -ItemType Directory -Path $setupPath -Force | Out-Null
    New-Item -ItemType Directory -Path $toolsPath -Force | Out-Null
    $uvPath = Join-Path $toolsPath 'uv'
    $uvExe = Join-Path $uvPath 'uv.exe'
    if (-not (Test-Path -LiteralPath $uvExe)) {
        $machine = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
        $arch = if ($machine -eq 'Arm64') { 'aarch64' } else { 'x86_64' }
        $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/astral-sh/uv/releases/latest' -Headers @{'User-Agent'='Career-Assistant-Bootstrap'} -TimeoutSec 45
        $name = "uv-$arch-pc-windows-msvc.zip"
        $assets = @($release.assets | Where-Object { $_.name -eq $name })
        if ($assets.Count -ne 1 -or $assets[0].digest -notmatch '^sha256:[0-9a-f]{64}$') { throw 'Verified official uv asset unavailable' }
        $archivePath = Join-Path $setupPath 'uv-download.zip'
        Invoke-WebRequest -Uri $assets[0].browser_download_url -OutFile $archivePath -UseBasicParsing -TimeoutSec 180
        $hasher = [System.Security.Cryptography.SHA256]::Create()
        $hashInput = [System.IO.File]::OpenRead($archivePath)
        try { $actualHash = ([System.BitConverter]::ToString($hasher.ComputeHash($hashInput))).Replace('-','').ToLowerInvariant() }
        finally { $hashInput.Dispose(); $hasher.Dispose() }
        if ($actualHash -ne $assets[0].digest.Substring(7)) { throw 'Official uv asset hash mismatch' }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $archive = [System.IO.Compression.ZipFile]::OpenRead($archivePath)
        try {
            $entries = @($archive.Entries | Where-Object { $_.Name -eq 'uv.exe' })
            if ($entries.Count -ne 1) { throw 'Unexpected uv archive layout' }
            New-Item -ItemType Directory -Path $uvPath -Force | Out-Null
            $inputStream = $entries[0].Open()
            $outputStream = [System.IO.File]::Create($uvExe)
            try { $inputStream.CopyTo($outputStream) } finally { $outputStream.Dispose(); $inputStream.Dispose() }
        } finally { $archive.Dispose() }
    }
    $runtimePath = Join-Path $toolsPath 'python'
    $installed = Invoke-PrivateUv $uvExe 'python install 3.13 --no-bin --no-registry --no-config' $runtimePath (Join-Path $setupPath 'uv-cache')
    if ($installed.ExitCode -ne 0) { throw 'Managed Python download failed' }
    $found = Invoke-PrivateUv $uvExe 'python find 3.13 --managed-python --no-python-downloads --no-config' $runtimePath (Join-Path $setupPath 'uv-cache')
    if ($found.ExitCode -ne 0) { throw 'Managed Python lookup failed' }
    $selected = $found.Output.Trim()
    $selected = Probe-Python ([string]$selected).Trim()
    if (-not $selected) { throw 'Installed Python could not be verified' }
    $runtimePrefix = [System.IO.Path]::GetFullPath($runtimePath).TrimEnd('\') + '\'
    if (-not $selected.StartsWith($runtimePrefix, [System.StringComparison]::OrdinalIgnoreCase) -or -not [System.IO.File]::Exists($selected)) { throw 'Installed Python path is not a verified private runtime' }
    [System.IO.File]::WriteAllText((Join-Path $setupPath 'python-executable.txt'), $selected)
    Write-SetupJson @{status='installed';python_executable=$selected;installed=$true;scope='workspace only; no PATH, registry or host policy changes'}
} catch [System.UnauthorizedAccessException] {
    Write-SetupJson @{status='approval_required';next_action='Ask the user to allow this workspace runtime installation and command execution, then rerun the same bootstrap. No policy bypass.'}
    exit 2
} catch {
    Write-SetupJson @{status='installation_failed';reason=$_.Exception.GetType().Name;next_action='Check official download/network and workspace command permissions, then retry. Ask the user for an actual denied permission; do not disable TLS or execution policy. Error details omitted.'}
    exit 2
}
