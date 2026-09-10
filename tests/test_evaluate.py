import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate import markdown_cell, summarize

ROOT = Path(__file__).resolve().parents[1]


class EvaluationTests(unittest.TestCase):
    def test_markdown_cells_escape_markup_and_control_characters(self):
        escaped = markdown_cell('<script>|[open](https://example.invalid)\n\x1b')
        self.assertNotIn('<script>', escaped)
        self.assertNotIn('[open](', escaped)
        self.assertNotIn('\n', escaped)
        self.assertNotIn('\x1b', escaped)
        self.assertIn('\\|', escaped)

    def test_report_export_pins_input_bytes_and_refuses_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'run.json', Path(directory) / 'report.md'
            source.write_text(json.dumps(self.run, indent=1), encoding='utf-8')
            command = [sys.executable, 'scripts/evaluate.py', str(source), '--format', 'markdown', '--output', str(target)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = target.read_text(encoding='utf-8')
            self.assertIn('Status: synthetic', report)
            self.assertIn(hashlib.sha256(source.read_bytes()).hexdigest(), report)
            original = target.read_bytes()
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(target.read_bytes(), original)

    def test_task_details_reconcile_to_totals_without_hiding_unverified_checks(self):
        self.run['records'][1]['checks'] = ['fail', 'unverified']
        result = summarize(self.run, self.suite)
        self.assertEqual(len(result['tasks']), 6)
        first = result['tasks'][0]
        self.assertEqual(first['checks'][1]['current'], 'unverified')
        self.assertEqual(first['checks'][1]['solo'], 'pass')
        self.assertEqual(first['checks'][1]['criterion'], self.suite['tasks'][0]['acceptance'][1])
        self.assertEqual(first['passed_check_difference_current_minus_solo'], -2)
        self.assertEqual(sum(task['passed_check_difference_current_minus_solo'] for task in result['tasks']),
                         result['passed_check_difference_current_minus_solo'])

    def test_cli_exports_actual_per_task_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'run.json'
            path.write_text(json.dumps(self.run), encoding='utf-8')
            result = subprocess.run([sys.executable, '-m', 'scripts.evaluate', str(path)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['tasks'][0]['task_id'], self.suite['tasks'][0]['id'])
            self.assertEqual(report['tasks'][0]['checks'][0]['solo'], 'pass')

    def setUp(self):
        self.suite = json.loads((ROOT / 'evals/tasks.json').read_text())
        self.run = {'run_version': 'agent-team-run/v0.1', 'suite_version': self.suite['suite_version'],
                    'status': 'synthetic', 'runner': 'runner', 'reviewer': 'reviewer', 'records': []}
        for task in self.suite['tasks']:
            for arm in ['solo', 'current']:
                self.run['records'].append({'task_id': task['id'], 'arm': arm,
                    'output_revision': 'fixture-o1', 'review_evidence': 'Synthetic check record.', 'configuration': 'Synthetic runner configuration.',
                    'prompt_revision': 'fixture-p1', 'evidence_revision': 'fixture-e1',
                    'checks': ['pass'] * len(task['acceptance']), 'tokens': 10, 'duration_seconds': 2.5})

    def test_known_totals_and_synthetic_label(self):
        result = summarize(self.run, self.suite)
        self.assertEqual(result['status'], 'synthetic')
        self.assertEqual(result['arms']['solo']['passed'], 12)
        self.assertEqual(result['arms']['current']['tokens'], 60)
        self.assertEqual(result['passed_check_difference_current_minus_solo'], 0)

    def test_unverified_is_never_a_pass(self):
        self.run['records'][0]['checks'][0] = 'unverified'
        result = summarize(self.run, self.suite)
        self.assertEqual(result['arms']['solo']['passed'], 11)
        self.assertEqual(result['arms']['solo']['unverified'], 1)

    def test_nonfinite_and_oversized_in_memory_measurements_fail(self):
        for field, value in [('duration_seconds', float('nan')),
                             ('duration_seconds', float('inf')),
                             ('duration_seconds', -float('inf')),
                             ('duration_seconds', 10 ** 400), ('tokens', 10 ** 400)]:
            run = copy.deepcopy(self.run)
            run['records'][0][field] = value
            with self.assertRaises(ValueError):
                summarize(run, self.suite)

    def test_finite_measurements_with_overflowing_totals_fail(self):
        for field, value in [('duration_seconds', 1e308), ('tokens', 2 ** 53 - 1)]:
            run = copy.deepcopy(self.run)
            for row in run['records']:
                row[field] = value
            with self.assertRaises(ValueError):
                summarize(run, self.suite)

    def test_cli_rejects_overflow_with_strict_json_in_both_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'run.json'
            for field, value in [('duration_seconds', 1e308), ('duration_seconds', 10 ** 400), ('tokens', 10 ** 400)]:
                run = copy.deepcopy(self.run)
                for row in run['records']:
                    row[field] = value
                path.write_text(json.dumps(run, allow_nan=False), encoding='utf-8')
                for entry in [['scripts/evaluate.py'], ['-m', 'scripts.evaluate']]:
                    result = subprocess.run([sys.executable, *entry, str(path)], cwd=ROOT,
                                            capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    def reject_constant(value):
                        self.fail('non-JSON constant emitted: ' + value)
                    self.assertFalse(json.loads(result.stdout, parse_constant=reject_constant)['ok'])
                    self.assertEqual(result.stderr, '')

    def test_incomplete_unpaired_duplicate_and_invalid_scores_fail(self):
        for mutation in ['missing', 'duplicate', 'evidence', 'checks', 'negative', 'reviewer']:
            run = copy.deepcopy(self.run)
            if mutation == 'missing':
                run['records'].pop()
            elif mutation == 'duplicate':
                run['records'].append(run['records'][0])
            elif mutation == 'evidence':
                run['records'][0]['evidence_revision'] = 'different'
            elif mutation == 'checks':
                run['records'][0]['checks'] = ['pass']
            elif mutation == 'reviewer':
                run['reviewer'] = run['runner']
            else:
                run['records'][0]['tokens'] = -1
            with self.assertRaises(ValueError, msg=mutation):
                summarize(run, self.suite)


if __name__ == '__main__':
    unittest.main()
