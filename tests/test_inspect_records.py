import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.inspect_records import inspect_plan, compare_plans

ROOT = Path(__file__).resolve().parents[1]


class InspectionTests(unittest.TestCase):
    def test_plan_comparison_surfaces_scope_changes_and_ignores_order(self):
        before = self.plan()
        after = copy.deepcopy(before)
        after['assignments'].reverse()
        self.assertFalse(compare_plans(before, after)['changed'])
        maker = next(item for item in after['assignments'] if item['id'] == 'build')
        maker['write_resources'].append('tests')
        maker['brief']['access_scope'] = 'Read supplied files; write src and tests.'
        result = compare_plans(before, after)
        self.assertTrue(result['changed'])
        change = result['assignment_changes'][0]
        self.assertEqual(change['write_resources_added'], ['tests'])
        self.assertIn('access_scope', change['brief_changes'])
        self.assertEqual(before['assignments'][1]['write_resources'], ['src'])

    def test_comparison_cli_shows_removed_assignment_and_rejects_invalid_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            before, after = Path(directory) / 'before.json', Path(directory) / 'after.json'
            plan = self.plan()
            before.write_text(json.dumps(plan))
            plan['assignments'].pop()
            after.write_text(json.dumps(plan))
            command = [sys.executable, '-m', 'scripts.inspect_records', 'compare-plans', str(before), str(after)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['inspection']['assignments_removed'], ['review'])
            plan['assignments'][0]['depends_on'] = ['build']
            after.write_text(json.dumps(plan))
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1)

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
