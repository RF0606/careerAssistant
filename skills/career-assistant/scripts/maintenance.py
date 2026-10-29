"""Private knowledge history, verified backups and recoverable local data operations."""
from __future__ import annotations
import json
import os
from pathlib import Path, PurePosixPath
import stat
import uuid
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile
from storage import SCHEMA, VERSION, atomic, atomic_bytes, digest, inside, json_bytes, load, no_secrets, now, slug, validate_preferences

CORE = {'workspace.json', 'profile.json', 'preferences.json', 'onboarding.json', 'sources.json', 'tracker.json'}
REQUIRED = CORE - {'workspace.json'}
TREES = {'sources', 'roles', 'routes', 'jobs', 'packages', 'evidence', 'history'}
SUFFIXES = {'.json', '.txt', '.md', '.pdf', '.docx', '.tex', '.png', '.log'}
EXCLUDED = {'credentials', 'browser', 'browser-data', 'backups', 'maintenance', 'skill-backups', 'node_modules', '__pycache__', '.secrets'}
MAX_FILE = 100_000_000
MAX_TOTAL = 1_000_000_000
MAX_FILES = 30_000
BACKUP_MANIFEST = 'private_backup_manifest.json'


def permitted(name):
    if not isinstance(name, str) or '\\' in name or ':' in name or '\x00' in name:
        return False
    parts = name.split('/')
    if any(not p or p in {'.', '..'} or p.casefold() in EXCLUDED for p in parts):
        return False
    return name in CORE or (parts[0] in TREES and len(parts) > 1 and PurePosixPath(name).suffix.lower() in SUFFIXES)


def knowledge_path(name):
    return name in {'profile.json', 'preferences.json', 'sources.json'} or name.startswith(('roles/', 'routes/'))


def record_write(store, name, after, write):
    if not knowledge_path(name):
        return write()
    target = inside(store.root, store.root / name)
    before = target.read_bytes() if target.is_file() else None
    if before == after:
        return
    if name.endswith('.json'):
        no_secrets(json.loads(after.decode('utf-8-sig')))
        if before:
            no_secrets(json.loads(before.decode('utf-8-sig')))
    event_id = 'event-' + uuid.uuid4().hex
    event = {'schema_version': SCHEMA, 'id': event_id, 'path': name, 'operation': 'write',
             'created_at': now(), 'status': 'prepared', 'before_sha256': digest(before) if before is not None else None,
             'after_sha256': digest(after)}
    for label, content in [('before', before), ('after', after)]:
        if content is not None:
            key = digest(content)
            obj = store.root / f'history/objects/{key}'
            if not obj.exists():
                atomic_bytes(inside(store.root, obj), content)
            event[label + '_object'] = f'history/objects/{key}'
    path = store.root / f'history/events/{event_id}.json'
    atomic(path, event)
    try:
        write()
    except Exception:
        event['status'] = 'failed'
        atomic(path, event)
        raise
    event['status'] = 'applied'
    atomic(path, event)


def history(store, limit=20, path=None):
    store.check_maintenance()
    if not 1 <= limit <= 100:
        raise ValueError('History limit must be 1-100')
    rows = [load(p) for p in (store.root / 'history/events').glob('*.json')]
    if path:
        rows = [r for r in rows if r.get('path') == path]
    rows.sort(key=lambda r: (r['created_at'], r['id']), reverse=True)
    return {'entries': [{k: r.get(k) for k in ['id', 'created_at', 'operation', 'path', 'status', 'before_sha256', 'after_sha256']} for r in rows[:limit]],
            'values_omitted': True, 'snapshot_location': str(store.root / 'history/objects')}


