#!/usr/bin/env python3
"""Build/verify a public release using a closed allowlist, never a workspace walk ZIP."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
ROOT_FILES = {'README.md','LICENSE','VERSION','AGENTS.md','CLAUDE.md','START_HERE_CODEX.md','.gitignore','.gitattributes','install.py','release.py','requirements.txt','package.json','package-lock.json'}
TREES = {'skills','tests','examples','docs'}
SUFFIXES = {'.md','.py','.mjs','.json','.tex','.yaml','.txt','.html'}
MANIFEST = 'release_manifest.json'

def sha(data): return hashlib.sha256(data).hexdigest()

def public_files():
    files = []
    for name in sorted(ROOT_FILES):
        p = ROOT / name
        if not p.is_file():
            raise ValueError(f'Missing required public file: {name}')
        files.append(p)
    for name in sorted(TREES):
        if (ROOT/name).is_symlink(): raise ValueError('Symlinked release tree')
        for p in sorted((ROOT/name).rglob('*')):
            if '__pycache__' in p.parts or p.suffix == '.pyc': continue
            if p.is_symlink(): raise ValueError('Symlink in release tree')
            if name == 'skills' and p.is_dir() and (p.name.casefold() == 'routes' or p.name.casefold().startswith('career-resume-')):
                raise ValueError('Personal routes/skills must be generated locally after download, not bundled in shared skills')
            if p.is_file():
                if p.suffix not in SUFFIXES: raise ValueError(f'Unexpected file in public tree: {p.relative_to(ROOT)}')
                if any(x in p.parts for x in ['.career-assistant','credentials','browser','skill-backups','node_modules']):
                    raise ValueError('Private/runtime directory in release tree')
                files.append(p)
    return files

def scan(files, denied=()):
    forbidden = [r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b',r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b', r'(?im)^\s*username\s*[:：]\s*[^<\s][^\r\n]*[,，]\s*password\s*[:：]']
    for p in files:
        if p.is_symlink(): raise ValueError('Symlinked public file')
        txt = p.read_text(encoding='utf-8')
        if any(re.search(pattern,txt) for pattern in forbidden) or any(s in txt for s in denied):
            raise ValueError(f'Private identifier/credential pattern in {p.relative_to(ROOT)}; values omitted')
        if re.search(r'[A-Z]:[\\/]Users[\\/]', txt):
            raise ValueError(f'Machine-specific absolute path in {p.relative_to(ROOT)}')

def manifest(denied=()):
    files=public_files(); scan(files,denied)
    value={'version':(ROOT/'VERSION').read_text().strip(),'files':{p.relative_to(ROOT).as_posix():{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in files}}
    (ROOT/MANIFEST).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    return value

def verify(denied=()):
    recorded=json.loads((ROOT/MANIFEST).read_text(encoding='utf-8'))
    files=public_files(); scan(files,denied)
    actual={p.relative_to(ROOT).as_posix():{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in files}
    if actual != recorded['files'] or recorded['version'] != (ROOT/'VERSION').read_text().strip():
        raise ValueError('Release manifest differs; inspect changes then run manifest')
    return recorded

def pack(output,denied=()):
    recorded=verify(denied)
    output=Path(output).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix('.zip.tmp')
    with ZipFile(temp,'w',ZIP_DEFLATED) as z:
        for name in sorted([*recorded['files'],MANIFEST]):
            z.write(ROOT/name,name)
    with ZipFile(temp) as z:
        if z.testzip(): raise ValueError('ZIP integrity failure')
        for name,info in recorded['files'].items():
            if sha(z.read(name)) != info['sha256']: raise ValueError('ZIP hash mismatch')
    temp.replace(output)
    output.with_suffix('.zip.sha256').write_text(sha(output.read_bytes())+'  '+output.name+'\n',encoding='utf-8')
    # A reproducible handoff bundle accompanies every ZIP; no separate manual copy step.
    startup = output.parent / 'START_HERE.txt'
    startup.write_text('Career Assistant v' + recorded['version'] + '\n\n'
        '1. Extract ' + output.name + ' into a new folder. README.md should be at its root.\n'
        '2. Open that folder in Codex or Claude Code with file-write and command permissions.\n'
        '3. Say: 帮我初始化信息\n'
        'The assistant collects and saves your profile step by step. No manual JSON is needed.\n'
        'Standard tools/templates only; enrich your personal knowledge and routes locally after download.\n'
        'Optional install: python install.py --host both\n'
        'Core requires Python 3.10+. PDF: Tectonic and pip install -r requirements.txt.\n'
        'See README.md for normal use; docs/VALIDATION.md for acceptance limits.\n'
        'Maintainers: read START_HERE_CODEX.md. Do not treat mock tests as live-site certification.\n'
        'Workday passwords belong only in the ignored local credentials file; never paste them in chat.\n'
        'This package contains no personal profile or login credentials.\n', encoding='utf-8')
    artifacts = [output, output.with_suffix('.zip.sha256'), startup]
    (output.parent/'SHA256SUMS.txt').write_text(''.join(sha(p.read_bytes())+'  '+p.name+'\n' for p in artifacts), encoding='utf-8')
    return {'version':recorded['version'],'file':str(output),'sha256':sha(output.read_bytes()),'files':len(recorded['files'])+1,'bytes':output.stat().st_size}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('action',choices=['manifest','verify','pack']); ap.add_argument('--output',type=Path); ap.add_argument('--deny-string',action='append',default=[]); args=ap.parse_args()
    try:
        if args.action=='manifest': result=manifest(args.deny_string)
        elif args.action=='verify': result=verify(args.deny_string)
        else:
            if not args.output: ap.error('--output required')
            result=pack(args.output,args.deny_string)
        print(json.dumps({'success':True,'version':result.get('version'),'files':len(result['files']) if isinstance(result.get('files'),dict) else result.get('files'),**({k:result[k] for k in ['file','sha256','bytes']} if 'file' in result else {})},indent=2))
    except (ValueError,FileNotFoundError) as exc:
        raise SystemExit(str(exc))
