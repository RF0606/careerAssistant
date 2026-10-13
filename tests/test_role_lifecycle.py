"""Fictional role installation/recovery and artifact freshness regressions."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fixtures import make_workspace, assessment, draft, stub_ready_package, authorized_preparation
from storage import Store, digest
import profiles
import jobs


class RoleLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = make_workspace(Path(self.temp.name) / 'fictional-user')
        jobs.assess(self.store, assessment(self.store))

    def complete_trial_stub(self):
        # Guard tests use a labelled stub, never PDF acceptance evidence.
        stub_ready_package(self.store)
        for step in ['environment', 'materials', 'facts', 'preferences', 'roles', 'automation', 'trial']:
            profiles.checkpoint(self.store, step)

    def block_folder(self, host):
        folder = self.store.workspace / host / 'skills/career-resume-operations'
        (folder / 'SKILL.md').unlink()
        folder.rmdir()
        folder.write_text('FICTIONAL path conflict for regression testing', encoding='utf-8')
        return folder

    def test_partial_install_on_either_host_cannot_complete_and_retries_saved_state(self):
        self.complete_trial_stub()
        before = {name: self.store.read(name) for name in ['profile.json', 'preferences.json', 'sources.json']}
        route = self.store.root / 'routes/operations.md'
        guide = route.read_bytes()
        old_assessment = self.store.read('jobs/demo-job.json')
        for host, folder_name in [('codex', '.agents'), ('claude', '.claude')]:
            with self.subTest(host=host):
                blocked = self.block_folder(folder_name)
                with self.assertRaisesRegex(ValueError, 'role-retry operations'):
                    profiles.role_create(self.store, self.store.read('roles/operations.json'), ['codex', 'claude'])
                generation = self.store.read('roles/operations.json')['generation']
                self.assertEqual('pending', generation['status'])
                self.assertEqual([host], list(generation['failures']))
                self.assertEqual('FileExistsError', generation['failures'][host]['reason'])
                for step in ['roles', 'automation', 'trial']:
                    with self.assertRaisesRegex(ValueError, 'personal skills'):
                        profiles.checkpoint(self.store, step)
                reopened = Store(self.store.workspace)
                status = reopened.initialize()
                self.assertEqual('roles', status['next_step'])
                self.assertNotIn('roles', status['progress']['completed'])
                self.assertTrue(status['role_issues'])
                blocked.unlink()
                result = profiles.role_retry(reopened, 'operations')
                self.assertEqual('ready', result['generation']['status'])
                self.assertEqual(['codex', 'claude'], result['generation']['hosts'])
                for info in result['generation']['skills'].values():
                    self.assertEqual(info['sha256'], digest((reopened.workspace / info['path']).read_bytes()))
                self.assertEqual('complete', reopened.status()['next_step'])
                self.assertEqual(guide, route.read_bytes())
                jobs.fresh(reopened, old_assessment)
                for name, value in before.items():
                    self.assertEqual(value, reopened.read(name))

    def test_permission_failure_records_pending_and_preserves_successful_host(self):
        path = self.store.workspace / '.agents/skills/career-resume-operations/SKILL.md'
        path.unlink()
        other = self.store.workspace / '.claude/skills/career-resume-operations/SKILL.md'
        before = other.stat().st_mtime_ns
        with patch.object(profiles, 'atomic_text', side_effect=PermissionError('Fictional write denial')):
            with self.assertRaisesRegex(ValueError, 'PermissionError'):
                profiles.role_retry(self.store, 'operations')
        self.assertEqual('pending', self.store.read('roles/operations.json')['generation']['status'])
        self.assertEqual(before, other.stat().st_mtime_ns)
        profiles.role_retry(self.store, 'operations')
        self.assertTrue(path.is_file())

    def test_interrupted_pending_record_resumes_without_recreating_route(self):
        self.complete_trial_stub()
        role = self.store.read('roles/operations.json')
        role['generation']['status'] = 'pending'
        self.store.write('roles/operations.json', role)
        guide = self.store.root / role['route_path']
        before = guide.stat().st_mtime_ns
        self.assertEqual('roles', Store(self.store.workspace).initialize()['next_step'])
        profiles.role_retry(self.store, 'operations')
        self.assertEqual(before, guide.stat().st_mtime_ns)
        self.assertEqual('complete', self.store.status()['next_step'])

    def test_missing_or_changed_installed_skill_reopens_completed_role_step(self):
        self.complete_trial_stub()
        path = self.store.workspace / '.agents/skills/career-resume-operations/SKILL.md'
        for mutation in ['missing', 'changed']:
            with self.subTest(mutation=mutation):
                if mutation == 'missing':
                    path.unlink()
                else:
                    path.write_text('Incomplete fictional skill', encoding='utf-8')
                self.assertEqual('roles', self.store.status()['next_step'])
                with self.assertRaisesRegex(ValueError, 'personal skills'):
                    profiles.checkpoint(self.store, 'roles')
                profiles.role_retry(self.store, 'operations')
                self.assertEqual('complete', self.store.status()['next_step'])

    def test_legacy_role_requires_refresh_without_losing_profile(self):
        self.complete_trial_stub()
        profile = self.store.read('profile.json')
        role = self.store.read('roles/operations.json')
        role.pop('generation')
        self.store.write('roles/operations.json', role)
        self.assertEqual('roles', self.store.initialize()['next_step'])
        with self.assertRaisesRegex(ValueError, 'Legacy role'):
            profiles.role_retry(self.store, 'operations')
        profiles.role_create(self.store, role, ['codex'])
        self.assertEqual(profile, self.store.read('profile.json'))
        self.assertEqual('complete', self.store.status()['next_step'])

    def test_retry_does_not_overwrite_changed_private_guide(self):
        route = self.store.root / 'routes/operations.md'
        route.write_text('Fictional user edited writing priorities', encoding='utf-8')
        before = route.read_bytes()
        with self.assertRaisesRegex(ValueError, 'route changed'):
            profiles.role_retry(self.store, 'operations')
        self.assertEqual(before, route.read_bytes())

    def test_noop_regeneration_or_host_repair_keeps_context_fresh(self):
        self.complete_trial_stub()
        previous = self.store.read('roles/operations.json')['created_at']
        profiles.role_create(self.store, self.store.read('roles/operations.json'), ['codex'])
        self.assertNotEqual(previous, self.store.read('roles/operations.json')['created_at'])
        profiles.role_retry(self.store, 'operations')
        jobs.fresh(self.store, self.store.read('jobs/demo-job.json'))
        self.assertEqual('complete', self.store.status()['next_step'])

    def test_each_role_writing_field_invalidates_assessment(self):
        original = self.store.read('roles/operations.json')
        source = self.store.root / 'fictional-jd.txt'
        source.write_text('FICTIONAL JD ONLY: emphasize service delivery and capacity planning.', encoding='utf-8')
        sid = profiles.import_source(self.store, source)['source_id']
        for change in [{'title': 'Delivery Operations Manager'}, {'focus': ['Delivery coordination']},
                       {'tailoring_guidance': ['Prioritize confirmed delivery outcomes.']}, {'jd_source_ids': [sid]}]:
            with self.subTest(change=change):
                profiles.role_create(self.store, {**original, **change}, ['codex'])
                with self.assertRaisesRegex(ValueError, 'Role configuration/personal route changed'):
                    jobs.fresh(self.store, self.store.read('jobs/demo-job.json'))
                profiles.role_create(self.store, original, ['codex'])
                jobs.fresh(self.store, self.store.read('jobs/demo-job.json'))

    def test_actual_route_bytes_and_missing_route_invalidate_assessment(self):
        role = self.store.read('roles/operations.json')
        route = self.store.root / role['route_path']
        route.write_bytes(route.read_bytes() + b'\nFictional additional priority.\n')
        self.assertEqual(role['route_sha256'], self.store.read('roles/operations.json')['route_sha256'])
        with self.assertRaisesRegex(ValueError, 'route changed'):
            jobs.fresh(self.store, self.store.read('jobs/demo-job.json'))
        route.unlink()
        with self.assertRaisesRegex(ValueError, 'route is missing'):
            jobs.fresh(self.store, self.store.read('jobs/demo-job.json'))

    def test_direct_role_file_edit_invalidates_context_even_with_unchanged_route(self):
        role = self.store.read('roles/operations.json')
        role['focus'].append('Fictional updated priority')
        self.store.write('roles/operations.json', role)
        with self.assertRaisesRegex(ValueError, 'route changed'):
            jobs.fresh(self.store, self.store.read('jobs/demo-job.json'))

    def test_legacy_assessment_requires_reassessment(self):
        old = self.store.read('jobs/demo-job.json')
        old.pop('role_context_hash')
        self.store.write('jobs/demo-job.json', old)
        stub_ready_package(self.store)
        with self.assertRaisesRegex(ValueError, 'predates context tracking'):
            jobs.add_application(self.store, 'demo-job')
        jobs.assess(self.store, assessment(self.store))
        jobs.fresh(self.store, self.store.read('jobs/demo-job.json'))

    def test_context_change_blocks_every_artifact_and_preclick_reuse(self):
        import resume
        self.complete_trial_stub()
        app, _, review = authorized_preparation(self.store)
        jobs.prepare(self.store, app['id'], review)
        tracker = self.store.read('tracker.json')
        pdf = (self.store.root / 'packages/demo-job/resume.pdf').read_bytes()
        role = self.store.read('roles/operations.json')
        profiles.role_create(self.store, {**role, 'focus': ['New fictional emphasis']}, ['codex'])
        for action in [lambda: jobs.add_application(self.store, 'demo-job'),
                       lambda: resume.render(self.store, 'demo-job', draft(self.store), False),
                       lambda: resume.visual_review(self.store, 'demo-job', {'passed': True, 'reviewer': 'Test', 'notes': 'Guard only'}),
                       lambda: jobs.prepare(self.store, app['id'], review),
                       lambda: jobs.begin_submit(self.store, app['id'])]:
            with self.assertRaisesRegex(ValueError, 'Role configuration/personal route changed'):
                action()
        self.assertEqual(tracker, self.store.read('tracker.json'))
        self.assertEqual(pdf, (self.store.root / 'packages/demo-job/resume.pdf').read_bytes())
        self.assertEqual('trial', self.store.status()['next_step'])
        with self.assertRaisesRegex(ValueError, 'current trial package'):
            profiles.checkpoint(self.store, 'trial')
        jobs.assess(self.store, assessment(self.store))
        with self.assertRaisesRegex(ValueError, 'stale'):
            jobs.prepare(self.store, app['id'], review)
        with self.assertRaisesRegex(ValueError, 'Prepared inputs changed'):
            jobs.begin_submit(self.store, app['id'])
        stub_ready_package(self.store)
        jobs.prepare(self.store, app['id'], review)
        jobs.begin_submit(self.store, app['id'])

    def test_changing_another_role_does_not_invalidate_unaffected_trial(self):
        profiles.update_preferences(self.store, {'targets': ['operations', 'logistics']})
        other = {'id': 'logistics', 'title': 'Logistics Coordinator', 'focus': ['Shipment planning']}
        profiles.role_create(self.store, other, ['codex'])
        jobs.assess(self.store, assessment(self.store))
        self.complete_trial_stub()
        profiles.role_create(self.store, {**other, 'focus': ['Inventory coordination']}, ['codex'])
        jobs.fresh(self.store, self.store.read('jobs/demo-job.json'))
        self.assertEqual('complete', self.store.status()['next_step'])

    def test_unknown_submission_can_still_be_reconciled_after_context_change(self):
        stub_ready_package(self.store)
        app, _, review = authorized_preparation(self.store)
        jobs.prepare(self.store, app['id'], review)
        begun = jobs.begin_submit(self.store, app['id'])
        role = self.store.read('roles/operations.json')
        profiles.role_create(self.store, {**role, 'focus': ['New fictional priority']}, ['codex'])
        receipt = self.store.root / 'evidence/receipt.txt'
        receipt.parent.mkdir()
        receipt.write_text('Fictional platform confirms this original application was received.', encoding='utf-8')
        reopened = Store(self.store.workspace)
        with self.assertRaisesRegex(ValueError, 'uncertain previous outcome'):
            jobs.prepare(reopened, app['id'], review)
        row = jobs.outcome(reopened, app['id'], {'attempt_id': begun['attempt_id'], 'result': 'confirmed',
            'detail': 'Fictional reconciliation only', 'observed_confirmation': True, 'confirmation_text': 'Received',
            'confirmation_url': 'https://example.invalid/history', 'evidence_path': 'evidence/receipt.txt', 'next_action': 'Wait'})
        self.assertEqual('Submitted', row['status'])

    def test_cli_failure_is_actionable_json_and_retry_needs_no_input_json(self):
        blocked = self.block_folder('.agents')
        script = Path(profiles.__file__).with_name('career.py')
        prefix = [sys.executable, str(script), '--workspace', str(self.store.workspace)]
        failed = subprocess.run([*prefix, 'role-create', '--input', str(self.store.root / 'roles/operations.json')],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(1, failed.returncode)
        self.assertEqual('', failed.stdout)
        self.assertIn('role-retry operations', json.loads(failed.stderr)['error'])
        self.assertNotIn('Traceback', failed.stderr)
        blocked.unlink()
        retried = subprocess.run([*prefix, 'role-retry', 'operations'], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(0, retried.returncode, retried.stderr)
        self.assertEqual('ready', json.loads(retried.stdout)['generation']['status'])


if __name__ == '__main__':
    unittest.main()