def collect(store):
    files = {}
    root = store.root.resolve()
    if store.root.exists() and (store.root.is_symlink() or root != store.root.absolute()):
        raise ValueError('Use a regular private data directory in the selected workspace; linked roots are not maintained')
    candidates = [store.root / name for name in CORE if (store.root / name).is_file()]
    for tree in sorted(TREES):
        directory = store.root / tree
        if not directory.exists():
            continue
        for base, dirs, names in os.walk(directory, followlinks=False):
            dirs[:] = [d for d in dirs if d.casefold() not in EXCLUDED]
            for item in [Path(base), *(Path(base) / d for d in dirs)]:
                if item.is_symlink() or not item.resolve().is_relative_to(root) or (hasattr(item, 'is_junction') and item.is_junction()):
                    raise ValueError('Unsafe linked data directory; preserve it and use local regular files')
            candidates.extend(Path(base) / name for name in names)
    total = 0
    for item in sorted(candidates):
        name = item.relative_to(store.root).as_posix()
        # Content-addressed history objects intentionally have no suffix.
        if name.startswith('history/objects/'):
            if len(name.split('/')) != 3 or len(item.name) != 64 or any(c not in '0123456789abcdef' for c in item.name):
                raise ValueError('Invalid history object name')
        elif not permitted(name):
            raise ValueError('Unexpected file in career-data tree; values omitted')
        resolved = inside(store.root, item)
        if item.is_symlink() or resolved != item.absolute():
            raise ValueError('Linked career files are not backed up or restored')
        size = item.stat().st_size
        if size > MAX_FILE:
            raise ValueError('A career-data file exceeds the backup size limit')
        total += size
        if total > MAX_TOTAL or len(files) >= MAX_FILES:
            raise ValueError('Career backup exceeds the size/file-count limit')
        content = item.read_bytes()
        if name.startswith('history/objects/') and item.name != digest(content):
            raise ValueError('Knowledge history object hash differs; preserve data')
        if item.suffix.lower() == '.json':
            no_secrets(json.loads(content.decode('utf-8-sig')))
        files[name] = content
    return files


def valid_member(name):
    if name.startswith('history/objects/'):
        parts = name.split('/')
        return len(parts) == 3 and len(parts[-1]) == 64 and all(c in '0123456789abcdef' for c in parts[-1])
    return permitted(name)


def active_document(name):
    # Attempt snapshots are immutable historical bytes, including their old schema.
    parts = name.split('/')
    return (name in CORE or len(parts) == 2 and parts[0] in {'roles', 'jobs'} and name.endswith('.json')
            or len(parts) == 3 and parts[0] == 'packages' and parts[2] in {'validation.json', 'match-report.json'})


def validate_data(files, schema):
    if schema not in {1, SCHEMA} or not REQUIRED <= set(files):
        raise ValueError('Unsupported or incomplete career-data schema; preserve data')
    def document(name):
        value = json.loads(files[name].decode('utf-8-sig'))
        no_secrets(value)
        if not isinstance(value, dict) or value.get('schema_version') != schema:
            raise ValueError('Mixed or unsupported active data schemas; preserve data')
        return value
    docs = {name: document(name) for name in CORE if name in files}
    validate_preferences(docs['preferences.json'])
    for name in files:
        if name not in CORE and active_document(name):
            document(name)
    facts, sources = docs['profile.json']['facts'], docs['sources.json']['sources']
    if not isinstance(facts, dict) or not isinstance(sources, dict):
        raise ValueError('Invalid facts/sources structure')
    for fact in facts.values():
        if not fact.get('source_ids') or any(sid not in sources for sid in fact['source_ids']):
            raise ValueError('A fact has missing source references; restore a complete backup')
    for source in sources.values():
        name = source['text_path'].replace('\\', '/')
        if not name.startswith('sources/') or not valid_member(name) or name not in files:
            raise ValueError('A source text reference is missing or unsafe')
    tracker = docs['tracker.json']
    rows = tracker['records']
    if tracker.get('authority') != 'local' or tracker.get('record_count') != len(rows) or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Invalid single application tracker')
    if any(r['status'] not in {'Pending', 'Needs user', 'Blocked', 'Submitted'} for r in rows):
        raise ValueError('Invalid application status')
    if schema == SCHEMA:
        uuid.UUID(docs['workspace.json']['id'])
    return docs


