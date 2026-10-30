#!/bin/sh
# Native first-use fallback. Uses existing Python first; no sudo or shell-profile edits.
set -eu
workspace=${1:-.}
provided=${2:-}
mode=${3:-}
workspace=$(cd "$workspace" && pwd -P)
for path in "$workspace/.career-assistant" "$workspace/.career-assistant/setup" "$workspace/.career-assistant/tools" "$workspace/.career-assistant/tools/uv" "$workspace/.career-assistant/tools/python"; do
    if [ -L "$path" ] || { [ -e "$path" ] && [ ! -d "$path" ]; }; then
        printf '%s\n' '{"status":"configuration_review_required","next_action":"Review linked or invalid setup directories before continuing. No runtime, state or lock was written through them."}'
        exit 2
    fi
done
for path in "$workspace/.career-assistant/setup/environment.json" "$workspace/.career-assistant/setup/python-executable.txt"; do
    if [ -L "$path" ] || { [ -e "$path" ] && [ ! -f "$path" ]; }; then
        printf '%s\n' '{"status":"configuration_review_required","next_action":"Review linked or non-file setup state before continuing. The original path was preserved."}'
        exit 2
    fi
done
selected=''
probe() {
    [ -n "$1" ] || return 1
    if result=$("$1" -c 'import sys; assert sys.version_info >= (3,10); print(sys.executable)' 2>/dev/null); then
        printf '%s' "$result"
    elif [ "$?" -eq 126 ]; then
        printf '%s' '__CAREER_PERMISSION_DENIED__'
    else
        return 1
    fi
}
if [ "$mode" != '--managed' ]; then
    if [ -n "$provided" ] && [ "$provided" != '--check-only' ]; then selected=$(probe "$provided" || true); fi
    if [ -z "$selected" ]; then selected=$(probe "$workspace/.venv/bin/python" || true); fi
    if [ -z "$selected" ] && [ -f "$workspace/.career-assistant/setup/python-executable.txt" ]; then
        prior=$(cat "$workspace/.career-assistant/setup/python-executable.txt")
        case "$prior" in
            "$workspace/.career-assistant/tools/python/"*) selected=$(probe "$prior" || true) ;;
        esac
    fi
    for candidate in python3 python; do
        if [ -z "$selected" ] && command -v "$candidate" >/dev/null 2>&1; then selected=$(probe "$candidate" || true); fi
    done
fi
if [ -n "$selected" ]; then
    if [ "$selected" = '__CAREER_PERMISSION_DENIED__' ]; then
        printf '%s\n' '{"status":"approval_required","next_action":"Ask the user to allow the denied runtime; do not install another executable to bypass the denial."}'
        exit 2
    fi
    "$selected" -c 'import json,sys; print(json.dumps({"status":"available","python_executable":sys.executable,"installed":False}))'
    exit 0
fi
if [ "$mode" = '--check-only' ] || [ "$provided" = '--check-only' ]; then
    printf '%s\n' '{"status":"python_missing","next_action":"Allow a workspace-local runtime install, then rerun bootstrap."}'
    exit 2
fi
policy="$workspace/.career-assistant/setup/environment.json"
if [ -f "$policy" ]; then
    if [ ! -r "$policy" ]; then
        printf '%s\n' '{"status":"approval_required","next_action":"Allow reading the saved installation choice before continuing; it was preserved."}'
        exit 2
    fi
fi
if [ -f "$policy" ] && [ "$mode" != '--resume-installation' ]; then
    if ! command -v grep >/dev/null 2>&1; then
        printf '%s\n' '{"status":"configuration_review_required","next_action":"Inspect the saved installation choice before downloading a runtime."}'
        exit 2
    fi
    if grep -Eq '"installation_policy"[[:space:]]*:[[:space:]]*"deferred"' "$policy"; then
        printf '%s\n' '{"status":"installation_deferred","next_action":"The user deferred installation; resume only after explicit user authorization."}'
        exit 2
    fi
    printf '%s\n' '{"status":"configuration_review_required","next_action":"Without a working Python the saved JSON cannot be fully validated. Review it and explicitly authorize resumption before any runtime download."}'
    exit 2
fi
setup="$workspace/.career-assistant/setup"
tools="$workspace/.career-assistant/tools"
if ! mkdir -p "$setup" "$tools"; then
    printf '%s\n' '{"status":"approval_required","next_action":"Ask the user to allow workspace writes, then resume the same bootstrap."}'
    exit 2
fi
uv="$tools/uv/uv"
if [ ! -x "$uv" ]; then
    if ! command -v curl >/dev/null 2>&1; then
        printf '%s\n' '{"status":"download_client_required","next_action":"The host must install or provide an approved HTTPS download client before downloading Python; ask for system-package permission if needed."}'
        exit 2
    fi
    if ! curl --proto '=https' --proto-redir '=https' --tlsv1.2 -fsSL --connect-timeout 15 --max-time 180 https://astral.sh/uv/install.sh -o "$setup/uv-install.sh"; then
        printf '%s\n' '{"status":"network_required","next_action":"Allow the official Astral runtime download if denied by the host, or retry when connected. Do not disable TLS."}'
        exit 2
    fi
    if ! env UV_UNMANAGED_INSTALL="$tools/uv" sh "$setup/uv-install.sh" >/dev/null 2>&1; then
        printf '%s\n' '{"status":"installation_failed","next_action":"Check workspace execution/network permissions; request an actual required permission and retry without sudo or policy changes."}'
        exit 2
    fi
fi
if ! "$uv" python install 3.13 --install-dir "$tools/python" --no-bin --no-config --cache-dir "$setup/uv-cache" >/dev/null 2>&1; then
    printf '%s\n' '{"status":"installation_failed","next_action":"Check the managed Python download and workspace permissions, then retry the same step."}'
    exit 2
fi
selected=$(UV_PYTHON_INSTALL_DIR="$tools/python" "$uv" python find 3.13 --managed-python --no-python-downloads --no-config 2>/dev/null || true)
if [ -z "$selected" ] || ! probe "$selected" >/dev/null; then
    printf '%s\n' '{"status":"verification_failed","next_action":"Installed Python did not verify; keep onboarding uninitialized until a working runtime is available."}'
    exit 2
fi
printf '%s' "$selected" > "$setup/python-executable.txt"
"$selected" -c 'import json,sys; print(json.dumps({"status":"installed","python_executable":sys.executable,"installed":True,"scope":"workspace only; no PATH/profile changes"}))'
