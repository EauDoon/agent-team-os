import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.author import compose_brief, compose_message, write_new_json

ROOT = Path(__file__).resolve().parents[1]


class AuthorTests(unittest.TestCase):
    def test_message_composition_keeps_explicit_version_and_copied_scope(self):
        payload = {'role_brief': self.brief()}
        message = compose_message('handoff', 'agent-team-connect/v0.2', 'owner', 'maker', 'm1', 'task1', payload)
        payload['role_brief']['access_scope'] = 'changed after composition'
        self.assertEqual(message['payload']['role_brief']['access_scope'], 'Supplied files only.')
        with self.assertRaises(ValueError):
            compose_message('handoff', 'agent-team-connect/v0.1', 'owner', 'maker', 'm1', 'task1', payload)
        with self.assertRaises(ValueError):
            compose_message('response', 'agent-team-connect/v0.2', 'owner', 'maker', 'm1', 'task1',
                            {'accepted': False, 'refusal_reason': ' ', 'next_step': 'Clarify scope.'})

    def test_actual_message_authoring_and_invalid_handoff_does_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            brief = Path(directory) / 'brief.json'
            write_new_json(brief, self.brief())
            for index, kind in enumerate(('handoff', 'refusal')):
                target = Path(directory) / f'{kind}.json'
                flags = ['--brief', str(brief)] if kind == 'handoff' else ['--reason', 'Outside scope.', '--next-step', 'Request scoped approval.']
                entry = ['scripts/author.py'] if index == 0 else ['-m', 'scripts.author']
                command = [sys.executable, *entry, kind, '--version', 'agent-team-connect/v0.2',
                           '--from', 'owner', '--to', 'maker', '--message-id', 'm1', '--correlation-id', 'task1',
                           '--output', str(target), *flags]
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(target.read_text())['connect_version'], 'agent-team-connect/v0.2')
            brief.write_text('{}')
            missing = Path(directory) / 'invalid-handoff.json'
            command = [sys.executable, 'scripts/author.py', 'handoff', '--version', 'agent-team-connect/v0.2',
                       '--from', 'owner', '--to', 'maker', '--message-id', 'm1', '--correlation-id', 'task1',
                       '--brief', str(brief), '--output', str(missing)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(missing.exists())

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
