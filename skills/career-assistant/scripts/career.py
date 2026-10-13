#!/usr/bin/env python3
"""Local workflow helpers. The host agent supplies evidence-backed JSON and browser observations."""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from pathlib import Path
from storage import Store, load
import profiles
import jobs
import resume

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workspace', type=Path, default=Path.cwd())
    sub = ap.add_subparsers(dest='command', required=True)
    for name in ['init', 'status', 'doctor', 'workday-init']:
        sub.add_parser(name)
    p = sub.add_parser('import-source'); p.add_argument('path', type=Path); p.add_argument('--kind', choices=['document','user-statement'], default='document')
    for name in ['profile-update', 'preferences-update', 'assess', 'grant']:
        p = sub.add_parser(name); p.add_argument('--input', required=True, type=Path)
    p = sub.add_parser('role-create'); p.add_argument('--input', required=True, type=Path); p.add_argument('--host', choices=['codex','claude','both'], default='both')
    p = sub.add_parser('role-retry'); p.add_argument('role_id')
    p = sub.add_parser('checkpoint'); p.add_argument('step'); p.add_argument('--note', default='')
    p = sub.add_parser('render'); p.add_argument('job_id'); p.add_argument('--input', required=True, type=Path); p.add_argument('--source-only', action='store_true')
    p = sub.add_parser('visual-review'); p.add_argument('job_id'); p.add_argument('--input', required=True, type=Path)
    p = sub.add_parser('application-add'); p.add_argument('job_id')
    for name in ['prepare', 'outcome']:
        p = sub.add_parser(name); p.add_argument('application_id'); p.add_argument('--input', required=True, type=Path)
    p = sub.add_parser('begin-submit'); p.add_argument('application_id')
    args = ap.parse_args(argv)
    store = Store(args.workspace)
    data = load(args.input) if hasattr(args, 'input') else None
    command = args.command
    if command == 'doctor':
        import importlib.util
        return {'python': sys.version.split()[0], 'tools': {x: bool(shutil.which(x)) for x in ['tectonic','node','npm','codex','claude']}, 'packages': {x: importlib.util.find_spec(x) is not None for x in ['pypdf','fitz']}, 'browser': 'Host must inspect available browser tools; CLI presence is not proof of an active session'}
    if command == 'init': return store.initialize()
    if command == 'workday-init':
        store.read('profile.json')
        with store.lock():
            directory = store.root / 'credentials' / 'workday'
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / 'accounts.txt'
            if not path.exists():
                path.touch(mode=0o600)
        return {'path': str(path), 'format': 'One username: <value>, password: <value> pair per nonempty line', 'next_action': 'User fills the local file; never paste credentials into chat. Existing contents are preserved.'}
    if command == 'status': return store.status()
    if command == 'import-source': return profiles.import_source(store, args.path, args.kind)
    if command == 'profile-update': return profiles.update_profile(store, data)
    if command == 'preferences-update': return profiles.update_preferences(store, data)
    if command == 'role-create': return profiles.role_create(store, data, ['codex','claude'] if args.host == 'both' else [args.host])
    if command == 'role-retry': return profiles.role_retry(store, args.role_id)
    if command == 'checkpoint': return profiles.checkpoint(store, args.step, args.note)
    if command == 'assess': return jobs.assess(store, data)
    if command == 'render': return resume.render(store, args.job_id, data, not args.source_only)
    if command == 'visual-review': return resume.visual_review(store, args.job_id, data)
    if command == 'application-add': return jobs.add_application(store, args.job_id)
    if command == 'grant': return jobs.grant(store, data)
    if command == 'prepare': return jobs.prepare(store, args.application_id, data)
    if command == 'begin-submit': return jobs.begin_submit(store, args.application_id)
    if command == 'outcome': return jobs.outcome(store, args.application_id, data)
    raise ValueError('Unknown command')

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    try:
        print(json.dumps(main(), ensure_ascii=False, indent=2))
    except (ValueError, KeyError, FileNotFoundError, TimeoutError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
