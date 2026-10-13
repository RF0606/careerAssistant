#!/usr/bin/env python3
"""Install the self-contained skill into a project or user skill directory."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime, timezone

SOURCE = Path(__file__).resolve().parent / 'skills' / 'career-assistant'

def inventory(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError('Symlinked skill resources are not installed')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc':
            result[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result

def install(workspace, host='both', scope='project', replace=False, user_root=None):
    workspace = Path(workspace).resolve()
    base = workspace if scope == 'project' else Path(user_root or Path.home()).resolve()
    folders = ['.agents', '.claude'] if host == 'both' else ['.agents' if host == 'codex' else '.claude']
    fingerprint = inventory(SOURCE)
    targets = [base / folder / 'skills' / 'career-assistant' for folder in folders]
    if scope == 'project':
        for folder in folders:
            global_copy = Path(user_root or Path.home()) / folder / 'skills' / 'career-assistant'
            if global_copy.exists():
                if inventory(global_copy) != fingerprint:
                    raise ValueError(f'A different user-scoped copy also exists: {global_copy}. Resolve it explicitly before project installation.')
                print(f'Notice: identical user-scoped skill exists at {global_copy}; both may appear in the host picker.')
    for dest in targets:
        if dest.exists() and inventory(dest) != fingerprint and not replace:
            raise ValueError(f'Different installed version: {dest}. Review it, then use --replace to back up and replace.')
    actions = []
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    for dest in targets:
        if dest.exists() and inventory(dest) == fingerprint:
            actions.append({'host': dest.parts[-3], 'action': 'unchanged'})
            continue
        if dest.exists():
            backup = base / '.career-assistant' / 'skill-backups' / stamp / dest.parts[-3] / 'career-assistant'
            backup.parent.mkdir(parents=True, exist_ok=True)
            dest.rename(backup)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SOURCE, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        if inventory(dest) != fingerprint:
            raise ValueError('Installed copy failed hash verification')
        actions.append({'host': dest.parts[-3], 'action': 'installed'})
    return {'actions': actions, 'scope': scope, 'note': 'Open this workspace in your host and say: 帮我初始化信息. Private data is created only by initialization.'}

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workspace', type=Path, default=Path.cwd())
    ap.add_argument('--host', choices=['codex','claude','both'], default='both')
    ap.add_argument('--scope', choices=['project','user'], default='project')
    ap.add_argument('--replace', action='store_true')
    args = ap.parse_args()
    try:
        print(json.dumps(install(args.workspace,args.host,args.scope,args.replace),ensure_ascii=False,indent=2))
    except ValueError as exc:
        raise SystemExit(str(exc))
