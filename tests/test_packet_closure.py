import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from scripts.check import read_json_bytes
from scripts.packet import inspect_packet, make_receipt, verify_receipt

ROOT = Path(__file__).resolve().parents[1]


class ClosurePacketTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / 'packet.json'
        self.audit = json.loads((ROOT / 'templates/audit-closure.json').read_text())
        self.target = self.audit['target_revision']
        self.evidence = {
            'ledger_version': 'agent-team-evidence/v0.1',
            'sources': [{'id': 'output', 'locator': 'Synthetic tool test record',
                         'revision': self.target, 'inspected_on': '26-09-2026'}],
            'claims': [{'id': 'empty-name', 'statement': 'Synthetic empty input is rejected.',
                        'status': 'supported', 'source_ids': ['output'],
                        'reasoning': 'Illustrative result only.', 'next_step': ''}],
        }
        self.packet = {
            'packet_version': 'agent-team-packet/v0.2', 'task_id': 'synthetic-tool',
            'records': [{'id': 'audit', 'kind': 'audit', 'path': 'audit.json'},
                        {'id': 'evidence', 'kind': 'evidence', 'path': 'evidence.json'}],
            'closure': {'audit_record': 'audit', 'evidence_record': 'evidence',
                        'target_revision': self.target, 'target_source': 'output',
                        'required_claims': ['empty-name']},
        }

    def write(self):
        for name, document in [('packet', self.packet), ('audit', self.audit), ('evidence', self.evidence)]:
            (self.root / (name + '.json')).write_text(json.dumps(document), encoding='utf-8')

    def inspect(self, **kwargs):
        self.write()
        return inspect_packet(self.path, **kwargs)

    def assert_not_ready(self, result):
        self.assertFalse(result['ok'])
        self.assertFalse(result['closure']['ready'])
        self.assertTrue(result['closure']['failures'])
        with self.assertRaises(ValueError):
            make_receipt(result)

    def test_valid_closure_and_receipt_use_one_read_per_record(self):
        self.write()
        with patch('scripts.packet.read_json_bytes', wraps=read_json_bytes) as reader:
            result = inspect_packet(self.path, target_revision=self.target)
        self.assertEqual(reader.call_count, 3)
        self.assertTrue(result['closure']['ready'])
        self.assertTrue(verify_receipt(result, make_receipt(result))['matches'])

    def test_incomplete_required_claims_cannot_receive_receipts(self):
        for status in ['unsupported', 'assumption', 'conflicting']:
            with self.subTest(status=status):
                self.evidence['claims'][0].update(status=status, next_step='Recheck the synthetic output.')
                if status == 'conflicting':
                    self.evidence['sources'].append({**self.evidence['sources'][0], 'id': 'other'})
                    self.evidence['claims'][0]['source_ids'].append('other')
                result = self.inspect()
                self.assertTrue(all(record['ok'] for record in result['records']))
                self.assert_not_ready(result)

    def test_missing_claim_and_target_source_and_unrelated_support_fail(self):
        for field, value in [('required_claims', ['missing']), ('target_source', 'missing')]:
            with self.subTest(field=field):
                original = copy.deepcopy(self.packet['closure'])
                self.packet['closure'][field] = value
                self.assert_not_ready(self.inspect())
                self.packet['closure'] = original
        self.evidence['sources'].append({**self.evidence['sources'][0], 'id': 'unrelated'})
        self.evidence['claims'][0]['source_ids'] = ['unrelated']
        self.assert_not_ready(self.inspect())

    def test_unselected_claims_do_not_expand_declared_policy(self):
        self.evidence['claims'].append({**self.evidence['claims'][0], 'id': 'optional',
                                       'status': 'unsupported', 'source_ids': [], 'next_step': 'Investigate later.'})
        self.assertTrue(self.inspect()['ok'])

    def test_stale_audit_and_source_fail_even_when_records_conform(self):
        self.audit['target_revision'] = 'fictional-tool-r1'
        self.audit['findings'][0]['checked_revision'] = 'fictional-tool-r1'
        result = self.inspect()
        self.assertTrue(all(record['ok'] for record in result['records']))
        self.assert_not_ready(result)
        self.audit['target_revision'] = self.target
        self.audit['findings'][0]['checked_revision'] = self.target
        self.evidence['sources'][0]['revision'] = 'fictional-tool-r1'
        self.assert_not_ready(self.inspect())

    def test_nonpass_and_invalid_audits_fail(self):
        for recommendation in ['revise', 'blocked']:
            self.audit['recommendation'] = recommendation
            self.assert_not_ready(self.inspect())
        self.audit['recommendation'] = 'pass'
        self.audit['findings'][0]['disposition'] = 'open'
        self.assert_not_ready(self.inspect())

    def test_unknown_wrong_kind_and_invalid_selected_records_fail(self):
        for field, value in [('audit_record', 'missing'), ('audit_record', 'evidence'),
                             ('evidence_record', 'missing'), ('evidence_record', 'audit')]:
            with self.subTest(field=field, value=value):
                original = copy.deepcopy(self.packet['closure'])
                self.packet['closure'][field] = value
                self.assert_not_ready(self.inspect())
                self.packet['closure'] = original
        self.write()
        (self.root / 'evidence.json').unlink()
        self.assert_not_ready(inspect_packet(self.path))
        self.write()
        (self.root / 'evidence.json').write_text('{}')
        self.assert_not_ready(inspect_packet(self.path))

    def test_unrelated_invalid_record_still_prevents_closure(self):
        self.packet['records'].append({'id': 'brief', 'kind': 'brief', 'path': 'missing.json'})
        self.assert_not_ready(self.inspect())

    def test_expected_revision_rejects_self_consistent_replay_and_legacy_downgrade(self):
        result = self.inspect()
        receipt = make_receipt(result)
        replay = inspect_packet(self.path, target_revision='fictional-tool-r3')
        self.assert_not_ready(replay)
        verification = verify_receipt(replay, receipt)
        self.assertFalse(verification['matches'])
        self.assertEqual(verification['record_changes'], [])
        self.assertEqual(verification['invalid_records'], [])
        self.assertIn('requested revision', verification['closure']['failures'][0])
        self.packet['packet_version'] = 'agent-team-packet/v0.1'
        del self.packet['closure']
        self.assertTrue(self.inspect()['ok'])
        self.assert_not_ready(self.inspect(target_revision=self.target))

    def test_empty_duplicate_oversized_or_unknown_closure_policy_is_rejected(self):
        original = copy.deepcopy(self.packet['closure'])
        for value in [[], ['empty-name', 'empty-name'], [str(i) for i in range(65)]]:
            self.packet['closure']['required_claims'] = value
            with self.assertRaises(ValueError):
                self.inspect()
        self.packet['closure'] = original
        self.packet['closure']['unexpected'] = True
        with self.assertRaises(ValueError):
            self.inspect()
        del self.packet['closure']
        with self.assertRaises(ValueError):
            self.inspect()

    def test_blank_target_and_bad_expected_revision_fail(self):
        self.packet['closure']['target_revision'] = ' '
        self.assert_not_ready(self.inspect())
        for value in ['', ' ', False, 3]:
            with self.assertRaises(ValueError):
                self.inspect(target_revision=value)

    def test_receipt_still_rejects_formatting_and_policy_drift(self):
        receipt = make_receipt(self.inspect())
        evidence = self.root / 'evidence.json'
        evidence.write_bytes(evidence.read_bytes() + b'\n')
        self.assertFalse(verify_receipt(inspect_packet(self.path), receipt)['matches'])
        self.packet['closure']['required_claims'].append('second')
        self.evidence['claims'].append({**self.evidence['claims'][0], 'id': 'second'})
        result = self.inspect()
        self.assertTrue(result['ok'])
        self.assertIn('index_sha256', verify_receipt(result, receipt)['differences'])

    def test_cli_failure_retains_closure_diagnostics_and_creates_no_receipt(self):
        self.evidence['claims'][0].update(status='unsupported', next_step='Recheck.')
        self.write()
        for entry in [['scripts/packet.py'], ['-m', 'scripts.packet']]:
            receipt = self.root / 'receipt.json'
            run = subprocess.run([sys.executable, *entry, str(self.path), '--receipt', str(receipt),
                                  '--target-revision', self.target], cwd=ROOT, capture_output=True, text=True, timeout=5)
            self.assertEqual(run.returncode, 1, run.stderr)
            self.assertFalse(json.loads(run.stdout)['closure']['ready'])
            self.assertFalse(receipt.exists())

    def test_walkthrough_from_source_and_extracted_package(self):
        archive_dir = self.root / 'dist'
        build = subprocess.run([sys.executable, str(ROOT / 'scripts/package.py'), '--output', str(archive_dir)],
                               cwd=self.root, capture_output=True, text=True, timeout=15)
        self.assertEqual(build.returncode, 0, build.stderr)
        with ZipFile(next(archive_dir.glob('*.zip'))) as archive:
            archive.extractall(self.root / 'extracted')
        extracted = next((self.root / 'extracted').iterdir())
        for label, tool_root in [('source', ROOT), ('extracted', extracted)]:
            result = subprocess.run([sys.executable, str(tool_root / 'examples/closure-walkthrough.py'),
                                     '--output', str(self.root / (label + '-run'))], cwd=self.root,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            summary = json.loads(result.stdout)
            self.assertTrue(summary['synthetic'])
            self.assertEqual(summary['checks'], 18)


if __name__ == '__main__':
    unittest.main()
