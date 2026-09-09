import copy
import json
from pathlib import Path
import unittest

from scripts.evaluate import summarize

ROOT = Path(__file__).resolve().parents[1]


class EvaluationTests(unittest.TestCase):
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