def fingerprint(store, files):
    values = {name: digest(data) for name, data in files.items()}
    grants = store.root / 'grants.json'
    values['grants.json'] = digest(grants.read_bytes()) if grants.is_file() else None
    return digest(values)


def _backup(store, label='manual'):
    slug(label)
    files = collect(store)
    profile = json.loads(files.get('profile.json', b'{}').decode('utf-8-sig'))
    schema = profile.get('schema_version')
    docs = validate_data(files, schema)
    wid = docs.get('workspace.json', {}).get('id') or uuid.uuid5(uuid.NAMESPACE_URL, 'career-assistant:' + str(store.workspace)).hex
    manifest = {'kind': 'career-private-backup', 'backup_format': 1, 'data_schema': schema,
                'workspace_id': wid, 'created_at': now(), 'software_version': VERSION,
                'excluded': ['credentials', 'browser', 'grants', 'host-skills', 'backups', 'maintenance', 'caches'],
                'files': {name: {'sha256': digest(data), 'bytes': len(data)} for name, data in files.items()}}
    backup_id = 'backup-' + uuid.uuid4().hex
    destination = store.root / 'backups' / (backup_id + '-' + label + '.zip')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.zip.tmp')
    with ZipFile(temporary, 'w', ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
        archive.writestr(BACKUP_MANIFEST, json_bytes(manifest))
    read_archive(temporary)
    temporary.replace(destination)
    return {'id': backup_id, 'path': str(destination), 'sha256': digest(destination.read_bytes()),
            'files': len(files), 'data_schema': schema, 'excluded': manifest['excluded'],
            'notice': 'Private plaintext career backup. Keep it local/private; never attach it to a public release.'}


def backup(store, label='manual'):
    store.check_maintenance()
    with store.lock(maintenance=True):
        return _backup(store, label)


def read_archive(path):
    path = Path(path).resolve()
    if any(part.casefold() in {'credentials', 'browser'} for part in path.parts):
        raise ValueError('Credential/browser files are not career backups; values omitted')
    try:
        with ZipFile(path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(n.casefold() for n in names)) or BACKUP_MANIFEST not in names:
                raise ValueError('Duplicate backup paths or missing manifest')
            if len(names) > MAX_FILES + 1 or sum(i.file_size for i in infos) > MAX_TOTAL or any(i.file_size > MAX_FILE for i in infos):
                raise ValueError('Backup size limit exceeded')
            for info in infos:
                if info.filename != BACKUP_MANIFEST and not valid_member(info.filename) or stat.S_ISLNK(info.external_attr >> 16) or info.is_dir():
                    raise ValueError('Backup contains an unsafe, private or unexpected path; values omitted')
            manifest = json.loads(archive.read(BACKUP_MANIFEST).decode('utf-8-sig'))
            if manifest.get('kind') != 'career-private-backup' or manifest.get('backup_format') != 1:
                raise ValueError('Unsupported private backup format')
            uuid.UUID(manifest['workspace_id'])
            if set(names) != set(manifest['files']) | {BACKUP_MANIFEST}:
                raise ValueError('Backup manifest/file list differs')
            files = {name: archive.read(name) for name in manifest['files']}
            for name, data in files.items():
                if manifest['files'][name] != {'sha256': digest(data), 'bytes': len(data)}:
                    raise ValueError('Backup content/hash differs; no data restored')
                if name.startswith('history/objects/') and name.split('/')[-1] != digest(data):
                    raise ValueError('Backup history object hash differs')
            validate_data(files, manifest['data_schema'])
            return manifest, files
    except (BadZipFile, KeyError, json.JSONDecodeError, UnicodeError, RuntimeError):
        raise ValueError('Invalid career backup; values omitted') from None


def verify_backup(path):
    manifest, files = read_archive(path)
    return {'valid': True, 'files': len(files), 'data_schema': manifest['data_schema'], 'workspace_id': manifest['workspace_id'], 'values_omitted': True}


def upgrade(files, wid, stamp):
    files = dict(files)
    schema = json.loads(files['profile.json'].decode('utf-8-sig'))['schema_version']
    if schema not in {1, SCHEMA}:
        raise ValueError('No supported migration path; preserve data')
    for name, data in list(files.items()):
        if not active_document(name):
            continue
        value = json.loads(data.decode('utf-8-sig'))
        value['schema_version'] = SCHEMA
        if name == 'preferences.json':
            value.setdefault('revision', 0)
            value.setdefault('updated_at', stamp)
        files[name] = json_bytes(value)
    if 'workspace.json' not in files:
        files['workspace.json'] = json_bytes({'schema_version': SCHEMA, 'id': wid, 'created_at': stamp})
    from roles import context_digest
    for name, data in list(files.items()):
        if name.startswith('roles/') and name.endswith('.json'):
            role = json.loads(data)
            route = role.get('route_path')
            if role.get('generation') and route in files:
                role['generation']['context_hash'] = context_digest(role, digest(files[route]))
                files[name] = json_bytes(role)
    return files


def nonempty(files):
    for name, key in [('profile.json', 'facts'), ('sources.json', 'sources'), ('preferences.json', 'targets'), ('tracker.json', 'records')]:
        if name in files and json.loads(files[name].decode('utf-8-sig')).get(key):
            return True
    return any(name.startswith('roles/') for name in files)


def combine(current, incoming, operation):
    from jobs import duplicate_kind, reviewed_separate
    incoming = dict(incoming)
    if operation == 'restore':
        # Immutable sources/audit and current application artifacts stay available.
        for name, data in current.items():
            if name.startswith(('sources/', 'history/', 'jobs/', 'packages/', 'evidence/')):
                incoming[name] = data
        if 'tracker.json' in current:
            old = json.loads(current['tracker.json'].decode('utf-8-sig'))
            restored = json.loads(incoming['tracker.json'])
            by_id = {row['id']: row for row in restored['records']}
            for row in old['records']:
                other = by_id.get(row['id'])
                if other and other['status'] == 'Submitted' and row['status'] != 'Submitted':
                    raise ValueError('Backup/current submission histories conflict; restore into a separate empty workspace for manual reconciliation')
                for candidate in by_id.values():
                    if candidate['id'] != row['id']:
                        kind = duplicate_kind(candidate, row)
                        if kind == 'exact' or kind == 'ambiguous' and not (reviewed_separate(candidate, row) or reviewed_separate(row, candidate)):
                            raise ValueError('Conflicting duplicate application histories; reconcile before restoring')
                by_id[row['id']] = row
            restored['records'] = list(by_id.values())
            restored['record_count'] = len(restored['records'])
            incoming['tracker.json'] = json_bytes(restored)
    tracker = json.loads(incoming['tracker.json'])
    tracker['schema_version'] = SCHEMA
    for row in tracker['records']:
        for attempt in row['attempts']:
            for key in ['resume_path', 'evidence_path']:
                if key in attempt:
                    attempt[key] = attempt[key].replace('\\', '/')
            if attempt.get('outcome') == 'prepared':
                attempt['outcome'] = 'paused'
                row['status'] = 'Needs user'
                row['next_action'] = 'Review restored materials and obtain new explicit submission authorization'
        if 'evidence_path' in row.get('last_observation', {}):
            row['last_observation']['evidence_path'] = row['last_observation']['evidence_path'].replace('\\', '/')
    incoming['tracker.json'] = json_bytes(tracker)
    incoming['grants.json'] = json_bytes({'schema_version': SCHEMA, 'grants': []})
    return incoming


def plan(store, archive=None, operation='restore'):
    store.check_maintenance()
    with store.lock(maintenance=True):
        current = collect(store)
        if operation == 'migrate':
            if not current:
                raise ValueError('No career data to migrate; initialize an empty workspace instead')
            schema = json.loads(current['profile.json'].decode('utf-8-sig'))['schema_version']
            if schema == SCHEMA:
                return {'status': 'up-to-date', 'data_schema': SCHEMA}
            archive = _backup(store, 'before-migration')['path']
        manifest, incoming = read_archive(archive)
        stamp = now()
        incoming = upgrade(incoming, manifest['workspace_id'], stamp)
        if nonempty(current):
            identity = json.loads(current.get('workspace.json', b'{}')).get('id')
            if operation == 'restore' and identity != manifest['workspace_id']:
                raise ValueError('This populated workspace has a different identity. Restore into a separate empty workspace; never mix people')
        incoming = combine(current, incoming, operation)
        validate_data({k: v for k, v in incoming.items() if k != 'grants.json'}, SCHEMA)
        current_all = dict(current)
        grants = store.root / 'grants.json'
        if grants.is_file():
            current_all['grants.json'] = grants.read_bytes()
        changed = sorted(name for name, data in incoming.items() if current_all.get(name) != data)
        removed = sorted(set(current_all) - set(incoming))
        value = {'schema_version': SCHEMA, 'id': 'plan-' + uuid.uuid4().hex, 'operation': operation,
                 'created_at': stamp, 'source_path': str(Path(archive).resolve()), 'source_sha256': digest(Path(archive).read_bytes()),
                 'source_schema': manifest['data_schema'], 'target_schema': SCHEMA,
                 'current_fingerprint': fingerprint(store, current), 'incoming_fingerprint': digest({k: digest(v) for k, v in incoming.items()}),
                 'changes': changed, 'removed': removed, 'overwrites_existing_data': nonempty(current),
                 'notice': 'Review these paths/counts. Credentials/browser files stay outside this operation; grants are cleared and uncertain/submitted attempts are preserved.'}
        atomic(store.root / f"maintenance/plans/{value['id']}.json", value)
        return value


def _incoming(store, proposal, current):
    source = Path(proposal['source_path'])
    if digest(source.read_bytes()) != proposal['source_sha256'] or fingerprint(store, current) != proposal['current_fingerprint']:
        raise ValueError('Backup or current data changed after the plan; create and review a new plan')
    manifest, files = read_archive(source)
    files = combine(current, upgrade(files, manifest['workspace_id'], proposal['created_at']), proposal['operation'])
    if digest({k: digest(v) for k, v in files.items()}) != proposal['incoming_fingerprint']:
        raise ValueError('Plan contents differ; create a new plan')
    return files


def apply(store, plan_id, confirmation, expected_operation=None):
    if not isinstance(confirmation, str) or not confirmation.strip():
        raise ValueError('Record the actual user request/confirmation for this reviewed local data plan')
    store.check_maintenance()
    with store.lock(maintenance=True):
        proposal = load(store.root / f'maintenance/plans/{slug(plan_id)}.json')
        if proposal['id'] != plan_id or proposal['operation'] not in {'restore', 'migrate'}:
            raise ValueError('Invalid maintenance plan')
        if expected_operation and expected_operation != proposal['operation']:
            raise ValueError('Plan operation does not match the requested command')
        current = collect(store)
        incoming = _incoming(store, proposal, current)
        current_all = dict(current)
        grants = store.root / 'grants.json'
        if grants.is_file():
            current_all['grants.json'] = grants.read_bytes()
        expected_changes = sorted(name for name, data in incoming.items() if current_all.get(name) != data)
        expected_removed = sorted(set(current_all) - set(incoming))
        if proposal['changes'] != expected_changes or proposal['removed'] != expected_removed:
            raise ValueError('Plan paths changed; create and review a new plan')
        prechange = _backup(store, 'before-' + proposal['operation']) if current else None
        stage = store.root / f'maintenance/stages/{plan_id}'
        if stage.exists():
            raise ValueError('This plan was already staged; review recovery/history before retrying')
        for name in proposal['changes']:
            atomic_bytes(inside(store.root, stage / 'incoming' / name), incoming[name])
        names = proposal['changes'] + proposal['removed']
        event = {'schema_version': SCHEMA, 'id': 'event-' + uuid.uuid4().hex, 'created_at': now(),
                 'operation': proposal['operation'], 'path': 'career-data', 'status': 'applied', 'plan_id': plan_id,
                 'before_sha256': proposal['current_fingerprint'], 'after_sha256': proposal['incoming_fingerprint']}
        event_name = f"history/events/{event['id']}.json"
        incoming[event_name] = json_bytes(event)
        names = [*names, event_name]
        state = {'schema_version': SCHEMA, 'id': plan_id, 'operation': proposal['operation'], 'status': 'applying',
                 'created_at': now(), 'confirmation': confirmation, 'prechange_backup': prechange,
                 'stage': stage.relative_to(store.root).as_posix(), 'files': []}
        for name in names:
            target = inside(store.root, store.root / name)
            old = target.read_bytes() if target.is_file() else None
            if old is not None:
                atomic_bytes(inside(store.root, stage / 'undo' / name), old)
            state['files'].append({'path': name, 'before': digest(old) if old is not None else None,
                                   'after': digest(incoming[name]) if name in incoming else None})
        journal = store.root / 'maintenance/operation.json'
        atomic(journal, state)
        try:
            for entry in state['files']:
                target = inside(store.root, store.root / entry['path'])
                if entry['after'] is None:
                    target.unlink(missing_ok=True)
                else:
                    atomic_bytes(target, incoming[entry['path']])
            restored = collect(store)
            validate_data(restored, SCHEMA)
            state['status'] = 'complete'
            state['completed_at'] = now()
            atomic(journal, state)
        except Exception:
            rollback(store, state)
            raise
        return {'status': 'complete', 'operation': proposal['operation'], 'data_schema': SCHEMA,
                'files_changed': len(state['files']), 'prechange_backup': prechange,
                'notice': 'Knowledge restored/migrated. No active submission authorization was inherited. Recheck role skill installation and refresh stale assessments/packages.'}


def rollback(store, state):
    if state['stage'] != f"maintenance/stages/{slug(state['id'])}":
        raise ValueError('Unsafe recovery stage; preserve all data')
    stage = inside(store.root, store.root / state['stage'])
    state['status'] = 'rolling-back'
    atomic(store.root / 'maintenance/operation.json', state)
    # Verify every undo object and current file before modifying any of them.
    for entry in state['files']:
        if not (valid_member(entry['path']) or entry['path'] == 'grants.json'):
            raise ValueError('Unsafe recovery path; preserve all data')
        target = inside(store.root, store.root / entry['path'])
        actual = digest(target.read_bytes()) if target.is_file() else None
        if actual not in {entry['before'], entry['after']}:
            raise ValueError('Files changed outside the interrupted operation; preserve data and review the prechange backup')
        if entry['before'] is not None and digest(inside(store.root, stage / 'undo' / entry['path']).read_bytes()) != entry['before']:
            raise ValueError('Recovery snapshot hash differs; preserve data for manual review')
    for entry in reversed(state['files']):
        target = inside(store.root, store.root / entry['path'])
        if not (valid_member(entry['path']) or entry['path'] == 'grants.json'):
            raise ValueError('Unsafe recovery path; preserve all data')
        undo = stage / 'undo' / entry['path']
        if entry['before'] is None:
            target.unlink(missing_ok=True)
        else:
            content = inside(store.root, undo).read_bytes()
            if digest(content) != entry['before']:
                raise ValueError('Recovery snapshot hash differs; preserve data for manual review')
            atomic_bytes(target, content)
    state['status'] = 'rolled-back'
    state['completed_at'] = now()
    atomic(store.root / 'maintenance/operation.json', state)
    return {'status': 'rolled-back', 'plan_id': state['id'], 'notice': 'Previous files restored. Review a new plan before retrying.'}


def recover(store):
    with store.lock(maintenance=True):
        journal = store.root / 'maintenance/operation.json'
        if not journal.is_file() or load(journal).get('status') not in {'applying', 'rolling-back'}:
            return {'status': 'no-pending-operation'}
        return rollback(store, load(journal))
