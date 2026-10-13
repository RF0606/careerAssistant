"""Local, optional capability checks; no installs or global configuration changes."""
import importlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


def write_probe(directory):
    try:
        directory.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix='.career-write-check-', dir=directory)
        os.close(fd)
        Path(name).unlink()
        return {'path': str(directory), 'writable': True}
    except OSError as exc:
        return {'path': str(directory), 'writable': False, 'reason': type(exc).__name__,
                'next_action': 'Allow writes to this workspace/path or resolve the file conflict. A host policy denial must be resolved in the host; do not bypass it.'}


def pdf_smoke(workspace, compiler):
    if not compiler:
        return {'status': 'unavailable', 'next_action': 'Install Tectonic locally; profile setup and source-only drafts remain available.'}
    directory = workspace / '.career-assistant/diagnostics' / ('pdf-probe-' + uuid.uuid4().hex[:12])
    try:
        directory.mkdir(parents=True)
        source = directory / 'probe.tex'
        source.write_text('\\documentclass{article}\n\\begin{document}Career Assistant cache probe.\\end{document}\n', encoding='utf-8')
        result = subprocess.run([compiler, '--only-cached', '--outdir', str(directory), str(source)],
                                capture_output=True, timeout=60)
        if result.returncode or not (directory / 'probe.pdf').is_file():
            return {'status': 'cache-unverified', 'offline_only': True,
                    'next_action': 'The offline probe failed. First compilation may need network access to download the TeX bundle. Keep resumes as drafts until a real build and PDF review pass.'}
        return {'status': 'passed', 'offline_only': True, 'path': str(directory / 'probe.pdf'),
                'scope': 'Only this small TeX probe was compiled; it does not validate a resume or every cached package.'}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'status': 'blocked', 'reason': type(exc).__name__, 'next_action': 'Check local execution/write permissions and Tectonic installation. Profile setup can continue.'}


def report(workspace, host='codex', probe_writes=False, check_pdf=False):
    workspace = Path(workspace).resolve()
    tools = {name: shutil.which(name) for name in ['tectonic', 'node', 'npm', 'codex', 'claude']}
    packages, package_errors = {}, {}
    for name in ['pypdf', 'fitz']:
        try:
            importlib.import_module(name)
            packages[name] = True
        except (ImportError, OSError) as exc:
            packages[name] = False
            package_errors[name] = type(exc).__name__
    local_python = workspace / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    actions = []
    if not all(packages.values()):
        commands = [] if local_python.is_file() else [[sys.executable, '-m', 'venv', str(workspace / '.venv')]]
        commands.append([str(local_python), '-m', 'pip', 'install', 'pypdf>=5,<7', 'PyMuPDF>=1.25,<2'])
        actions.append({'feature': 'pdf', 'next_action': 'Use a workspace .venv for PDF packages; reuse a compatible existing environment. Invoke its Python directly; shell activation and administrator access are unnecessary.', 'commands': commands})
    if not tools['tectonic']:
        actions.append({'feature': 'pdf-generation', 'next_action': 'Use the official Tectonic binary for this OS, place it in a local tools directory and expose it to this session PATH.',
                        'documentation': 'https://tectonic-typesetting.github.io/en-US/install.html'})
    actions.append({'feature': 'browser', 'next_action': 'The host must inspect its supported live browser APIs. Browser absence does not block profile setup or resume drafting; hand off login/upload if a required API is unavailable.'})
    result = {'python': sys.version.split()[0], 'python_executable': sys.executable,
              'platform': platform.system(), 'tools': {name: bool(value) for name, value in tools.items()},
              'packages': packages, 'package_errors': package_errors,
              'features': {'profile_text_docx_and_scoring': True, 'pdf_import': packages['pypdf'],
                           'pdf_generation_and_qa': bool(tools['tectonic'] and packages['fitz']),
                           'browser': 'host-inspection-required'},
              'browser': 'CLI presence is not proof of a usable host browser session', 'next_actions': actions,
              'permissions': 'Not probed. Host policy is separate from OS filesystem permissions.'}
    if probe_writes:
        folders = ['.agents', '.claude'] if host == 'both' else ['.agents' if host == 'codex' else '.claude']
        result['permissions'] = {'host_policy': 'The host must authorize the command before this probe can run.',
                                 'probes': [write_probe(workspace / '.career-assistant'),
                                            *(write_probe(workspace / folder / 'skills') for folder in folders)]}
    if check_pdf:
        result['pdf_cache_probe'] = pdf_smoke(workspace, tools['tectonic'])
    return result
