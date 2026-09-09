import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.author import compose_brief, write_new_json

ROOT = Path(__file__).resolve().parents[1]


class AuthorTests(unittest.TestCase):
    def brief(self):
        return compose_brief('Maker', 'Supplied files only.', 'Build a fictional tool.',
                             'Supplied requirements.', 'Tool and acceptance checks.',
                             'Stop after acceptance checks or a scope gap.')

    def test_blank_field_is_not_authored(self):
        with self.assertRaises(ValueError):
            compose_brief('Maker', ' ', 'task', 'evidence', 'output', 'stop')

    def test_complete_brief_and_exclusive_write(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'brief.json'
            write_new_json(target, self.brief())
            original = target.read_bytes()
            self.assertEqual(json.loads(original), self.brief())
            with self.assertRaises(FileExistsError):
                write_new_json(target, {'replacement': True})
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ['brief.json'])

    def test_actual_author_cli_and_no_overwrite_in_both_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            for index, entry in enumerate([['scripts/author.py'], ['-m', 'scripts.author']]):
                target = Path(directory) / f'brief-{index}.json'
                command = [sys.executable, *entry, 'brief', '--role', 'Maker', '--scope', 'Supplied files.',
                           '--task', 'Build the fictional tool.', '--evidence', 'Supplied requirements.',
                           '--deliver', 'Tool and acceptance checks.', '--stop', 'Acceptance or gap.', '--output', str(target)]
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(json.loads(result.stdout)['ok'])
                before = target.read_bytes()
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stderr, '')
                self.assertEqual(target.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
