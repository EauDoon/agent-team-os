import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from scripts.inspect_records import inspect_plan

ROOT = Path(__file__).resolve().parents[1]


class InspectionTests(unittest.TestCase):
    def plan(self):
        return json.loads((ROOT / 'templates/routing-plan.json').read_text())

    def test_readiness_uses_accepted_dependencies_without_mutation(self):
        plan = self.plan()
        before = copy.deepcopy(plan)
        result = inspect_plan(plan, ['requirements'])
        self.assertEqual(result['ready'], ['build'])
        self.assertEqual(result['stages'], [['requirements'], ['build'], ['review']])
        self.assertEqual(result['waiting'], [{'id': 'review', 'unaccepted_dependencies': ['build']}])
        self.assertEqual(plan, before)

    def test_unknown_duplicate_and_premature_acceptance_fail(self):
        for accepted in [['unknown'], ['build'], ['requirements', 'requirements']]:
            with self.assertRaises(ValueError):
                inspect_plan(self.plan(), accepted)

    def test_actual_inspection_cli_in_both_modes(self):
        for entry in [['scripts/inspect_records.py'], ['-m', 'scripts.inspect_records']]:
            result = subprocess.run([sys.executable, *entry, 'plan', 'templates/routing-plan.json',
                                     '--accepted', 'requirements'], cwd=ROOT, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['inspection']['ready'], ['build'])


if __name__ == '__main__':
    unittest.main()
