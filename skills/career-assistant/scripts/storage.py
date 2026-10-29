"""Portable, local-only storage. No external service credentials are accepted."""
from __future__ import annotations
import contextlib
import hashlib
import json
import os
import re
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

VERSION = '0.1.11'
SCHEMA = 2
PRIVATE = '.career-assistant'
SECRET_KEYS = {'password', 'passwd', 'access_token', 'refresh_token', 'api_key', 'client_secret', 'cookies', 'otp', 'sin', 'ssn', 'passport_number'}
PREFERENCE_KEYS = {'submission_policy', 'include_projects', 'targets', 'locations', 'work_authorization', 'compensation', 'work_modes', 'commute', 'contracts', 'travel', 'start_date', 'exclusions'}


def validate_preferences(value):
    """Validate storage shapes without supplying a user's goals or unknown answers."""
    if not isinstance(value, dict) or not PREFERENCE_KEYS <= value.keys():
        raise ValueError('Preferences need all standard fields; preserve the file and correct missing fields with preferences-update')
    def invalid(field, shape):
        raise ValueError(f'preferences.{field} must be {shape}; correct it with preferences-update. Unknown lists use [], objects use {{}} and optional answers use null.')
    for field in ['targets', 'locations', 'work_authorization', 'work_modes', 'contracts', 'exclusions']:
        if not isinstance(value[field], list):
            invalid(field, 'a list')
    for field in ['locations', 'work_modes', 'contracts', 'exclusions']:
        if any(not isinstance(item, str) or not item.strip() for item in value[field]):
            invalid(field, 'a list of nonempty strings')
    for target in value['targets']:
        if isinstance(target, str) and target.strip():
            continue
        if not isinstance(target, dict) or not any(isinstance(target.get(k), str) and target[k].strip() for k in ['id', 'title']):
            invalid('targets', 'nonempty strings or objects with an id or title')
        if 'id' in target:
            slug(target['id'])
        if 'title' in target and (not isinstance(target['title'], str) or not target['title'].strip()):
            invalid('targets', 'objects with a nonempty title when supplied')
        if 'priority' in target and (type(target['priority']) is not int or target['priority'] < 1):
            invalid('targets', 'objects with a positive integer priority when supplied')
    if any(not (isinstance(item, str) and item.strip() or isinstance(item, dict) and item) for item in value['work_authorization']):
        invalid('work_authorization', 'nonempty strings or structured objects')
    if not isinstance(value['compensation'], dict):
        invalid('compensation', 'an object')
    if value['submission_policy'] is not None and value['submission_policy'] not in ('per-application', 'per-batch'):
        invalid('submission_policy', 'per-application, per-batch or null')
    if type(value['include_projects']) is not bool:
        invalid('include_projects', 'a user-chosen boolean')
    if value['start_date'] is not None and (not isinstance(value['start_date'], str) or not value['start_date'].strip()):
        invalid('start_date', 'a nonempty string or null')
    for field in ['commute', 'travel']:
        answer = value[field]
        if answer is not None and not isinstance(answer, (str, dict, int, float)):
            invalid(field, 'a description, structured object, number or null')


