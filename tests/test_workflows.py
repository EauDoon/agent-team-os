import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check import check_document
from scripts.workflows import BASELINE_CAPABILITIES, identity_key, negotiate

ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def plan(self):
        return json.loads((ROOT / 'templates/routing-plan.json').read_text())

    def test_evidence_references_and_uncertainty(self):
        ledger = json.loads((ROOT / 'templates/evidence-ledger.json').read_text())
        self.assertEqual(check_document('evidence', ledger), [])
        for refs, status, next_step in [(['missing'], 'supported', ''), ([], 'supported', ''), (['brief-a'], 'conflicting', 'Resolve'), ([], 'unsupported', '')]:
            broken = copy.deepcopy(ledger)
            broken['claims'][0].update(source_ids=refs, status=status, next_step=next_step)
            self.assertTrue(check_document('evidence', broken))

    def test_audit_closure_requires_current_recheck_and_independence(self):
        report = json.loads((ROOT / 'templates/audit-closure.json').read_text())
        self.assertEqual(check_document('audit', report), [])
        for mutation in ['stale', 'open', 'risk', 'author']:
            broken = copy.deepcopy(report)
            if mutation == 'stale':
                broken['target_revision'] = 'next-revision'
            elif mutation == 'author':
                broken['auditor'] = broken['author']
            else:
                broken['findings'][0]['disposition'] = 'open' if mutation == 'open' else 'accepted_risk'
            self.assertTrue(check_document('audit', broken))
        blank = json.loads((ROOT / 'templates/audit-closure.json').read_text())
        blank['target_revision'] = ' \t '
        blank['findings'][0]['checked_revision'] = ' \t '
        errors = check_document('audit', blank)
        self.assertTrue(any('target revision must not be blank' in error for error in errors), errors)
        blank = json.loads((ROOT / 'templates/audit-closure.json').read_text())
        blank['author'] = ' '
        blank['auditor'] = '\t'
        errors = check_document('audit', blank)
        self.assertTrue(any('author and auditor must not be blank' in error for error in errors), errors)

    def test_audit_independence_ignores_case_whitespace_and_compatibility_forms(self):
        report = json.loads((ROOT / 'templates/audit-closure.json').read_text())
        self.assertEqual(check_document('audit', report), [])
        for author, auditor in [('Maker', ' maker'), ('maker', 'MAKER\t'),
                                ('\N{FULLWIDTH LATIN CAPITAL LETTER M}aker', 'maker')]:
            with self.subTest(author=author, auditor=auditor):
                broken = copy.deepcopy(report)
                broken.update(author=author, auditor=auditor)
                self.assertIn('audit: author and independent auditor must be distinct',
                              check_document('audit', broken))
        self.assertEqual(identity_key(' \N{FULLWIDTH LATIN CAPITAL LETTER M}aker\n'), 'maker')
        self.assertNotEqual(identity_key('maker'), identity_key('auditor'))

    def request(self, required=None, offered=None):
        message = {'connect_version': 'agent-team-connect/v0.1', 'type': 'request', 'message_id': 'm1',
                   'correlation_id': 'c1', 'from': 'initiator', 'to': 'orchestrator',
                   'payload': {'objective': 'Fictional objective.', 'completion_test': 'Fictional test.'}}
        if required is not None:
            message['payload']['required_capabilities'] = required
        if offered is not None:
            message['capabilities'] = offered
        return message

    def test_negotiation_sorts_and_limits_to_advertised_capabilities(self):
        baseline = list(BASELINE_CAPABILITIES)
        self.assertEqual(baseline, sorted(baseline))
        self.assertEqual(negotiate(self.request(['evidence-trace', 'bounded-scope'], ['evidence-trace']), baseline),
                         {'accepted': True, 'negotiated_capabilities': ['bounded-scope', 'evidence-trace']})
        # An offered token the Orchestrator lacks is dropped, never a refusal.
        self.assertEqual(negotiate(self.request(None, ['telepathy', 'route']), baseline),
                         {'accepted': True, 'negotiated_capabilities': ['route']})
        self.assertEqual(negotiate(self.request(['audit', 'audit']), ['audit']),
                         {'accepted': True, 'negotiated_capabilities': ['audit']})

    def test_negotiation_refusal_text_is_exact(self):
        self.assertEqual(negotiate(self.request(['route', 'external-write', 'audit']), ['bounded-scope']), {
            'accepted': False,
            'refusal_reason': 'missing required capabilities: audit, external-write, route',
            'next_step': 'authorize or remove: audit, external-write, route'})

    def test_negotiation_rejects_bad_advertised_tokens_and_non_requests(self):
        for advertised in [['Route'], ['route', 'route'], ['bounded_scope'], ['-route'], ['route-'], [''],
                           'route', [1]]:
            with self.subTest(advertised=advertised), self.assertRaises(ValueError):
                negotiate(self.request(), advertised)
        for message in [{**self.request(), 'type': 'handoff'}, [], {**self.request(), 'payload': []},
                        self.request('route'), self.request(None, [3])]:
            with self.subTest(message=message), self.assertRaises(ValueError):
                negotiate(message, ['route'])

    def test_budget_inconsistency_fails(self):
        for key, value in [('max_assignments', 2), ('max_parallel', 4), ('review_reserve', 8), ('total_work_units', -1)]:
            plan = self.plan()
            plan['budget'][key] = value
            self.assertTrue(check_document('plan', plan))
        plan = self.plan()
        del plan['budget']
        self.assertEqual(check_document('plan', plan), [])
        plan = self.plan()
        for key in ('total_work_units', 'review_reserve', 'max_assignments', 'max_parallel', 'max_correction_rounds'):
            plan['budget'][key] = float(plan['budget'][key])
        self.assertEqual(check_document('plan', plan), [])

    def test_valid_plan(self):
        self.assertEqual(check_document('plan', self.plan()), [])

    def test_resource_limits_reject_per_assignment_and_total_excess(self):
        plan = self.plan()
        plan['assignments'][0]['write_resources'] = [str(index) for index in range(257)]
        self.assertTrue(check_document('plan', plan))
        plan = self.plan()
        del plan['budget']
        for index in range(2):
            extra = copy.deepcopy(plan['assignments'][0])
            extra.update(id='extra-' + str(index), output='extra-' + str(index))
            plan['assignments'].append(extra)
        for item in plan['assignments']:
            item['write_resources'] = [item['id'] + '/' + str(index) for index in range(256)]
        self.assertIn('assignments: at most 1024 total write resources are allowed', check_document('plan', plan))
        plan['assignments'].pop()
        self.assertEqual(check_document('plan', plan), [])

    def test_prefix_index_handles_both_orders_same_owner_and_siblings(self):
        for first, second, conflict in [(['src'], ['SRC/main.py'], True),
                                        (['src/main.py'], ['src'], True),
                                        (['src/a'], ['src/b'], False),
                                        (['src', 'src/a'], ['source'], False),
                                        (['src\\a'], ['SRC/a'], True)]:
            plan = self.plan()
            plan['assignments'][0]['write_resources'] = first
            plan['assignments'][1]['write_resources'] = second
            self.assertEqual(bool(check_document('plan', plan)), conflict)

    def test_routing_conflict_diagnostics_are_bounded(self):
        plan = self.plan()
        plan['assignments'][0]['write_resources'] = ['src']
        plan['assignments'][1]['write_resources'] = ['src/' + str(index) for index in range(256)]
        errors = check_document('plan', plan)
        self.assertEqual(len(errors), 33)
        self.assertEqual(errors[-1], 'additional routing diagnostics omitted')

    def test_cli_rejects_large_resource_plan_without_quadratic_work(self):
        plan = self.plan()
        for assignment, prefix in zip(plan['assignments'], ['a', 'b']):
            assignment['write_resources'] = [prefix + str(index) for index in range(10000)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            path.write_text(json.dumps(plan), encoding='utf-8')
            for entry in [['scripts/check.py'], ['-m', 'scripts.check']]:
                result = subprocess.run([sys.executable, *entry, 'plan', str(path), '--json'], cwd=ROOT,
                                        capture_output=True, text=True, timeout=3)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                payload = json.loads(result.stdout)
                self.assertFalse(payload['ok'])
                self.assertLessEqual(len(payload['failures']), 2)

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
