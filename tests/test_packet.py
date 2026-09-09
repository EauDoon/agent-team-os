import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.packet import inspect_packet, make_receipt, record_path, verify_receipt

ROOT = Path(__file__).resolve().parents[1]


class PacketTests(unittest.TestCase):
    def test_bundled_packet_checks_actual_bytes(self):
        result = inspect_packet(ROOT / 'templates/operator-packet.json')
        self.assertTrue(result['ok'])
        for record in result['records']:
            self.assertEqual(record['sha256'], hashlib.sha256((ROOT / 'templates' / record['path']).read_bytes()).hexdigest())

    def test_unsafe_paths_fail_before_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['../outside.json', '/outside.json', 'C:/outside.json', 'file.json:stream', 'a\\b.json', './file.json', 'a//b.json']:
                with self.assertRaises(ValueError, msg=name):
                    record_path(root, name)

    def test_bad_record_preserves_other_results_and_duplicates_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'plan.json').write_bytes((ROOT / 'templates/routing-plan.json').read_bytes())
            packet = {'packet_version': 'agent-team-packet/v0.1', 'task_id': 'fictional-task',
                      'records': [{'id': 'plan', 'kind': 'plan', 'path': 'plan.json'},
                                  {'id': 'brief', 'kind': 'brief', 'path': 'missing.json'}]}
            path = root / 'packet.json'
            path.write_text(json.dumps(packet))
            result = inspect_packet(path)
            self.assertFalse(result['ok'])
            self.assertTrue(result['records'][0]['ok'])
            packet['records'][1]['id'] = 'plan'
            path.write_text(json.dumps(packet))
            with self.assertRaises(ValueError):
                inspect_packet(path)

    def test_actual_packet_cli_in_both_modes(self):
        for entry in [['scripts/packet.py'], ['-m', 'scripts.packet']]:
            result = subprocess.run([sys.executable, *entry, 'templates/operator-packet.json'],
                                    cwd=ROOT, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)['ok'])

    def test_receipt_metadata_and_duplicate_records_cannot_match(self):
        result = inspect_packet(ROOT / 'templates/operator-packet.json')
        receipt = make_receipt(result)
        self.assertTrue(verify_receipt(result, receipt)['ok'])
        for key, value in [('task_id', 'other'), ('index_sha256', '0' * 64)]:
            changed = copy.deepcopy(receipt)
            changed[key] = value
            self.assertFalse(verify_receipt(result, changed)['ok'])
        for key, value in [('id', 'other'), ('kind', 'brief'), ('path', '../outside.json'),
                           ('sha256', '0' * 64), ('bytes', 0)]:
            changed = copy.deepcopy(receipt)
            changed['records'][0][key] = value
            self.assertFalse(verify_receipt(result, changed)['ok'])
        receipt['records'].append(receipt['records'][0])
        with self.assertRaises(ValueError):
            verify_receipt(result, receipt)

    def test_receipt_cli_detects_byte_drift_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['operator-packet.json', 'routing-plan.json', 'audit-closure.json']:
                (root / name).write_bytes((ROOT / 'templates' / name).read_bytes())
            index = root / 'operator-packet.json'
            receipt = root / 'receipt.json'
            def run(*args):
                result = subprocess.run([sys.executable, '-m', 'scripts.packet', str(index), *map(str, args)],
                                        cwd=ROOT, capture_output=True, text=True, timeout=5)
                self.assertNotIn('Traceback', result.stderr)
                return result.returncode, json.loads(result.stdout)
            self.assertEqual(run('--receipt', receipt)[0], 0)
            original = receipt.read_bytes()
            self.assertEqual(run('--receipt', receipt)[0], 1)
            self.assertEqual(receipt.read_bytes(), original)
            self.assertEqual(run('--verify-receipt', receipt)[0], 0)
            plan = root / 'routing-plan.json'
            plan.write_bytes(plan.read_bytes() + b'\n')
            code, result = run('--verify-receipt', receipt)
            self.assertEqual(code, 1)
            self.assertIn('records', result['differences'])
            plan.write_bytes((ROOT / 'templates/routing-plan.json').read_bytes())
            index.write_bytes(index.read_bytes() + b'\n')
            self.assertIn('index_sha256', run('--verify-receipt', receipt)[1]['differences'])
            plan.write_bytes(b'{}')
            self.assertEqual(run('--receipt', root / 'invalid-receipt.json')[0], 1)
            self.assertFalse((root / 'invalid-receipt.json').exists())
            self.assertEqual(run('--verify-receipt', receipt)[1]['differences'], ['packet_conformance'])

    def test_packet_cardinality_and_total_byte_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = root / 'packet.json'
            packet = {'packet_version': 'agent-team-packet/v0.1', 'task_id': 'fictional-task',
                      'records': [{'id': str(i), 'kind': 'plan', 'path': f'{i}.json'} for i in range(17)]}
            index.write_text(json.dumps(packet), encoding='utf-8')
            with self.assertRaises(ValueError):
                inspect_packet(index)
            packet['records'] = packet['records'][:5]
            index.write_text(json.dumps(packet), encoding='utf-8')
            raw = (ROOT / 'templates/routing-plan.json').read_bytes()
            for item in packet['records']:
                (root / item['path']).write_bytes(raw + b' ' * (1048576 - len(raw)))
            with self.assertRaises(OverflowError):
                inspect_packet(index)

    def test_symbolic_record_is_rejected_when_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'record.json'
            target.write_text('{}', encoding='utf-8')
            link = root / 'link.json'
            try:
                link.symlink_to(target.name)
            except OSError:
                self.skipTest('symbolic links are unavailable to this account')
            with self.assertRaises(ValueError):
                record_path(root, 'link.json')


if __name__ == '__main__':
    unittest.main()
