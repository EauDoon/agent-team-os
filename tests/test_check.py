import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.check import check_document, load_json, MAX_BYTES

ROOT = Path(__file__).resolve().parents[1]


class CheckTests(unittest.TestCase):
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
