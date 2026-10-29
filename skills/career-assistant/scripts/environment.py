"""Workspace dependency setup. No profile facts, credentials or global settings."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import uuid
try:
    import tomllib as _toml
except ImportError:
    try:
        import tomli as _toml
    except ImportError:
        _toml = None
try:
    import venv
except ImportError:
    venv = None
from zipfile import ZipFile
from storage import atomic, atomic_bytes, atomic_text, inside, now

PACKAGES = {'pypdf': 'pypdf>=5,<7', 'fitz': 'PyMuPDF>=1.25,<2'}
TRUSTED = {'api.github.com', 'github.com', 'release-assets.githubusercontent.com',
           'objects.githubusercontent.com', 'nodejs.org', 'pypi.org', 'files.pythonhosted.org'}
PROBE = "import importlib,json,sys,io,contextlib; r={};\nfor n in ['pypdf','fitz']:\n try:\n  with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()): importlib.import_module('pymupdf' if n=='fitz' else n)\n  r[n]=True\n except (ImportError,OSError): r[n]=False\ntry:\n with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()): importlib.import_module('tomllib' if sys.version_info >= (3,11) else 'tomli')\n parser=True\nexcept (ImportError,OSError): parser=False\nprint(json.dumps({'packages':r,'version':list(sys.version_info[:3]),'python':sys.executable,'toml_parser':parser}))"


class SetupError(Exception):
    def __init__(self, status, reason, action, command=None):
        super().__init__(reason)
        self.result = {'status': status, 'reason': reason, 'next_action': action}
        if command:
            self.result['command'] = list(map(str, command))


def root(workspace):
    return Path(workspace).resolve() / '.career-assistant'


def settings(workspace):
    path = root(workspace) / 'setup/environment.json'
    try:
        if not path.exists():
            return {}
        if not path.is_file() or path.is_symlink() or inside(root(workspace), path) != path.absolute():
            raise ValueError('Non-regular setup state')
        if path.stat().st_size > 2_000_000:
            raise ValueError('Oversized setup state')
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if (not isinstance(value, dict) or value.get('schema_version') != 1
                or value.get('kind', 'dependency_setup') != 'dependency_setup'
                or value.get('installation_policy') not in ('auto', 'deferred')
                or not isinstance(value.get('steps'), dict)
                or any(not isinstance(step, dict) or ('status' in step and not isinstance(step['status'], str))
                       for step in value['steps'].values())):
            raise ValueError('Invalid setup state structure/version')
        return value
    except PermissionError:
        raise SetupError('approval_required', 'Saved installation choices cannot be read',
                         'Allow reading this setup state before continuing. It was not replaced and no installation is authorized by this failure.') from None
    except (ValueError, OSError):
        raise SetupError('configuration_review_required', 'Saved installation state is damaged, unsupported or unreadable',
                         'Preserve the existing file; no downloads are allowed. Ask the user to choose continued deferral or resumed installation, then use recover-setup with that choice and their actual confirmation. The original will be backed up before recovery.') from None


def local_python(workspace):
    base = Path(workspace).resolve()
    for folder in [base / '.venv', root(base) / 'tools/pdf-venv']:
        yield folder / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def configured_python(workspace):
    chosen = settings(workspace).get('steps', {}).get('python_packages', {}).get('python_executable')
    for candidate in local_python(workspace):
        if chosen == str(candidate) and candidate.is_file():
            return candidate
    return None


def tool_path(workspace, name):
    suffix = '.exe' if os.name == 'nt' else ''
    private = root(workspace) / f'tools/{name}/{name}{suffix}'
    return str(private) if private.is_file() else shutil.which(name)


def tool_env(workspace):
    env = dict(os.environ)
    cache = settings(workspace).get('steps', {}).get('tex_cache', {})
    if cache.get('cache_scope') == 'workspace':
        env['TECTONIC_CACHE_DIR'] = str(root(workspace) / 'tools/tex-cache')
    return env


def compiler_download_flags(workspace):
    return ['--only-cached'] if settings(workspace).get('installation_policy') == 'deferred' else []


def _command(args, env=None, timeout=300, input_text=None):
    try:
        result = subprocess.run(list(map(str, args)), cwd=None, env=env, capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=timeout,
                                **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}),
                                **({'input': input_text} if input_text is not None else {}))
    except PermissionError:
        raise SetupError('approval_required', 'Command execution or target access was denied',
                         'Ask the user to allow this dependency installation in the selected workspace, then retry the same step.', args) from None
    except subprocess.TimeoutExpired:
        raise SetupError('retryable_error', 'Dependency operation timed out',
                         'Check network/tool access and retry; completed steps are retained.', args) from None
    if result.returncode:
        output = result.stdout + result.stderr
        if re.search(r'permission denied|PermissionError|access is denied|operation not permitted|blocked by policy|EACCES|EPERM|WinError\s*5|拒绝访问|权限不足|访问被拒绝', output, re.I):
            status, action = 'approval_required', 'Ask the user to permit this exact installation or workspace path. Do not change host policy or retry through another tool.'
        elif re.search(r'shared librar|lib[a-z0-9_-]+\.so|host system is missing dependencies', output, re.I):
            status, action = 'system_dependencies_required', 'The browser needs OS libraries. If current host/OS permissions already allow system-package installation, run the prepared system dependency command. Otherwise ask for that specific permission. Never invoke sudo or change policy to gain access.'
        else:
            status, action = 'retryable_error', 'Check supported versions and network access, then retry this step. Logs and environment secrets are omitted.'
        raise SetupError(status, f'Dependency command exited {result.returncode}; output omitted', action, args)
    return result


def probe_python(executable):
    try:
        result = _command([executable, '-c', PROBE], timeout=20)
        data = json.loads(result.stdout)
        return data if tuple(data['version']) >= (3, 10) else None
    except SetupError as exc:
        if exc.result['status'] == 'approval_required':
            raise
        return None
    except (ValueError, KeyError, OSError):
        return None


def _fetch(url, max_bytes=300_000_000):
    from urllib.parse import urlsplit
    if urlsplit(url).scheme != 'https' or urlsplit(url).hostname not in TRUSTED:
        raise SetupError('verification_failed', 'Unapproved dependency download origin',
                         'Use the documented official vendor or package registry; never disable TLS verification.')
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'Career-Assistant-Setup',
                                                       'Accept': 'application/vnd.github+json' if 'api.github.com' in url else '*/*'})
        with urllib.request.urlopen(request, timeout=45) as response:
            final = urlsplit(response.geturl())
            if final.scheme != 'https' or final.hostname not in TRUSTED:
                raise SetupError('verification_failed', 'Unapproved dependency redirect', 'Inspect the official release; no executable was installed.')
            pieces, size = [], 0
            while True:
                block = response.read(1_048_576)
                if not block:
                    break
                size += len(block)
                if size > max_bytes:
                    raise SetupError('verification_failed', 'Dependency download exceeds size limit', 'Inspect the official asset before retrying.')
                pieces.append(block)
            return b''.join(pieces)
    except urllib.error.URLError:
        raise SetupError('network_required', 'Official dependency download was unavailable',
                         'If the host denied network access, ask the user to allow this official download. Otherwise retry when the network is available; do not disable TLS or use an unverified mirror.') from None


def _unpack(archive, destination, strip_root=False):
    """Extract only regular files/directories, never archive links or special files."""
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    def write(name, data, executable=False):
        nonlocal total
        parts = PurePosixPath(name.replace('\\', '/')).parts
        if any(p in {'..', '.'} or ':' in p for p in parts) or name.startswith(('/', '\\')):
            raise SetupError('verification_failed', 'Unsafe archive member', 'Do not execute this asset.')
        if strip_root:
            parts = parts[1:]
        if not parts:
            return
        target = inside(destination, destination.joinpath(*parts))
        total += len(data)
        if total > 600_000_000:
            raise SetupError('verification_failed', 'Expanded dependency exceeds size limit', 'Inspect the official asset.')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if executable and os.name != 'nt':
            target.chmod(0o755)
    if str(archive).endswith('.zip'):
        with ZipFile(archive) as source:
            for info in source.infolist():
                if not info.is_dir():
                    if (info.external_attr >> 16) & 0o170000 == 0o120000:
                        continue
                    if info.file_size > 300_000_000 or total + info.file_size > 600_000_000:
                        raise SetupError('verification_failed', 'Archive member exceeds size limit', 'Inspect the official asset.')
                    write(info.filename, source.read(info), bool(info.external_attr >> 16 & 0o111))
    else:
        with tarfile.open(archive, 'r:gz') as source:
            for info in source:
                if info.isfile():
                    stream = source.extractfile(info)
                    if info.size > 300_000_000:
                        raise SetupError('verification_failed', 'Archive member exceeds size limit', 'Inspect the official asset.')
                    write(info.name, stream.read(), bool(info.mode & 0o111))


def _install_tectonic(workspace, downloads=True):
    existing = tool_path(workspace, 'tectonic')
    if existing:
        try:
            _command([existing, '--version'], timeout=20)
            return {'status': 'available', 'executable': existing}
        except SetupError as exc:
            if exc.result['status'] == 'approval_required':
                raise
        except OSError:
            pass
    if not downloads:
        raise SetupError('download_required', 'Tectonic is missing', 'Rerun setup with network/installation permission to install the official local binary.')
    machine = platform.machine().lower()
    arch = {'amd64': 'x86_64', 'x86_64': 'x86_64', 'arm64': 'aarch64', 'aarch64': 'aarch64'}.get(machine)
    system = platform.system()
    target = {('Windows', 'x86_64'): 'x86_64-pc-windows-msvc.zip',
              ('Darwin', 'x86_64'): 'x86_64-apple-darwin.tar.gz',
              ('Darwin', 'aarch64'): 'aarch64-apple-darwin.tar.gz',
              ('Linux', 'x86_64'): 'x86_64-unknown-linux-musl.tar.gz',
              ('Linux', 'aarch64'): 'aarch64-unknown-linux-musl.tar.gz'}.get((system, arch))
    if not target:
        raise SetupError('unsupported', 'No supported Tectonic binary for this OS/architecture',
                         'Use the official Tectonic installation guide for this platform; profile setup can continue.')
    release = json.loads(_fetch('https://api.github.com/repos/tectonic-typesetting/tectonic/releases/latest', 10_000_000))
    assets = [a for a in release['assets'] if a['name'].endswith('-' + target)]
    if len(assets) != 1 or not re.fullmatch(r'sha256:[0-9a-f]{64}', assets[0].get('digest') or ''):
        raise SetupError('verification_failed', 'Official asset or SHA-256 is unavailable', 'Inspect the official release; do not execute an unverified download.')
    asset = assets[0]
    data = _fetch(asset['browser_download_url'])
    if hashlib.sha256(data).hexdigest() != asset['digest'][7:]:
        raise SetupError('verification_failed', 'Tectonic SHA-256 mismatch', 'Preserve the failure and retry only from the official verified release.')
    directory = root(workspace) / 'tools'
    directory.mkdir(parents=True, exist_ok=True)
    staged = directory / ('tectonic-stage-' + uuid.uuid4().hex[:10])
    staged.mkdir()
    archive = staged / asset['name']
    archive.write_bytes(data)
    extracted = staged / 'unpacked'
    _unpack(archive, extracted)
    filename = 'tectonic.exe' if os.name == 'nt' else 'tectonic'
    executables = list(extracted.rglob(filename))
    if len(executables) != 1:
        raise SetupError('verification_failed', 'Official archive has an unexpected layout', 'Inspect the release layout before retrying.')
    _command([executables[0], '--version'], timeout=20)
    dest = directory / 'tectonic'
    if dest.exists():
        raise SetupError('path_conflict', 'Local Tectonic directory already exists but is unusable', 'Review this interrupted installation; do not overwrite an unrelated directory.')
    executables[0].parent.rename(dest)
    return {'status': 'installed', 'executable': str(dest / filename), 'version': release['tag_name'], 'sha256': asset['digest'][7:]}


def _runtime_required(workspace):
    scripts = Path(__file__).resolve().parent
    command = [shutil.which('pwsh') or shutil.which('powershell') or 'powershell', '-NoProfile', '-File', str(scripts/'bootstrap-python.ps1'), '-Workspace', str(Path(workspace).resolve()), '-ManagedPython'] if os.name == 'nt' else ['sh', str(scripts/'bootstrap-python.sh'), str(Path(workspace).resolve()), '', '--managed']
    return SetupError('runtime_required', 'This Python lacks a working venv/ensurepip component',
                      'Reuse a complete host runtime, or automatically run this native managed-runtime bootstrap when permitted, then rerun setup with its returned Python. Ask only for an actual denied permission; do not modify system Python.', command)


def _install_packages(workspace, downloads=True):
    current = probe_python(sys.executable)
    chosen = next((p for p in local_python(workspace) if p.is_file() and probe_python(p)), None)
    parser_ready = lambda info: info.get('toml_parser', tuple(info.get('version', [])) >= (3, 11))
    if chosen is None and current and all(current['packages'].values()) and parser_ready(current):
        return {'status': 'available', 'python_executable': sys.executable, 'packages': current['packages'], 'toml_parser': True}
    if chosen is None:
        chosen = next(local_python(workspace))
        folder = chosen.parent.parent
        if folder.exists() and any(folder.iterdir()):
            chosen = list(local_python(workspace))[1]
            folder = chosen.parent.parent
        if not downloads:
            raise SetupError('download_required', 'PDF Python dependencies are missing', 'Allow local dependency setup; text/DOCX profile work remains usable.')
        if folder.exists() and any(folder.iterdir()):
            raise SetupError('path_conflict', 'Existing PDF virtual environment is unusable', 'Review the selected environment; no existing files were reset.')
        if venv is None:
            raise _runtime_required(workspace)
        try:
            venv.EnvBuilder(with_pip=True).create(folder)
        except (subprocess.CalledProcessError, ImportError) as exc:
            detail = str(getattr(exc, 'output', ''))
            if re.search(r'PermissionError|permission denied|WinError\s*5|EACCES|EPERM', detail, re.I):
                raise SetupError('approval_required', 'Virtual environment creation was denied', 'Ask for permission at this workspace path; do not switch runtimes to bypass the denial.') from None
            raise _runtime_required(workspace) from None
    info = probe_python(chosen)
    if info is None:
        raise SetupError('runtime_required', 'Selected Python environment cannot run', 'Select a working Python 3.10+ or rerun the native Python bootstrap.')
    missing = [PACKAGES[name] for name, present in info['packages'].items() if not present]
    if not parser_ready(info):
        missing.append('tomli>=2,<3')
    if missing:
        if not downloads:
            raise SetupError('download_required', 'PDF Python dependencies are missing', 'Allow downloads and retry setup.')
        try:
            _command([chosen, '-m', 'pip', '--version'], timeout=30)
        except SetupError as exc:
            if exc.result['status'] == 'approval_required':
                raise
            try:
                _command([chosen, '-m', 'ensurepip', '--upgrade'], timeout=120)
            except SetupError as repair:
                if repair.result['status'] == 'approval_required':
                    raise
                raise _runtime_required(workspace) from None
        _command([chosen, '-m', 'pip', 'install', '--isolated', '--disable-pip-version-check',
                  '--index-url', 'https://pypi.org/simple', '--cache-dir', root(workspace)/'setup/pip-cache', '--only-binary=:all:', *missing], timeout=600)
    verified = probe_python(chosen)
    if not verified or not all(verified['packages'].values()) or not parser_ready(verified):
        raise SetupError('verification_failed', 'Installed PDF packages failed import', 'Inspect the local interpreter and compatible official wheels; keep PDF output draft.')
    return {'status': 'installed' if missing else 'available', 'python_executable': str(chosen), 'packages': verified['packages'], 'toml_parser': True}


def _warm_tex(workspace, compiler, downloads=True, save=None):
    template = Path(__file__).resolve().parent.parent / 'assets/resume-template.tex'
    text = template.read_text(encoding='utf-8')
    values = {'HEADER': r'\begin{center}Career Assistant Environment Check\end{center}',
              'SUMMARY': 'Non-personal dependency probe.', 'SKILLS': 'Template resources and fonts.',
              'EXPERIENCE': 'Environment check only.', 'PROJECTS': '', 'EDUCATION': 'No personal career facts.'}
    for key, value in values.items():
        text = text.replace('@@' + key + '@@', value)
    directory = root(workspace) / 'setup' / ('tex-probe-' + uuid.uuid4().hex[:10])
    directory.mkdir(parents=True)
    source = directory / 'probe.tex'; source.write_text(text, encoding='utf-8')
    env = tool_env(workspace)
    try:
        _command([compiler, '--only-cached', '--outdir', directory, source], env=env, timeout=90)
        if (directory / 'probe.pdf').is_file():
            return {'status': 'available', 'cache_scope': 'workspace' if 'TECTONIC_CACHE_DIR' in env and env['TECTONIC_CACHE_DIR'] == str(root(workspace)/'tools/tex-cache') else 'existing',
                    'template_sha256': hashlib.sha256(template.read_bytes()).hexdigest(), 'scope': 'Canonical template resources only; a personal resume still needs PDF/text/visual QA.'}
    except SetupError as exc:
        if exc.result['status'] == 'approval_required':
            raise
    if not downloads:
        raise SetupError('download_required', 'Canonical TeX resources are not cached', 'Permit the first template compilation/download; profile work can continue.')
    env['TECTONIC_CACHE_DIR'] = str(root(workspace) / 'tools/tex-cache')
    # Persist the cache choice before compilation, including on interruption/failure.
    if save:
        save({'status': 'installing', 'cache_scope': 'workspace'})
    _command([compiler, '--outdir', directory, source], env=env, timeout=600)
    if not (directory / 'probe.pdf').is_file():
        raise SetupError('verification_failed', 'Template compilation produced no PDF', 'Keep resume output draft and inspect Tectonic setup.')
    return {'status': 'installed', 'cache_scope': 'workspace', 'template_sha256': hashlib.sha256(template.read_bytes()).hexdigest(),
            'scope': 'Canonical template resources only; no user resume was generated.'}


def _node(workspace, downloads):
    private = root(workspace)/'tools/node'
    node = private/('node.exe' if os.name == 'nt' else 'bin/node')
    candidates = [node] if node.is_file() else []
    found = shutil.which('node')
    if found:
        candidates.append(Path(found).resolve())
    for candidate in candidates:
        try:
            version = _command([candidate, '--version'], timeout=20).stdout.strip()
            if int(version.lstrip('v').split('.')[0]) < 18:
                continue
            npm = shutil.which('npm')
            paths = [candidate.parent/'node_modules/npm/bin/npm-cli.js',
                     candidate.parent.parent/'lib/node_modules/npm/bin/npm-cli.js']
            if npm and Path(npm).resolve().name == 'npm-cli.js':
                paths.insert(0, Path(npm).resolve())
            cli = next((p for p in paths if p.is_file()), None)
            if cli:
                return str(candidate), str(cli)
        except SetupError as exc:
            if exc.result['status'] == 'approval_required':
                raise
        except ValueError:
            pass
    if not downloads:
        raise SetupError('download_required', 'Node.js/npm is missing for the browser fallback', 'Permit the official local Node.js LTS download.')
    machine = {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(platform.machine().lower())
    system = {'Windows': 'win', 'Darwin': 'darwin', 'Linux': 'linux'}.get(platform.system())
    if not machine or not system:
        raise SetupError('unsupported', 'Node.js platform unsupported', 'Use a supported host browser or an official supported Node distribution.')
    releases = json.loads(_fetch('https://nodejs.org/dist/index.json', 20_000_000))
    release = next(r for r in releases if r.get('lts'))
    version = release['version']; suffix = '.zip' if system == 'win' else '.tar.gz'
    name = f'node-{version}-{system}-{machine}{suffix}'
    prefix = f'https://nodejs.org/dist/{version}/'
    checksums = _fetch(prefix+'SHASUMS256.txt', 2_000_000).decode('utf-8')
    expected = next((line.split()[0] for line in checksums.splitlines() if len(line.split()) == 2 and line.split()[-1] == name), None)
    data = _fetch(prefix+name)
    if not expected or hashlib.sha256(data).hexdigest() != expected:
        raise SetupError('verification_failed', 'Official Node archive SHA-256 mismatch', 'Do not execute the download; inspect the official release.')
    tools = root(workspace)/'tools'; tools.mkdir(parents=True, exist_ok=True)
    staged = tools/('node-stage-'+uuid.uuid4().hex[:10]); staged.mkdir()
    archive = staged/name; archive.write_bytes(data)
    _unpack(archive, staged/'unpacked', strip_root=True)
    if private.exists():
        raise SetupError('path_conflict', 'Local Node directory already exists but is unusable', 'Review the interrupted install; do not overwrite existing tools.')
    (staged/'unpacked').rename(private)
    node = private/('node.exe' if os.name == 'nt' else 'bin/node')
    cli = private/('node_modules/npm/bin/npm-cli.js' if os.name == 'nt' else 'lib/node_modules/npm/bin/npm-cli.js')
    _command([node, '--version'], timeout=20)
    return str(node), str(cli)


def _toml_info(text, server, parser):
    if parser is None:
        return {'parser_missing': True}
    try:
        data = parser.loads(text)
        servers = data.get('mcp_servers', {})
        if not isinstance(servers, dict):
            return {'valid': False}
        current = servers.get('career_browser')
        exists = 'career_browser' in servers
        same = (isinstance(current, dict) and not (set(current) - {'command', 'args', 'env'})
                and current.get('command') == server['command']
                and current.get('args', []) == server['args']
                and current.get('env', {}) == server['env'])
        return {'valid': True, 'exists': exists, 'same': same}
    except (ValueError, TypeError):
        return {'valid': False}


_TOML_WORKER = "import json,sys;sys.path.insert(0,sys.argv[1]);from environment import _toml_info,_toml;p=json.load(sys.stdin);print(json.dumps(_toml_info(p['text'],p['server'],_toml)))"


def _inspect_toml(workspace, text, server):
    if len(text.encode('utf-8')) > 2_000_000:
        raise SetupError('configuration_review_required', 'Project TOML exceeds the setup size limit', 'Review this existing configuration; it was preserved.')
    if _toml is not None:
        result = _toml_info(text, server, _toml)
    else:
        selected = configured_python(workspace)
        if selected is None:
            raise SetupError('parser_required', 'A TOML parser is needed before modifying project config',
                             'Run setup with Python 3.11+ or install the conditional tomli dependency in the workspace runtime. Existing config was preserved.')
        parsed = _command([selected, '-c', _TOML_WORKER, Path(__file__).resolve().parent],
                          input_text=json.dumps({'text': text, 'server': server}), timeout=30)
        result = json.loads(parsed.stdout)
    if result.get('parser_missing'):
        raise SetupError('parser_required', 'The selected runtime has no TOML parser', 'Resume dependency setup; no configuration was changed.')
    if not result.get('valid'):
        raise SetupError('configuration_review_required', 'Project TOML is invalid or cannot accept the proposed server table',
                         'Review the project config before adding a browser. The original file was preserved; no config contents are logged.')
    return result


def _register_browser(workspace, host, server):
    base = Path(workspace).resolve()
    if (not isinstance(server.get('command'), str) or not server['command']
            or not isinstance(server.get('args'), list) or any(not isinstance(x, str) for x in server['args'])
            or not isinstance(server.get('env'), dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in server['env'].items())):
        raise ValueError('Browser registration needs a command, string arguments and string environment values')
    plans = []
    def read(path):
        if not path.exists():
            return None, ''
        if not path.is_file() or path.is_symlink() or path.resolve() != path.absolute() or path.stat().st_size > 2_000_000:
            raise SetupError('configuration_review_required', 'Project host config is not a supported regular file', 'Review the original file; it was preserved.')
        raw = path.read_bytes()
        try:
            return raw, raw.decode('utf-8-sig')
        except UnicodeError:
            raise SetupError('configuration_review_required', 'Project host config is not valid UTF-8', 'Review its encoding before changing it; the original was preserved.') from None
    if host in {'codex', 'both'}:
        path = base/'.codex/config.toml'
        original, existing = read(path)
        info = _inspect_toml(workspace, existing, server)
        if info['exists']:
            if not info['same']:
                raise SetupError('configuration_review_required', 'Existing career_browser config differs', 'Review this project-only server; all original settings were preserved.')
        else:
            block = '[mcp_servers.career_browser]\ncommand = '+json.dumps(server['command'], ensure_ascii=False)+'\nargs = '+json.dumps(server['args'], ensure_ascii=False)+'\n'
            block += '[mcp_servers.career_browser.env]\n'+'\n'.join(json.dumps(key, ensure_ascii=False)+' = '+json.dumps(value, ensure_ascii=False) for key,value in server['env'].items())+'\n'
            candidate = existing.rstrip()+'\n\n'+block
            verified = _inspect_toml(workspace, candidate, server)
            if not verified['exists'] or not verified['same']:
                raise SetupError('configuration_review_required', 'Candidate browser config did not validate', 'No host configuration was changed.')
            plans.append((path, original, candidate.encode('utf-8')))
    if host in {'claude', 'both'}:
        path = base/'.mcp.json'
        original, existing = read(path)
        try:
            data = json.loads(existing) if existing else {}
        except ValueError:
            raise SetupError('configuration_review_required', 'Existing project MCP JSON is invalid', 'Review the original; no host configuration was changed.') from None
        if not isinstance(data, dict) or not isinstance(data.get('mcpServers', {}), dict):
            raise SetupError('configuration_review_required', 'Existing project MCP JSON has an invalid structure', 'Review the existing config; all original server entries were preserved.')
        servers = data.setdefault('mcpServers', {})
        if 'career_browser' in servers:
            if servers['career_browser'] != server:
                raise SetupError('configuration_review_required', 'Existing career_browser config differs', 'Review the existing project server before changing it; it was preserved.')
        else:
            servers['career_browser'] = server
            plans.append((path, original, json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')+b'\n'))
    # Preflight every requested host before any write; preserve concurrent edits.
    for path, original, proposed in plans:
        if path.resolve() != path.absolute():
            raise SetupError('configuration_review_required', 'Project host config path changed or escapes the workspace', 'It was not written; preserve linked/global host settings.')
        current = path.read_bytes() if path.exists() else None
        if current != original:
            raise SetupError('configuration_review_required', 'Project host config changed during registration', 'Inspect the current file and retry; it was not overwritten.')
    ignore = base/'.gitignore'
    old = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
    missing = [rule for rule in ['/.codex/', '/.mcp.json'] if rule not in old.splitlines()]
    if missing:
        atomic_text(ignore, old.rstrip()+'\n'+'\n'.join(missing)+'\n')
    for path, original, proposed in plans:
        atomic_bytes(path, proposed)


def _install_browser(workspace, host, downloads):
    node, npm = _node(workspace, downloads)
    directory = root(workspace)/'tools/browser'
    module = directory/'node_modules/@playwright/mcp'
    if not (module/'package.json').is_file():
        if not downloads:
            raise SetupError('download_required', 'Microsoft Playwright MCP is missing', 'Allow the official npm package installation in this workspace.')
        _command([node, npm, 'install', '--prefix', directory, '--ignore-scripts', '--no-audit', '--no-fund',
                  '--cache', root(workspace)/'setup/npm-cache', '--registry=https://registry.npmjs.org', '@playwright/mcp@latest'], timeout=600)
    env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(root(workspace)/'browser/engines'))
    library = next((directory/'node_modules'/name for name in ['playwright', 'playwright-core']
                    if (directory/'node_modules'/name/'cli.js').is_file()), None)
    if library is None:
        raise SetupError('verification_failed', 'Playwright package layout is unavailable', 'Inspect the official package before configuring the host.')
    probe = "const {chromium}=require(process.argv[1]); (async()=>{const b=await chromium.launch({headless:true});console.log(JSON.stringify({executable:chromium.executablePath()}));await b.close();})().catch(e=>{console.error(e.message);process.exit(1);});"
    def verify_browser():
        try:
            return _command([node, '-e', probe, library], env=env, timeout=90)
        except SetupError as exc:
            if exc.result['status'] == 'system_dependencies_required':
                exc.result['system_dependency_command'] = [node, str(library/'cli.js'), 'install-deps', 'chromium']
            raise
    try:
        result = verify_browser()
    except SetupError as exc:
        if exc.result['status'] in {'approval_required','system_dependencies_required'} or not downloads:
            raise
        _command([node, library/'cli.js', 'install', 'chromium'], env=env, timeout=600)
        result = verify_browser()
    executable = json.loads(result.stdout)['executable']
    package = json.loads((module/'package.json').read_text(encoding='utf-8'))
    binary = package['bin']; binary = binary if isinstance(binary,str) else next(iter(binary.values()))
    server = {'command': node, 'args': [str(module/binary), '--executable-path', executable,
                                        '--user-data-dir', str(root(workspace)/'browser/profile')],
              'env': {'PLAYWRIGHT_BROWSERS_PATH': env['PLAYWRIGHT_BROWSERS_PATH']}}
    _register_browser(workspace, host, server)
    return {'status': 'host_reload_required', 'installed': True, 'project_configured': True,
            'next_action': 'Reload the host/project and inspect the real browser API. Approve the project/tool prompt if required; login is a separate user action. Search can use this browser after connection.'}


def _state_failure(workspace, error):
    return {**error.result, 'state_saved': False, 'state_path': str(root(workspace)/'setup/environment.json')}


def recover_setup(workspace, choice, confirmation):
    """Explicitly reviewed recovery of operational state; never installs software."""
    if choice not in {'defer', 'resume'} or not isinstance(confirmation, str) or not confirmation.strip():
        raise ValueError('Recovery needs defer/resume and the actual user confirmation')
    workspace = Path(workspace).resolve()
    path = root(workspace)/'setup/environment.json'
    try:
        try:
            current = settings(workspace)
        except SetupError as exc:
            if exc.result['status'] != 'configuration_review_required':
                return _state_failure(workspace, exc)
        else:
            return {'status': 'not_required', 'state_saved': False,
                    'next_action': 'The saved state is valid or absent. Use normal setup --defer-installation/--resume-installation; no state was reset.'}
        lock = path.parent/'.install.lock'
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return {'status': 'setup_in_progress', 'state_saved': False,
                    'next_action': 'Inspect the active installer before recovering its state. Do not steal the lock.'}
        try:
            os.write(fd, str(os.getpid()).encode()); os.close(fd)
            if not path.is_file() or path.is_symlink() or inside(root(workspace), path) != path.absolute() or path.stat().st_size > 2_000_000:
                raise SetupError('configuration_review_required', 'State recovery requires a bounded regular local file',
                                 'Preserve the original and review its path/size; it was not replaced.')
            original = path.read_bytes()
            key = hashlib.sha256(original).hexdigest()
            backup = path.parent/'state-backups'/('environment-'+uuid.uuid4().hex+'.bin')
            atomic_bytes(backup, original)
            if hashlib.sha256(backup.read_bytes()).hexdigest() != key:
                raise SetupError('verification_failed', 'Setup state backup did not verify', 'The original state was not replaced.')
            # Recheck after the backup rather than overwrite an external edit.
            if path.read_bytes() != original:
                raise SetupError('configuration_review_required', 'Setup state changed during recovery', 'Inspect the current state and retry; it was preserved.')
            restored = {'schema_version': 1, 'kind': 'dependency_setup', 'workspace': str(workspace),
                        'installation_policy': 'deferred' if choice == 'defer' else 'auto',
                        'steps': {}, 'status': 'recovered', 'updated_at': now(),
                        'recovered_from': str(backup.relative_to(root(workspace))), 'original_sha256': key,
                        'confirmation_sha256': hashlib.sha256(confirmation.encode('utf-8')).hexdigest()}
            atomic(path, restored)
            settings(workspace)
            return {'status': 'recovered', 'state_saved': True, 'installation_policy': restored['installation_policy'],
                    'backup_path': str(backup), 'original_sha256': key, 'installed_software': False,
                    'next_action': 'Resume setup with the reviewed choice. Existing tools, career facts and application history were not reset.'}
        finally:
            lock.unlink(missing_ok=True)
    except PermissionError:
        return _state_failure(workspace, SetupError('approval_required', 'Setup state recovery was denied',
                             'Allow reading/backing up/replacing this operational file before retrying. No permission is inferred from the failure.'))
    except SetupError as exc:
        return _state_failure(workspace, exc)


def setup(workspace, host='codex', browser='inspect', search='inspect', downloads=True, defer=False, resume=False):
    workspace = Path(workspace).resolve()
    if defer and resume:
        raise ValueError('Choose deferral or resumption, not both')
    state_path = root(workspace)/'setup/environment.json'
    try:
        # Invalid/unreadable existing state is not equivalent to a first run.
        settings(workspace)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        lock = state_path.parent/'.install.lock'
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return {'status':'setup_in_progress', 'state_saved':False, 'next_action':'An installer or interrupted run holds setup/.install.lock. Check the writer before removing a stale lock; do not start another installer.'}
        try:
            os.write(fd, str(os.getpid()).encode()); os.close(fd)
            # Re-read under the lock so a just-saved user choice cannot be lost.
            state = settings(workspace)
            if defer:
                state['installation_policy'] = 'deferred'
            elif resume:
                state['installation_policy'] = 'auto'
            state.setdefault('installation_policy', 'auto')
            if state['installation_policy'] == 'deferred':
                downloads = False
                if browser == 'missing':
                    browser = 'defer'
            state.update(schema_version=1, kind='dependency_setup', workspace=str(workspace), updated_at=now(), status='checking')
            state.setdefault('steps', {})
            state['state_path'] = str(state_path)
            def save(name, value):
                previous = state['steps'].get(name, {})
                state['steps'][name] = {**({'cache_scope': previous['cache_scope']} if 'cache_scope' in previous else {}), **value}
                state['updated_at'] = now()
                atomic(state_path, state)
            ignore = workspace/'.gitignore'
            existing = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
            missing = [rule for rule in ['/.career-assistant/', '/.venv/'] if rule not in existing.splitlines()]
            if missing:
                atomic_text(ignore, existing.rstrip()+'\n'+'\n'.join(missing)+'\n')
            def step(name, function):
                save(name, {'status':'checking'})
                try:
                    result = function()
                except SetupError as exc:
                    result = exc.result
                except PermissionError:
                    result = {'status':'approval_required', 'reason':'Workspace/tool write was denied',
                              'next_action':'Ask the user to allow installation at this workspace path, then resume setup. Do not bypass the denial.'}
                except (OSError, ValueError, KeyError) as exc:
                    result = {'status':'retryable_error', 'reason':type(exc).__name__,
                              'next_action':'Check the selected tool/runtime/network and retry; previous completed work is retained and details are omitted.'}
                save(name,result)
                return result
            packages = step('python_packages',lambda:_install_packages(workspace,downloads))
            compiler = step('tectonic',lambda:_install_tectonic(workspace,downloads))
            if compiler.get('executable') and packages['status'] in {'available','installed'}:
                step('tex_cache',lambda:_warm_tex(workspace,compiler['executable'],downloads,lambda v:save('tex_cache',v)))
            else:
                save('tex_cache',{'status':'waiting_for_dependencies','next_action':'Resolve PDF Python/Tectonic setup first; profile collection can continue.'})
            if browser == 'missing':
                step('browser',lambda:_install_browser(workspace,host,downloads))
            else:
                save('browser',{'status':{'existing':'available','defer':'deferred','inspect':'host_inspection_required'}[browser],
                                'next_action':'Use the host-approved browser API; presence of a CLI alone proves no browser session.'})
            search_status = {'existing':'available','defer':'deferred','inspect':'host_inspection_required',
                             'missing':'available_via_browser' if state['steps']['browser']['status'] == 'available' else 'host_connection_required'}[search]
            save('search',{'status':search_status,
                           'next_action':'Inspect host search tools. If unavailable, enable an approved search connection or use the configured browser after reload; do not install accounts or API credentials.'})
            save('login',{'status':'user_action_when_target_known','next_action':'Ask for local sign-in to the actual requested site when needed; never install credentials, bypass CAPTCHA/2FA or infer login state.'})
            states = [s['status'] for k,s in state['steps'].items() if k not in {'search','login'}]
            state['status'] = 'approval_required' if 'approval_required' in states else 'host_reload_required' if 'host_reload_required' in states else 'ready' if all(s in {'available','installed','deferred','host_inspection_required'} for s in states) else 'partial'
            if state['status'] == 'ready' and ('host_inspection_required' in states or search_status == 'host_inspection_required'):
                state['status'] = 'host_inspection_required'
            elif state['status'] == 'ready' and search_status == 'host_connection_required':
                state['status'] = 'partial'
            state['state_saved'] = True
            state['python_executable'] = packages.get('python_executable',sys.executable)
            state['next_action'] = 'Use the returned Python for helpers. Continue saved onboarding; request only actual pending permission, host connection or sign-in actions.'
            if state['installation_policy'] == 'deferred':
                state['next_action'] = 'Installation was deferred by the user. Continue independent profile work without asking again or downloading. After the user authorizes installation, resume with --resume-installation; host/OS permission is still required.'
            atomic(state_path,state)
        finally:
            lock.unlink(missing_ok=True)
    except PermissionError:
        return {'status':'approval_required','state_saved':False,'next_action':'Ask the user to allow writes/command execution for this workspace, then resume. No successful setup was saved.'}
    except SetupError as exc:
        return _state_failure(workspace, exc)
    return state