def replace_file(source, destination):
    """Retry only bounded Windows sharing/access conflicts; preserve other denials."""
    delays = (0.02, 0.05, 0.1, 0.2, 0.4)
    for attempt in range(len(delays) + 1):
        try:
            os.replace(source, destination)
            return
        except OSError as exc:
            if getattr(exc, 'winerror', None) not in {5, 32, 33} or attempt == len(delays):
                raise
            time.sleep(delays[attempt])

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(data):
    return hashlib.sha256(data if isinstance(data, bytes) else json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        replace_file(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        replace_file(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        replace_file(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

def slug(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', value):
        raise ValueError('ID must be 1-64 lowercase ASCII letters/digits/hyphens')
    return value

def no_secrets(value):
    if isinstance(value, dict):
        for k, v in value.items():
            if k.lower() in SECRET_KEYS:
                raise ValueError(f'Do not store sensitive credential/identity field: {k}')
            no_secrets(v)
    elif isinstance(value, list):
        for v in value:
            no_secrets(v)

def inside(root, path):
    path = Path(path).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError('Path escapes the selected workspace data directory')
    return path

class Store:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.root = self.workspace / PRIVATE
        self._maintenance = False

    def check_maintenance(self):
        operation = self.root / 'maintenance/operation.json'
        if not self._maintenance and operation.is_file() and load(operation).get('status') in {'applying', 'rolling-back'}:
            raise ValueError('An interrupted data operation needs maintenance-recover before reading or changing career data. Preserve .write.lock until no writer is running.')

    @contextlib.contextmanager
    def lock(self, maintenance=False):
        if not maintenance:
            self.check_maintenance()
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root / '.write.lock'
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise ValueError('Another writer or an interrupted run holds .write.lock. Verify no process is writing before manually removing it.') from None
        try:
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            previous = self._maintenance
            self._maintenance = maintenance
            try:
                yield
            finally:
                self._maintenance = previous
        finally:
            lock.unlink(missing_ok=True)

    def read(self, name, *, allow_invalid_preferences=False):
        self.check_maintenance()
        if str(name).replace('\\', '/') == 'setup/environment.json':
            raise ValueError('Dependency setup state is operational metadata. Read it through career.py doctor/setup or environment.settings; it is not an old career-data schema and must not trigger migration.')
        value = load(inside(self.root, self.root / name))
        if value.get('schema_version') != SCHEMA:
            if value.get('schema_version') == 1:
                raise ValueError('Data schema 1 needs explicit migration to schema 2. Preserve data; use migrate-plan, then migrate after reviewing its plan.')
            raise ValueError('Unsupported schema version; preserve data and migrate explicitly')
        if name == 'preferences.json' and not allow_invalid_preferences:
            validate_preferences(value)
        return value

    def write(self, name, value, audit=True):
        no_secrets(value)
        if name == 'preferences.json':
            validate_preferences(value)
        self.check_maintenance()
        data = json_bytes(value)
        target = inside(self.root, self.root / name)
        if audit:
            from maintenance import record_write
            record_write(self, name, data, lambda: atomic_bytes(target, data))
        else:
            atomic_bytes(target, data)

    def write_text(self, name, text):
        self.check_maintenance()
        from maintenance import record_write
        target = inside(self.root, self.root / name)
        record_write(self, name, text.encode('utf-8'), lambda: atomic_text(target, text))

    def initialize(self):
        self.check_maintenance()
        self.workspace.mkdir(parents=True, exist_ok=True)
        # Also protect users who install the skill into an existing unrelated repo.
        ignore = self.workspace / '.gitignore'
        rules = ['/.career-assistant/', '/.agents/skills/career-resume-*/', '/.claude/skills/career-resume-*/']
        existing = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
        missing = [r for r in rules if r not in existing.splitlines()]
        if missing:
            ignore.write_text(existing.rstrip('\n') + '\n' + '\n'.join(missing) + '\n', encoding='utf-8')
        defaults = {
            'workspace.json': {'schema_version': SCHEMA, 'id': uuid.uuid4().hex, 'created_at': now()},
            'profile.json': {'schema_version': SCHEMA, 'revision': 0, 'facts': {}, 'updated_at': now()},
            'preferences.json': {'schema_version': SCHEMA, 'revision': 0, 'updated_at': now(), 'submission_policy': None, 'include_projects': False, 'targets': [], 'locations': [], 'work_authorization': [], 'compensation': {}, 'work_modes': [], 'commute': None, 'contracts': [], 'travel': None, 'start_date': None, 'exclusions': []},
            'onboarding.json': {'schema_version': SCHEMA, 'completed': [], 'skipped_optional': [], 'notes': {}},
            'sources.json': {'schema_version': SCHEMA, 'sources': {}},
            'tracker.json': {'schema_version': SCHEMA, 'authority': 'local', 'records': [], 'record_count': 0},
            'grants.json': {'schema_version': SCHEMA, 'grants': []},
        }
        with self.lock():
            # Preflight every existing core file before creating any new defaults.
            for name in defaults:
                if (self.root / name).exists():
                    self.read(name)
            for name, value in defaults.items():
                if not (self.root / name).exists():
                    self.write(name, value, audit=False)
                else:
                    self.read(name)
        return self.status()

    def status(self):
        from roles import selected_issues
        from jobs import trial_ready
        steps = ['environment', 'materials', 'facts', 'preferences', 'roles', 'automation', 'trial']
        state = self.read('onboarding.json')
        role_issues = selected_issues(self)
        invalid = []
        if 'roles' in state['completed'] and role_issues:
            invalid = [s for s in ['roles', 'automation', 'trial'] if s in state['completed']]
        elif 'trial' in state['completed'] and not trial_ready(self):
            invalid = ['trial']
        if invalid:
            state['completed'] = [s for s in state['completed'] if s not in invalid]
            state['invalidated_steps'] = invalid
        profile = self.read('profile.json')
        tracker = self.read('tracker.json')
        counts = {status: sum(row['status'] == status for row in tracker['records']) for status in ['Pending', 'Needs user', 'Blocked', 'Submitted']}
        return {'version': VERSION, 'workspace': str(self.workspace), 'profile_revision': profile['revision'], 'fact_count': len(profile['facts']), 'next_step': next((s for s in steps if s not in state['completed']), 'complete'), 'progress': state, 'role_issues': role_issues, 'applications': {'total': len(tracker['records']), 'counts': counts, 'next_actions': [{'id': row['id'], 'status': row['status'], 'next_action': row['next_action']} for row in tracker['records'] if row['status'] != 'Submitted']}}
