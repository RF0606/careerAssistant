#!/usr/bin/env python3
"""Local workflow helpers. The host agent supplies evidence-backed JSON and browser observations."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
if sys.version_info < (3, 10):
    print(json.dumps({'error': 'Python 3.10+ is required. Select a supported python/python3/py -3 interpreter or install it from python.org; no career data was written.'}), file=sys.stderr)
    sys.exit(1)
from storage import Store, load, slug
import profiles
import jobs
import resume

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workspace', type=Path, default=Path.cwd())
    sub = ap.add_subparsers(dest='command', required=True)
    for name in ['init', 'status', 'workday-init']:
        sub.add_parser(name)
    p = sub.add_parser('doctor'); p.add_argument('--host', choices=['codex','claude','both']); p.add_argument('--probe-writes', action='store_true'); p.add_argument('--pdf-smoke', action='store_true')
    p = sub.add_parser('import-source'); p.add_argument('path', type=Path); p.add_argument('--kind', choices=['document','user-statement'], default='document')
    for name in ['profile-update', 'preferences-update', 'assess', 'grant']:
        p = sub.add_parser(name); p.add_argument('--input', required=True, type=Path)
    p = sub.add_parser('role-create'); p.add_argument('--input', required=True, type=Path); p.add_argument('--host', choices=['codex','claude','both'])
    p = sub.add_parser('role-retry'); p.add_argument('role_id')
    p = sub.add_parser('checkpoint'); p.add_argument('step'); p.add_argument('--note', default='')
    p = sub.add_parser('render'); p.add_argument('job_id'); p.add_argument('--input', required=True, type=Path); p.add_argument('--source-only', action='store_true')
    p = sub.add_parser('visual-review'); p.add_argument('job_id'); p.add_argument('--input', required=True, type=Path)
    p = sub.add_parser('application-add'); p.add_argument('job_id')
    for name in ['prepare', 'outcome']:
        p = sub.add_parser(name); p.add_argument('application_id'); p.add_argument('--input', required=True, type=Path)
    p = sub.add_parser('begin-submit'); p.add_argument('application_id')
    p = sub.add_parser('backup'); p.add_argument('--label', default='manual')
    p = sub.add_parser('backup-verify'); p.add_argument('archive', type=Path)
    p = sub.add_parser('restore-plan'); p.add_argument('archive', type=Path)
    sub.add_parser('migrate-plan')
    sub.add_parser('maintenance-recover')
    p = sub.add_parser('history'); p.add_argument('--limit', type=int, default=20); p.add_argument('--path')
    for name in ['restore', 'migrate']:
        p = sub.add_parser(name); p.add_argument('--plan', required=True); p.add_argument('--confirmation', required=True)
    args = ap.parse_args(argv)
    store = Store(args.workspace)
    data = load(args.input) if hasattr(args, 'input') else None
    command = args.command
    active_host = 'claude' if Path(__file__).resolve().parents[3].name == '.claude' else 'codex'
    if command in {'backup', 'backup-verify', 'restore-plan', 'restore', 'migrate-plan', 'migrate', 'maintenance-recover', 'history'}:
        import maintenance
        if command == 'backup': return maintenance.backup(store, args.label)
        if command == 'backup-verify': return maintenance.verify_backup(args.archive)
        if command == 'restore-plan': return maintenance.plan(store, args.archive)
        if command == 'migrate-plan': return maintenance.plan(store, operation='migrate')
        if command == 'maintenance-recover': return maintenance.recover(store)
        if command == 'history': return maintenance.history(store, args.limit, args.path)
        return maintenance.apply(store, args.plan, args.confirmation, expected_operation=command)
    if command == 'doctor':
        from capabilities import report
        return report(args.workspace, args.host or active_host, args.probe_writes, args.pdf_smoke)
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
    if command == 'role-create':
        if args.host:
            hosts = ['codex','claude'] if args.host == 'both' else [args.host]
        else:
            rid = slug(data['id'])
            role_file = store.root / f'roles/{rid}.json'
            previous = store.read(f'roles/{rid}.json') if role_file.is_file() else {}
            saved = (previous.get('generation') or {}).get('hosts', [])
            hosts = saved if isinstance(saved, list) and saved and all(h in {'codex','claude'} for h in saved) else [active_host]
        return profiles.role_create(store, data, hosts)
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
    except OSError as exc:
        print(json.dumps({'error': f'Local operation failed ({type(exc).__name__}) at {exc.filename or "the requested path"}. Check workspace writes, path conflicts and local tool execution. Resolve a host policy denial in the host; do not bypass it.'}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
