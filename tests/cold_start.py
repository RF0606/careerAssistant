"""Cold-start acceptance in a new fictional workspace and dependency-free venv."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import venv

PROJECT = Path(__file__).resolve().parents[1]


def run(results):
    directory = Path(results).resolve() / ('cold-' + uuid.uuid4().hex[:12])
    directory.mkdir(parents=True)
    environment = directory / '.venv'
    venv.EnvBuilder(with_pip=False).create(environment)
    executable = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    workspace = directory / 'fictional-workspace'
    workspace.mkdir()
    empty_path = directory / 'empty-path'
    empty_path.mkdir()
    isolated = dict(os.environ, PATH=str(empty_path), PYTHONNOUSERSITE='1')
    for key in ['PYTHONPATH', 'PYTHONHOME']:
        isolated.pop(key, None)
    checks = []

    def command(args, success=True, env=isolated):
        result = subprocess.run([str(executable), *map(str, args)], env=env, cwd=workspace,
                                capture_output=True, text=True, encoding='utf-8', timeout=60)
        assert result.returncode == (0 if success else 1), result.stderr
        return json.loads(result.stdout if success else result.stderr)

    command([PROJECT / 'install.py', '--workspace', workspace, '--host', 'codex'])
    helper = workspace / '.agents/skills/career-assistant/scripts/career.py'
    doctor = command([helper, '--workspace', workspace, 'doctor', '--probe-writes', '--pdf-smoke'])
    assert not any(doctor['packages'].values()) and not any(doctor['tools'].values())
    assert doctor['features']['profile_text_docx_and_scoring']
    assert doctor['features']['browser'] == 'host-inspection-required'
    assert doctor['pdf_cache_probe']['status'] == 'unavailable'
    assert all(probe['writable'] for probe in doctor['permissions']['probes'])
    checks.append('missing-optional-tools-and-packages-guided')
    command([helper, '--workspace', workspace, 'init'])
    assert not (workspace / '.career-assistant/routes').exists()
    assert not list((workspace / '.agents/skills').glob('career-resume-*'))
    checks.append('empty-init-without-optional-dependencies')
    command([PROJECT / 'tests/fixtures.py', workspace])
    args = [helper, '--workspace', workspace, 'render', 'demo-job', '--input', workspace / '.career-assistant/demo-draft.json']
    draft = command([*args, '--source-only'])
    assert draft['status'] == 'draft'
    checks.append('facts-role-skill-scoring-and-source-only-without-dependencies')
    profile = (workspace / '.career-assistant/profile.json').read_bytes()
    failure = command(args, success=False)
    assert 'Tectonic is missing' in failure['error']
    checks.append('missing-compiler-keeps-draft')
    if shutil.which('tectonic'):
        # Restore tools, but the venv still has no PDF Python packages.
        failure = command(args, success=False, env=dict(os.environ, PYTHONNOUSERSITE='1'))
        assert 'PyMuPDF' in failure['error']
        assert not (workspace / '.career-assistant/packages/demo-job/compile-output.txt').exists()
        checks.append('missing-pdf-qa-blocks-before-compiler-or-download')
    assert (workspace / '.career-assistant/profile.json').read_bytes() == profile
    validation = json.loads((workspace / '.career-assistant/packages/demo-job/validation.json').read_text())
    assert validation['status'] == 'draft'
    assert not (workspace / '.career-assistant/packages/demo-job/resume.pdf').exists()
    checks.append('failures-preserve-profile-and-do-not-create-ready-pdf')
    result = {'passed': checks, 'workspace': str(workspace), 'python': sys.version.split()[0], 'platform': sys.platform,
              'doctor': doctor, 'scope': 'Fictional user, isolated venv, empty PATH; no installs, cache warming or browser login'}
    (directory / 'results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=PROJECT / 'test-results/cold-start')
    print(json.dumps(run(parser.parse_args().results), indent=2))
