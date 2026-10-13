"""Fictional knowledge backup/restore/migration with no credential contents exposed."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import warnings
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED
from fixtures import make_workspace, assessment, stub_ready_package, authorized_preparation
from storage import Store, SCHEMA, atomic, digest, json_bytes
import profiles, jobs, maintenance


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = make_workspace(self.root / 'fictional-person')
        jobs.assess(self.store, assessment(self.store))

    def change_name(self):
        fact = copy.deepcopy(self.store.read('profile.json')['facts']['name'])
        fact['text'] = 'Fictional corrected spelling'
        profiles.update_profile(self.store, {'facts': {'name': fact}, 'change_confirmation': 'Fictional owner corrects the spelling'})

    def legacy(self):
        for path in [*(self.store.root.glob('*.json')), *(self.store.root.glob('roles/*.json')), *(self.store.root.glob('jobs/*.json')), *(self.store.root.glob('packages/*/validation.json')), *(self.store.root.glob('packages/*/match-report.json'))]:
            value = json.loads(path.read_text(encoding='utf-8'))
            value['schema_version'] = 1
            if path.name == 'preferences.json':
                value.pop('revision', None); value.pop('updated_at', None)
            atomic(path, value)
        (self.store.root / 'workspace.json').unlink()

    def begin(self, job_id='demo-job'):
        stub_ready_package(self.store, job_id)
        app, grant, review = authorized_preparation(self.store, job_id)
        jobs.prepare(self.store, app['id'], review)
        intent = jobs.begin_submit(self.store, app['id'])
        return app, intent

    def confirm(self, app, intent):
        path = self.store.root / 'evidence' / (app['id'] + '.txt'); path.parent.mkdir(exist_ok=True)
        path.write_text('Observed fictional receipt', encoding='utf-8')
        jobs.outcome(self.store, app['id'], {'attempt_id': intent['attempt_id'], 'result': 'confirmed', 'detail': 'Fictional test observation', 'observed_confirmation': True,
            'confirmation_text': 'Received', 'confirmation_url': 'https://example.invalid/history', 'evidence_path': path.relative_to(self.store.root).as_posix(), 'next_action': 'Wait'})

    def test_backup_never_reads_credentials_or_browser_and_excludes_grants_host_skills(self):
        for name in ['credentials/workday/accounts.txt', 'browser/storage-state.json']:
            path = self.store.root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('FICTIONAL PRIVATE SENTINEL')
        original = Path.read_bytes
        def checked(path):
            if any(part in {'credentials', 'browser'} for part in path.parts):
                raise AssertionError('Excluded file read')
            return original(path)
        with patch.object(Path, 'read_bytes', checked):
            result = maintenance.backup(self.store)
        with ZipFile(result['path']) as archive:
            self.assertNotIn('grants.json', archive.namelist())
            self.assertFalse(any('credentials' in n or 'browser' in n or '.agents' in n for n in archive.namelist()))
        self.assertTrue(maintenance.verify_backup(result['path'])['valid'])

    def test_history_has_old_and_new_snapshots_but_cli_summary_omits_values(self):
        before = self.store.read('profile.json'); self.change_name()
        summary = maintenance.history(self.store, path='profile.json')
        self.assertNotIn('Riley Stone', json.dumps(summary)); self.assertNotIn('Fictional corrected spelling', json.dumps(summary))
        event = json.loads((self.store.root / 'history/events' / (summary['entries'][0]['id'] + '.json')).read_text())
        old = json.loads((self.store.root / event['before_object']).read_bytes())
        new = json.loads((self.store.root / event['after_object']).read_bytes())
        self.assertEqual(before, old)
        self.assertEqual('Fictional corrected spelling', new['facts']['name']['text'])

    def test_preferences_have_protected_revision_metadata_and_noop_is_unchanged(self):
        before = self.store.read('preferences.json')
        profiles.update_preferences(self.store, {'locations': before['locations']})
        self.assertEqual(before, self.store.read('preferences.json'))
        profiles.update_preferences(self.store, {'locations': ['Fictional new city']})
        self.assertEqual(before['revision'] + 1, self.store.read('preferences.json')['revision'])
        with self.assertRaises(ValueError): profiles.update_preferences(self.store, {'revision': 99})

    def test_restore_to_new_workspace_preserves_facts_routes_and_has_no_authorization(self):
        saved = maintenance.backup(self.store)
        target = Store(self.root / 'restored-person')
        proposal = maintenance.plan(target, saved['path'])
        result = maintenance.apply(target, proposal['id'], 'Fictional owner requests this backup be restored here')
        self.assertEqual('complete', result['status'])
        self.assertEqual(self.store.read('profile.json'), target.read('profile.json'))
        self.assertEqual((self.store.root / 'routes/operations.md').read_bytes(), (target.root / 'routes/operations.md').read_bytes())
        self.assertEqual([], target.read('grants.json')['grants'])
        self.assertTrue(target.status()['role_issues'])
        profiles.role_retry(target, 'operations')
        self.assertEqual([], target.status()['role_issues'])

    def test_populated_different_workspace_identity_is_not_mixed(self):
        saved = maintenance.backup(self.store)
        other = make_workspace(self.root / 'other-person', 'software'); before = other.read('profile.json')
        with self.assertRaisesRegex(ValueError, 'different identity'):
            maintenance.plan(other, saved['path'])
        self.assertEqual(before, other.read('profile.json'))

    def test_old_backup_preserves_current_submitted_and_unknown_records_and_artifacts(self):
        saved = maintenance.backup(self.store)
        app, intent = self.begin(); self.confirm(app, intent)
        jobs.assess(self.store, assessment(self.store, 'other-job', 'Other Fictional Employer'))
        unknown, unknown_intent = self.begin('other-job')
        tracker = self.store.read('tracker.json'); self.change_name()
        proposal = maintenance.plan(self.store, saved['path'])
        result = maintenance.apply(self.store, proposal['id'], 'Fictional owner approves restoring older knowledge')
        self.assertTrue(Path(result['prechange_backup']['path']).is_file())
        self.assertEqual(tracker, self.store.read('tracker.json'))
        self.assertEqual([], self.store.read('grants.json')['grants'])
        self.assertTrue((self.store.root / 'packages/other-job/resume.pdf').is_file())
        self.assertEqual(1, self.store.status()['applications']['counts']['Submitted'])
        self.assertEqual(1, self.store.status()['applications']['counts']['Needs user'])
        with self.assertRaises(ValueError): jobs.begin_submit(self.store, unknown['id'])
        self.confirm(unknown, unknown_intent)
        self.assertEqual(2, self.store.status()['applications']['counts']['Submitted'])

    def test_restored_preparation_is_paused_and_requires_a_new_grant(self):
        stub_ready_package(self.store); app, _, review = authorized_preparation(self.store)
        jobs.prepare(self.store, app['id'], review)
        saved = maintenance.backup(self.store); target = Store(self.root / 'restored')
        proposal = maintenance.plan(target, saved['path']); maintenance.apply(target, proposal['id'], 'Fictional restore request')
        self.assertEqual('paused', target.read('tracker.json')['records'][0]['attempts'][-1]['outcome'])
        self.assertEqual('Needs user', target.read('tracker.json')['records'][0]['status'])
        with self.assertRaises(ValueError): jobs.begin_submit(target, app['id'])
        with self.assertRaises(ValueError): jobs.prepare(target, app['id'], review)

    def test_current_credentials_and_browser_files_are_untouched(self):
        saved = maintenance.backup(self.store); self.change_name()
        paths = []
        for name in ['credentials/workday/accounts.txt', 'browser/storage-state.json']:
            path = self.store.root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'FICTIONAL local private data'); paths.append(path)
        proposal = maintenance.plan(self.store, saved['path']); maintenance.apply(self.store, proposal['id'], 'Fictional restore request')
        for path in paths: self.assertEqual(b'FICTIONAL local private data', path.read_bytes())

    def test_changed_current_data_or_archive_rejects_stale_plan(self):
        saved = maintenance.backup(self.store); target = Store(self.root / 'new')
        proposal = maintenance.plan(target, saved['path']); target.initialize()
        with self.assertRaisesRegex(ValueError, 'changed after the plan'):
            maintenance.apply(target, proposal['id'], 'Fictional restore request')
        target2 = Store(self.root / 'another'); proposal = maintenance.plan(target2, saved['path'])
        with Path(saved['path']).open('ab') as stream: stream.write(b'CHANGED')
        with self.assertRaisesRegex(ValueError, 'changed after the plan'):
            maintenance.apply(target2, proposal['id'], 'Fictional restore request')

    def test_tampered_plan_cannot_remove_a_credential_file(self):
        saved = maintenance.backup(self.store); proposal = maintenance.plan(self.store, saved['path'])
        path = self.store.root / f"maintenance/plans/{proposal['id']}.json"
        data = json.loads(path.read_bytes()); data['removed'].append('credentials/workday/accounts.txt'); atomic(path, data)
        with self.assertRaisesRegex(ValueError, 'Plan paths changed'):
            maintenance.apply(self.store, proposal['id'], 'Fictional restore request')

    def test_zip_traversal_extra_credentials_duplicates_and_tampering_are_rejected(self):
        saved = maintenance.backup(self.store)
        for attack in ['../outside.txt', 'credentials/workday/accounts.txt', 'profile.json', 'PROFILE.JSON']:
            bad = self.root / ('bad-' + attack.replace('/', '-').replace('.', '-') + '.zip')
            with ZipFile(saved['path']) as original, ZipFile(bad, 'w', ZIP_DEFLATED) as new:
                for info in original.infolist(): new.writestr(info, original.read(info.filename))
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    new.writestr(attack, b'UNTRUSTED FICTIONAL DATA')
            with self.subTest(attack=attack), self.assertRaises(ValueError): maintenance.verify_backup(bad)
        bad = self.root / 'tampered.zip'
        with ZipFile(saved['path']) as original, ZipFile(bad, 'w') as new:
            for info in original.infolist(): new.writestr(info, b'{}' if info.filename == 'profile.json' else original.read(info.filename))
        with self.assertRaisesRegex(ValueError, 'hash differs'): maintenance.verify_backup(bad)

    def test_write_failure_rolls_back_all_changed_files(self):
        saved = maintenance.backup(self.store); self.change_name()
        profiles.update_preferences(self.store, {'locations': ['Fictional changed city']})
        before = maintenance.collect(self.store); proposal = maintenance.plan(self.store, saved['path'])
        real = maintenance.atomic_bytes; failed = False
        def fail_once(path, data):
            nonlocal failed
            if Path(path) == self.store.root / 'preferences.json' and not failed:
                failed = True; raise PermissionError('Fictional write denial')
            return real(path, data)
        with patch.object(maintenance, 'atomic_bytes', fail_once), self.assertRaises(PermissionError):
            maintenance.apply(self.store, proposal['id'], 'Fictional restore request')
        self.assertEqual(before, maintenance.collect(self.store))
        self.assertEqual('rolled-back', json.loads((self.store.root / 'maintenance/operation.json').read_bytes())['status'])

    def test_interruption_blocks_normal_work_until_recovery(self):
        saved = maintenance.backup(self.store); self.change_name()
        before = maintenance.collect(self.store); proposal = maintenance.plan(self.store, saved['path'])
        real = maintenance.atomic_bytes
        def interrupt(path, data):
            if Path(path) == self.store.root / 'profile.json': raise SystemExit('Simulated process interruption')
            return real(path, data)
        with patch.object(maintenance, 'atomic_bytes', interrupt), self.assertRaises(SystemExit):
            maintenance.apply(self.store, proposal['id'], 'Fictional restore request')
        reopened = Store(self.store.workspace)
        with self.assertRaisesRegex(ValueError, 'maintenance-recover'): reopened.status()
        with self.assertRaises(ValueError): maintenance.backup(reopened)
        self.assertEqual('rolled-back', maintenance.recover(reopened)['status'])
        self.assertEqual(before, maintenance.collect(reopened))

    def test_schema1_explicit_migration_preserves_facts_sources_and_uncertain_attempts(self):
        app, intent = self.begin(); self.legacy()
        facts = json.loads((self.store.root / 'profile.json').read_bytes())['facts']
        sources = json.loads((self.store.root / 'sources.json').read_bytes())['sources']
        before = (self.store.root / 'profile.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'migration'): self.store.initialize()
        self.assertEqual(before, (self.store.root / 'profile.json').read_bytes())
        self.assertFalse((self.store.root / 'workspace.json').exists())
        proposal = maintenance.plan(self.store, operation='migrate')
        self.assertEqual(1, proposal['source_schema'])
        maintenance.apply(self.store, proposal['id'], 'Fictional owner requests the format upgrade')
        self.assertEqual(SCHEMA, self.store.read('profile.json')['schema_version'])
        self.assertEqual(facts, self.store.read('profile.json')['facts'])
        self.assertEqual(sources, self.store.read('sources.json')['sources'])
        self.assertEqual('unknown', self.store.read('tracker.json')['records'][0]['attempts'][-1]['outcome'])
        self.assertEqual([], self.store.read('grants.json')['grants'])
        with self.assertRaises(ValueError): jobs.fresh(self.store, self.store.read('jobs/demo-job.json'))
        self.confirm(app, intent)
        self.assertEqual('up-to-date', maintenance.plan(self.store, operation='migrate')['status'])

    def test_recovery_preserves_external_edits_without_partial_rollback(self):
        saved = maintenance.backup(self.store); self.change_name()
        proposal = maintenance.plan(self.store, saved['path'])
        real = maintenance.atomic_bytes
        def interrupt(path, data):
            if Path(path) == self.store.root / 'profile.json': raise SystemExit('Fictional interruption')
            return real(path, data)
        with patch.object(maintenance, 'atomic_bytes', interrupt), self.assertRaises(SystemExit):
            maintenance.apply(self.store, proposal['id'], 'Fictional restore request')
        path = self.store.root / 'profile.json'
        edited = json.loads(path.read_bytes()); edited['facts']['name']['text'] = 'Fictional manual edit after interruption'
        atomic(path, edited)
        before_recovery = maintenance.collect(self.store)
        with self.assertRaisesRegex(ValueError, 'changed outside'):
            maintenance.recover(Store(self.store.workspace))
        self.assertEqual(before_recovery, maintenance.collect(self.store))

    def test_migrate_command_cannot_apply_a_restore_plan(self):
        saved = maintenance.backup(self.store)
        target = Store(self.root / 'new'); proposal = maintenance.plan(target, saved['path'])
        with self.assertRaisesRegex(ValueError, 'does not match'):
            maintenance.apply(target, proposal['id'], 'Fictional upgrade request', expected_operation='migrate')
        self.assertFalse((target.root / 'profile.json').exists())

    def test_unknown_schema_is_not_migrated_or_reset(self):
        path = self.store.root / 'profile.json'; data = self.store.read('profile.json'); data['schema_version'] = 99; atomic(path, data); before = path.read_bytes()
        with self.assertRaises(ValueError): maintenance.plan(self.store, operation='migrate')
        self.assertEqual(before, path.read_bytes())

    def test_cli_backup_verify_history_and_restore_use_metadata_only(self):
        helper = Path(profiles.__file__).with_name('career.py')
        def cli(workspace, *args):
            result = subprocess.run([sys.executable, str(helper), '--workspace', str(workspace), *args], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn('Riley Stone', result.stdout)
            return json.loads(result.stdout)
        saved = cli(self.store.workspace, 'backup')
        self.assertTrue(cli(self.store.workspace, 'backup-verify', saved['path'])['valid'])
        self.assertTrue(cli(self.store.workspace, 'history')['values_omitted'])
        target = self.root / 'cli-restored'; proposal = cli(target, 'restore-plan', saved['path'])
        self.assertEqual('complete', cli(target, 'restore', '--plan', proposal['id'], '--confirmation', 'Fictional restore request')['status'])


if __name__ == '__main__': unittest.main()
