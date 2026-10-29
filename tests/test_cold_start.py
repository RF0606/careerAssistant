"""Optional capabilities cannot prevent source-backed local onboarding."""
from pathlib import Path
import subprocess
import json
import sys
import tempfile
import unittest
import threading
import time
from unittest.mock import patch
from fixtures import make_workspace, assessment, draft
from storage import Store, atomic
import storage
import host_smoke
import profiles
import capabilities
import jobs
import resume
from cold_start import run


class ColdStartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_actual_dependency_free_venv_can_onboard_score_and_save_draft(self):
        result = run(self.root)
        self.assertIn('failures-preserve-profile-and-do-not-create-ready-pdf', result['passed'])
        self.assertFalse(result['doctor']['features']['pdf_generation_and_qa'])

    def test_host_acceptance_starts_from_public_download_without_installed_skills(self):
        root = self.root / 'downloaded-project'
        initial = host_smoke.prepare_workspace(root, 'codex')
        self.assertFalse(any(initial.values()))
        self.assertTrue((root/'README.md').is_file())
        self.assertTrue((root/'skills/career-assistant/SKILL.md').is_file())
        with self.assertRaisesRegex(ValueError, 'empty workspace'):
            host_smoke.prepare_workspace(root, 'codex')

    def test_denied_host_skill_directory_is_specific_and_creates_no_routes(self):
        (self.root / '.agents').write_text('Fictional folder conflict', encoding='utf-8')
        report = capabilities.report(self.root, probe_writes=True)
        probes = report['permissions']['probes']
        self.assertTrue(probes[0]['writable'])
        self.assertFalse(probes[1]['writable'])
        self.assertIn(probes[1]['reason'], ['FileExistsError', 'NotADirectoryError'])
        self.assertFalse((self.root / '.career-assistant/routes').exists())

    def test_default_doctor_does_not_write_or_claim_browser_access(self):
        report = capabilities.report(self.root)
        self.assertEqual([], list(self.root.iterdir()))
        self.assertEqual('host-inspection-required', report['features']['browser'])

    def test_source_cli_defaults_to_codex_and_preserves_explicit_hosts_on_refresh(self):
        store = Store(self.root / 'fictional-user'); store.initialize()
        profiles.update_preferences(store, {'targets': ['logistics']})
        payload = {'id': 'logistics', 'title': 'Fictional Logistics Coordinator', 'focus': ['Shipment planning']}
        input_path = store.root / 'role-input.json'; atomic(input_path, payload)
        command = [sys.executable, str(Path(profiles.__file__).with_name('career.py')), '--workspace', str(store.workspace), 'role-create', '--input', str(input_path)]
        def invoke(extra=()):
            result = subprocess.run([*command, *extra], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(0, result.returncode, result.stderr)
            return json.loads(result.stdout)
        self.assertEqual(['codex'], invoke()['generation']['hosts'])
        self.assertFalse((store.workspace / '.claude').exists())
        self.assertEqual(['codex', 'claude'], invoke(['--host', 'both'])['generation']['hosts'])
        payload['focus'] = ['Fictional updated delivery priority']; atomic(input_path, payload)
        self.assertEqual(['codex', 'claude'], invoke()['generation']['hosts'])

    def test_pdf_cache_probe_cannot_claim_empty_offline_cache_ready(self):
        # Deterministically emulate the documented compiler failure; an actual
        # empty-cache execution is recorded separately by the maintainer.
        result = subprocess.CompletedProcess(['tectonic'], 1, b'', b'cache empty')
        with patch.object(capabilities.subprocess, 'run', return_value=result) as call:
            report = capabilities.pdf_smoke(self.root, 'tectonic')
        self.assertEqual('cache-unverified', report['status'])
        self.assertIn('--only-cached', call.call_args.args[0])
        self.assertTrue(report['offline_only'])

    def test_missing_qa_dependency_prevents_compiler_invocation(self):
        store = make_workspace(self.root / 'fictional-user')
        jobs.assess(store, assessment(store))
        with patch.object(resume.shutil, 'which', return_value='tectonic'), patch.dict(sys.modules, {'pymupdf': None}), patch.object(resume.subprocess, 'run') as compiler:
            with self.assertRaisesRegex(ValueError, 'PyMuPDF'):
                resume.render(store, 'demo-job', draft(store))
            compiler.assert_not_called()
        self.assertEqual('draft', store.read('packages/demo-job/validation.json')['status'])

    def test_compilation_timeout_is_actionable_and_preserves_draft(self):
        store = make_workspace(self.root / 'fictional-user')
        jobs.assess(store, assessment(store))
        with patch.object(resume.shutil, 'which', return_value='tectonic'), patch.dict(sys.modules, {'pymupdf': object()}), patch.object(resume.subprocess, 'run', side_effect=subprocess.TimeoutExpired('tectonic', 180)):
            with self.assertRaisesRegex(ValueError, 'timed out.*Source saved as draft'):
                resume.render(store, 'demo-job', draft(store))
        self.assertEqual('draft', store.read('packages/demo-job/validation.json')['status'])


class AtomicWriteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'state.json'
        self.path.write_bytes(b'original')

    def test_transient_windows_sharing_conflict_recovers_without_partial_data(self):
        original = storage.os.replace
        calls = []
        error = PermissionError('Fictional transient Windows sharing conflict'); error.winerror = 32
        def transient(source, target):
            calls.append(1)
            if len(calls) < 3: raise error
            return original(source, target)
        with patch.object(storage.os, 'replace', transient), patch.object(storage.time, 'sleep'):
            storage.atomic_bytes(self.path, b'complete replacement')
        self.assertEqual(3, len(calls))
        self.assertEqual(b'complete replacement', self.path.read_bytes())
        self.assertEqual([self.path], list(self.path.parent.iterdir()))

    def test_persistent_windows_denial_stops_and_preserves_original(self):
        error = PermissionError('Fictional persistent denial'); error.winerror = 5
        with patch.object(storage.os, 'replace', side_effect=error) as replacement, patch.object(storage.time, 'sleep'):
            with self.assertRaises(PermissionError): storage.atomic_bytes(self.path, b'never committed')
        self.assertEqual(6, replacement.call_count)
        self.assertEqual(b'original', self.path.read_bytes())
        self.assertEqual([self.path], list(self.path.parent.iterdir()))

    def test_non_windows_or_policy_denials_are_not_retried(self):
        with patch.object(storage.os, 'replace', side_effect=PermissionError('Fictional policy denial')) as replacement, patch.object(storage.time, 'sleep') as sleep:
            with self.assertRaises(PermissionError): storage.atomic(self.path, {'new': 'value'})
        self.assertEqual(1, replacement.call_count); sleep.assert_not_called()
        self.assertEqual(b'original', self.path.read_bytes())

    @unittest.skipUnless(sys.platform == 'win32', 'Actual Windows file-sharing behavior')
    def test_actual_windows_reader_lock_is_tolerated(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(self.path), 0x80000000, 1, None, 3, 0x80, None)
        self.assertNotEqual(ctypes.c_void_p(-1).value, handle, ctypes.get_last_error())
        def release():
            time.sleep(0.07)
            kernel.CloseHandle(handle)
        reader = threading.Thread(target=release); reader.start()
        try:
            storage.atomic_bytes(self.path, b'replaced after actual reader closed')
        finally:
            reader.join()
        self.assertEqual(b'replaced after actual reader closed', self.path.read_bytes())


if __name__ == '__main__':
    unittest.main()
