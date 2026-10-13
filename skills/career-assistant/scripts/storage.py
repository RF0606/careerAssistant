"""Portable, local-only storage. No external service credentials are accepted."""
from __future__ import annotations
import contextlib
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

VERSION = '0.1.6'
SCHEMA = 1
PRIVATE = '.career-assistant'
SECRET_KEYS = {'password', 'passwd', 'access_token', 'refresh_token', 'api_key', 'client_secret', 'cookies', 'otp', 'sin', 'ssn', 'passport_number'}

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
        os.replace(temp, path)
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
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

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

    @contextlib.contextmanager
    def lock(self):
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root / '.write.lock'
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise ValueError('Another writer or an interrupted run holds .write.lock. Verify no process is writing before manually removing it.') from None
        try:
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            yield
        finally:
            lock.unlink(missing_ok=True)

    def read(self, name):
        value = load(inside(self.root, self.root / name))
        if value.get('schema_version') != SCHEMA:
            raise ValueError('Unsupported schema version; preserve data and migrate explicitly')
        return value

    def write(self, name, value):
        no_secrets(value)
        atomic(inside(self.root, self.root / name), value)

    def initialize(self):
        self.workspace.mkdir(parents=True, exist_ok=True)
        # Also protect users who install the skill into an existing unrelated repo.
        ignore = self.workspace / '.gitignore'
        rules = ['/.career-assistant/', '/.agents/skills/career-resume-*/', '/.claude/skills/career-resume-*/']
        existing = ignore.read_text(encoding='utf-8') if ignore.exists() else ''
        missing = [r for r in rules if r not in existing.splitlines()]
        if missing:
            ignore.write_text(existing.rstrip('\n') + '\n' + '\n'.join(missing) + '\n', encoding='utf-8')
        defaults = {
            'profile.json': {'schema_version': SCHEMA, 'revision': 0, 'facts': {}, 'updated_at': now()},
            'preferences.json': {'schema_version': SCHEMA, 'submission_policy': None, 'include_projects': False, 'targets': [], 'locations': [], 'work_authorization': [], 'compensation': {}, 'work_modes': [], 'commute': None, 'contracts': [], 'travel': None, 'start_date': None, 'exclusions': []},
            'onboarding.json': {'schema_version': SCHEMA, 'completed': [], 'skipped_optional': [], 'notes': {}},
            'sources.json': {'schema_version': SCHEMA, 'sources': {}},
            'tracker.json': {'schema_version': SCHEMA, 'authority': 'local', 'records': [], 'record_count': 0},
            'grants.json': {'schema_version': SCHEMA, 'grants': []},
        }
        with self.lock():
            for name, value in defaults.items():
                if not (self.root / name).exists():
                    self.write(name, value)
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
