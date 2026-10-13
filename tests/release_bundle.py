"""Build and independently verify only the standard distribution for CI/releases."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
from zipfile import ZipFile

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_release', PROJECT / 'release.py')
releaser = importlib.util.module_from_spec(spec); spec.loader.exec_module(releaser)


def build(output, tag=None):
    version = (PROJECT / 'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version) or tag is not None and tag != 'v' + version:
        raise ValueError('Version/tag mismatch; no assets published')
    if tag:
        tagged = subprocess.run(['git', 'rev-parse', 'refs/tags/' + tag + '^{commit}'], cwd=PROJECT, capture_output=True, text=True, check=True).stdout.strip()
        current = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=PROJECT, capture_output=True, text=True, check=True).stdout.strip()
        if tagged != current:
            raise ValueError('Release source is not the exact tagged commit')
    releaser.tracked_check()
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=True)
    result = releaser.pack(output / ('career-assistant-v' + version + '.zip'))
    with ZipFile(result['file']) as archive:
        manifest = json.loads(archive.read('release_manifest.json'))
        if set(archive.namelist()) != set(manifest['files']) | {'release_manifest.json'}:
            raise ValueError('Distribution ZIP file list differs')
        for name, value in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != value['sha256']:
                raise ValueError('Distribution ZIP hash differs')
    for line in (output / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1)
        if hashlib.sha256((output / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Distribution handoff checksum differs')
    expected_files = {'career-assistant-v' + version + '.zip', 'career-assistant-v' + version + '.zip.sha256', 'START_HERE.txt', 'SHA256SUMS.txt'}
    if {p.name for p in output.iterdir() if p.is_file()} != expected_files:
        raise ValueError('Release output directory contains extra files; use a clean dedicated directory')
    return {'version': version, 'files': result['files'], 'sha256': result['sha256'], 'public_assets_verified': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True); parser.add_argument('--tag')
    try:
        args = parser.parse_args(); print(json.dumps(build(args.output, args.tag), indent=2))
    except (ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc))
