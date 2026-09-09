import copy
import json
from pathlib import Path
import unittest

from scripts.check import check_document

ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def plan(self):
        return json.loads((ROOT / 'templates/routing-plan.json').read_text())

    def test_valid_plan(self):
        self.assertEqual(check_document('plan', self.plan()), [])

    def test_routing_cycles_unknown_dependencies_and_conflicting_owners(self):
        for mutation in ['cycle', 'unknown', 'owner', 'output', 'solo']:
            plan = self.plan()
            first, second = plan['assignments'][:2]
            if mutation == 'cycle':
                first['depends_on'] = [second['id']]
            elif mutation == 'unknown':
                first['depends_on'] = ['missing']
            elif mutation == 'owner':
                first['write_resources'] = ['src']
                second['write_resources'] = ['SRC/main.py']
            elif mutation == 'output':
                second['output'] = first['output']
            else:
                plan['route'] = 'solo'
            self.assertTrue(check_document('plan', plan), mutation)

    def test_malformed_plan_does_not_run_semantic_checks(self):
        self.assertTrue(check_document('plan', {'assignments': [None]}))


if __name__ == '__main__':
    unittest.main()
