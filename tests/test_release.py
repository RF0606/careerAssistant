"""Public bundle boundaries: private sentinel, hashes and clean extraction."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid
import os
from unittest.mock import patch
from zipfile import ZipFile

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('releaser', PROJECT/'release.py')
releaser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(releaser)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'public'
        self.root.mkdir()
        for source in releaser.public_files():
            target = self.root/source.relative_to(PROJECT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        self.override = patch.object(releaser, 'ROOT', self.root)
        self.override.start()
        self.addCleanup(self.override.stop)

    def test_pack_excludes_private_data_and_verifies_handoff_hashes(self):
        sentinel = 'PRIVATE-' + uuid.uuid4().hex
        for name in ['.career-assistant/credentials/workday/accounts.txt',
                     '.career-assistant/routes/private-direction.md',
                     '.agents/skills/career-resume-private/SKILL.md',
                     'test-results/host-output.txt']:
            target = self.root/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(sentinel)
        manifest = releaser.manifest()
        archive = self.root/'outputs/career-assistant.zip'
        releaser.pack(archive)
        with ZipFile(archive) as zipped:
            self.assertEqual(set(zipped.namelist()), set(manifest['files'])|{'release_manifest.json'})
            for name in zipped.namelist():
                self.assertNotIn(sentinel.encode(), zipped.read(name))
            self.assertIn('README.md', zipped.namelist())
            self.assertFalse(any('/references/routes/' in name for name in zipped.namelist()))
            extracted = self.root/'unpacked'
            zipped.extractall(extracted)
        with patch.object(releaser, 'ROOT', extracted):
            releaser.verify()
        for line in (archive.parent/'SHA256SUMS.txt').read_text().splitlines():
            sha, name = line.split('  ', 1)
            self.assertEqual(sha, hashlib.sha256((archive.parent/name).read_bytes()).hexdigest())

    def test_secret_line_in_public_tree_is_rejected_without_echo(self):
        p = self.root/'docs/accidental.txt'
        p.write_text('username'+': fictional@example.invalid, '+'password'+': secret-sentinel')
        with self.assertRaises(ValueError) as caught:
            releaser.manifest()
        self.assertNotIn('secret-sentinel', str(caught.exception))

    def test_changed_source_cannot_be_packed_without_reviewed_manifest(self):
        releaser.manifest()
        with (self.root/'README.md').open('a', encoding='utf-8') as stream:
            stream.write('\nChanged\n')
        with self.assertRaises(ValueError):
            releaser.pack(self.root/'outputs/changed.zip')

    def test_zip_is_reproducible_after_file_timestamps_change(self):
        releaser.manifest()
        first = self.root/'first/career-assistant.zip'; releaser.pack(first)
        for path in releaser.public_files(): os.utime(path, (1700000000, 1700000000))
        second = self.root/'second/career-assistant.zip'; releaser.pack(second)
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_tracked_private_or_extra_paths_are_rejected(self):
        recorded = releaser.manifest()
        paths = [*recorded['files'], 'release_manifest.json', '.career-assistant/profile.json']
        import subprocess
        result = subprocess.CompletedProcess(['git'], 0, ('\x00'.join(paths)+'\x00').encode(), b'')
        with patch.object(releaser.subprocess, 'run', return_value=result), self.assertRaisesRegex(ValueError, 'allowlist'):
            releaser.tracked_check()

    def test_bundled_personal_routes_are_rejected(self):
        target=self.root/'skills/career-assistant/references/routes/user-role.md'
        target.parent.mkdir(parents=True)
        target.write_text('Locally generated user knowledge must stay private.')
        with self.assertRaisesRegex(ValueError,'generated locally after download'):
            releaser.manifest()

    def test_bundled_personal_skills_are_rejected(self):
        target=self.root/'skills/career-resume-personal/SKILL.md'
        target.parent.mkdir(parents=True)
        target.write_text('Locally generated user skill must stay private.')
        with self.assertRaisesRegex(ValueError,'generated locally after download'):
            releaser.manifest()


if __name__ == '__main__':
    unittest.main()
