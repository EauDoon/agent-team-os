import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.check import check_document, load_json, MAX_BYTES

ROOT = Path(__file__).resolve().parents[1]


class CheckTests(unittest.TestCase):
    def test_connection_cli_selects_declared_wire_version(self):
        suite = json.loads((ROOT / 'conformance/connect/cases.json').read_text())
        message = next(case['message'] for case in suite['cases'] if case['name'] == 'handoff-valid')
        message['payload']['role_brief']['consumer_note'] = 'Existing v0.1 extension.'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'message.json'
            for version, expected in [('v0.1', 0), ('v0.2', 1), ('v999', 1)]:
                message['connect_version'] = 'agent-team-connect/' + version
                path.write_text(json.dumps(message), encoding='utf-8')
                for entry in [['scripts/check.py'], ['-m', 'scripts.check']]:
                    result = subprocess.run([sys.executable, *entry, 'connect', str(path), '--json'],
                                            cwd=ROOT, capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                    self.assertEqual(json.loads(result.stdout)['ok'], expected == 0)

    def test_schema_root_is_the_requested_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'schemas').mkdir()
            (root / 'schemas/role-brief.schema.json').write_text('{"const": "alternate"}')
            self.assertEqual(check_document('brief', 'alternate', schema_root=root), [])
            self.assertTrue(check_document('brief', 'other', schema_root=root))

    def test_bundled_operator_fixtures_in_both_cli_modes(self):
        for kind, name in [('plan', 'routing-plan'), ('evidence', 'evidence-ledger'), ('audit', 'audit-closure')]:
            for entry in [['scripts/check.py'], ['-m', 'scripts.check']]:
                result = subprocess.run([sys.executable, *entry, kind, f'templates/{name}.json', '--json'],
                                        cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertTrue(json.loads(result.stdout)['ok'])

    def test_rejects_duplicate_nonfinite_oversize_and_bad_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            for raw in [b'{"x":1,"x":2}', b'NaN', b'Infinity', b'1e999', b'\xff', b' ' * (MAX_BYTES + 1)]:
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    load_json(path)

    def test_standalone_and_module_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'brief.json'
            path.write_text(json.dumps(dict.fromkeys(
                ['role', 'access_scope', 'task', 'evidence', 'output_contract', 'stop_condition'],
                'Supplied fictional task.')))
            for entry in [['scripts/check.py'], ['-m', 'scripts.check']]:
                command = [sys.executable, *entry, 'brief', str(path), '--json']
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(json.loads(result.stdout)['ok'])
            path.write_text('{}')
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)['ok'])


if __name__ == '__main__':
    unittest.main()
