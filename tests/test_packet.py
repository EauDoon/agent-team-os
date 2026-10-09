import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.packet import inspect_packet, make_receipt, record_path, verify_receipt

ROOT = Path(__file__).resolve().parents[1]


class PacketTests(unittest.TestCase):
    def test_receipt_differences_identify_records_and_fields_without_reading_receipt_paths(self):
        result = inspect_packet(ROOT / 'templates/operator-packet.json')
        receipt = make_receipt(result)
        changed = copy.deepcopy(result)
        changed['records'][0]['sha256'] = '0' * 64
        report = verify_receipt(changed, receipt)
        self.assertEqual(report['record_changes'], [{'id': result['records'][0]['id'], 'fields': ['sha256']}])
        changed['records'].pop()
        self.assertEqual(verify_receipt(changed, receipt)['records_removed'], [result['records'][-1]['id']])
        changed = copy.deepcopy(result)
        changed['records'][0].update(ok=False, sha256=None, bytes=None)
        changed['ok'] = False
        report = verify_receipt(changed, receipt)
        self.assertEqual(report['differences'], ['packet_conformance'])
        self.assertEqual(report['invalid_records'], [result['records'][0]['id']])
        self.assertEqual(report['record_changes'][0]['fields'], ['bytes', 'sha256'])
        changed = copy.deepcopy(result)
        changed['records'].reverse()
        report = verify_receipt(changed, receipt)
        self.assertTrue(report['record_order_changed'])
        self.assertEqual(report['record_changes'], [])

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

    def test_trailing_dot_or_space_components_fail_before_any_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['plan.json.', 'plan.json ', 'dir./plan.json', 'dir /plan.json', 'plan.json. .']:
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'canonical and relative'):
                    record_path(root, name)

    def test_aliased_record_path_cannot_count_one_file_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'routing-plan.json').write_bytes((ROOT / 'templates/routing-plan.json').read_bytes())
            packet = {'packet_version': 'agent-team-packet/v0.1', 'task_id': 'fictional-task',
                      'records': [{'id': 'plan', 'kind': 'plan', 'path': 'routing-plan.json'},
                                  {'id': 'alias', 'kind': 'plan', 'path': 'routing-plan.json.'}]}
            index = root / 'packet.json'
            index.write_text(json.dumps(packet), encoding='utf-8')
            result = inspect_packet(index)
            self.assertFalse(result['ok'])
            self.assertTrue(result['records'][0]['ok'])
            self.assertFalse(result['records'][1]['ok'])
            self.assertIsNone(result['records'][1]['sha256'])
            with self.assertRaises(ValueError):
                make_receipt(result)

    def test_hard_link_alias_is_reported_as_an_already_listed_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'routing-plan.json').write_bytes((ROOT / 'templates/routing-plan.json').read_bytes())
            try:
                os.link(root / 'routing-plan.json', root / 'alias.json')
            except OSError:
                self.skipTest('hard links are unavailable on this filesystem')
            packet = {'packet_version': 'agent-team-packet/v0.1', 'task_id': 'fictional-task',
                      'records': [{'id': 'plan', 'kind': 'plan', 'path': 'routing-plan.json'},
                                  {'id': 'alias', 'kind': 'plan', 'path': 'alias.json'}]}
            index = root / 'packet.json'
            index.write_text(json.dumps(packet), encoding='utf-8')
            result = inspect_packet(index)
            self.assertFalse(result['ok'])
            self.assertTrue(result['records'][0]['ok'])
            self.assertEqual(result['records'][1]['failures'],
                             ['record names a file already listed in this packet'])

    def test_evaluation_records_use_the_requested_schema_root(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            schema_root = base / 'alternate'
            for relative in ('schemas/packet.schema.json', 'evals/tasks.json', 'evals/run.schema.json'):
                (schema_root / relative).parent.mkdir(parents=True, exist_ok=True)
                (schema_root / relative).write_bytes((ROOT / relative).read_bytes())
            suite = json.loads((ROOT / 'evals/tasks.json').read_text(encoding='utf-8'))
            run = {'run_version': 'agent-team-run/v0.1', 'suite_version': suite['suite_version'],
                   'status': 'synthetic', 'runner': 'runner', 'reviewer': 'reviewer',
                   'records': [{'task_id': task['id'], 'arm': arm, 'output_revision': 'fixture-o1',
                                'review_evidence': 'Synthetic check record.',
                                'configuration': 'Synthetic runner configuration.',
                                'prompt_revision': 'fixture-p1', 'evidence_revision': 'fixture-e1',
                                'checks': ['pass'] * len(task['acceptance']), 'tokens': 10,
                                'duration_seconds': 2.5}
                               for task in suite['tasks'] for arm in ('solo', 'current')]}
            packet_dir = base / 'packet'
            packet_dir.mkdir()
            (packet_dir / 'run.json').write_text(json.dumps(run), encoding='utf-8')
            index = packet_dir / 'packet.json'
            index.write_text(json.dumps({'packet_version': 'agent-team-packet/v0.1', 'task_id': 'fictional-task',
                                         'records': [{'id': 'run', 'kind': 'evaluation', 'path': 'run.json'}]}),
                             encoding='utf-8')
            self.assertTrue(inspect_packet(index, schema_root=schema_root)['ok'])
            schema = json.loads((schema_root / 'evals/run.schema.json').read_text(encoding='utf-8'))
            schema['required'] = schema['required'] + ['alternate_only_field']
            (schema_root / 'evals/run.schema.json').write_text(json.dumps(schema), encoding='utf-8')
            self.assertFalse(inspect_packet(index, schema_root=schema_root)['ok'])
            self.assertTrue(inspect_packet(index)['ok'])

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
        for label, mutate in (
            ('index', lambda item: item.update(index_sha256='g' * 64)),
            ('record', lambda item: item['records'][0].update(sha256='a' * 65)),
            ('short', lambda item: item['records'][0].update(sha256='ab')),
        ):
            changed = copy.deepcopy(make_receipt(result))
            mutate(changed)
            with self.assertRaises(ValueError, msg=label):
                verify_receipt(result, changed)

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
