import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.inspect_records import (
    compare_plans,
    compare_evidence,
    inspect_audit,
    inspect_evidence,
    inspect_plan,
    inspect_handoff,
)

ROOT = Path(__file__).resolve().parents[1]


class InspectionTests(unittest.TestCase):
    def test_handoff_pair_requires_matching_version_correlation_and_endpoints(self):
        handoff = {'connect_version': 'agent-team-connect/v0.2', 'type': 'handoff', 'message_id': 'h1',
                   'correlation_id': 'tool-task', 'from': 'owner', 'to': 'maker',
                   'payload': {'role_brief': self.plan()['assignments'][1]['brief']}}
        response = {**handoff, 'type': 'response', 'message_id': 'r1', 'from': 'maker', 'to': 'owner',
                    'payload': {'accepted': True}}
        self.assertTrue(inspect_handoff(handoff, response)['accepted'])
        for field, value in [('correlation_id', 'other'), ('from', 'other'), ('to', 'other'),
                             ('message_id', 'h1'), ('connect_version', 'agent-team-connect/v0.1')]:
            changed = {**response, field: value}
            result = inspect_handoff(handoff, changed)
            self.assertFalse(result['contract_valid'], field)
            self.assertFalse(result['accepted'], field)
        response['payload'] = {'accepted': False, 'refusal_reason': 'Outside scope.', 'next_step': 'Clarify scope.'}
        result = inspect_handoff(handoff, response)
        self.assertTrue(result['contract_valid'])
        self.assertFalse(result['accepted'])
        self.assertEqual(result['next_step'], 'Clarify scope.')

    def test_audit_owner_filter_cannot_hide_global_closure_failures(self):
        report = json.loads((ROOT / 'templates/audit-closure.json').read_text())
        report['findings'][0]['disposition'] = 'open'
        other = copy.deepcopy(report['findings'][0])
        other.update(id='second', owner='analyst', disposition='resolved')
        report['findings'].append(other)
        result = inspect_audit(report, owner='analyst')
        self.assertEqual(result['remediation_queue'], [])
        self.assertEqual(result['total_remediation_count'], 1)
        self.assertFalse(result['closure_ready'])
        self.assertFalse(result['contract_valid'])
        with self.assertRaises(ValueError):
            inspect_audit(report, owner='unknown')

    def test_evidence_freshness_is_explicit_and_flags_unknown_or_future_dates(self):
        ledger = json.loads((ROOT / 'templates/evidence-ledger.json').read_text())
        self.assertEqual(inspect_evidence(ledger, as_of='11-09-2026', max_age_days=2)['freshness']['stale_sources'], [])
        result = inspect_evidence(ledger, as_of='12-09-2026', max_age_days=2)
        self.assertEqual(result['freshness']['stale_sources'], ['brief-a', 'brief-b'])
        self.assertEqual(result['affected_claims'][0]['id'], 'support-hours')
        ledger['sources'][0]['inspected_on'] = 'yesterday'
        ledger['sources'][1]['inspected_on'] = '13-09-2026'
        result = inspect_evidence(ledger, as_of='12-09-2026', max_age_days=2)['freshness']
        self.assertEqual(result['unknown_date_sources'], ['brief-a'])
        self.assertEqual(result['future_sources'], ['brief-b'])
        for options in [{'as_of': '12-09-2026'}, {'max_age_days': 2},
                        {'as_of': '31-02-2026', 'max_age_days': 2},
                        {'as_of': '12-09-2026', 'max_age_days': -1}]:
            with self.assertRaises(ValueError):
                inspect_evidence(ledger, **options)

    def test_evidence_comparison_tracks_revisions_and_claim_edits(self):
        before = json.loads((ROOT / 'templates/evidence-ledger.json').read_text())
        after = copy.deepcopy(before)
        after['sources'].reverse()
        self.assertFalse(compare_evidence(before, after)['changed'])
        after['sources'][0]['revision'] = 'fixture-2'
        result = compare_evidence(before, after)
        self.assertEqual(result['sources_changed'], ['brief-b'])
        self.assertEqual(result['recheck_claims'], ['support-hours'])
        after['claims'][0]['statement'] = 'Revised fictional support claim.'
        self.assertEqual(compare_evidence(before, after)['claims_changed'], ['support-hours'])
        after['sources'].pop(0)
        after['claims'][0].update(status='unsupported', source_ids=[])
        self.assertEqual(compare_evidence(before, after)['sources_removed'], ['brief-b'])

    def test_plan_changes_trace_rework_through_old_and_new_dependencies(self):
        before = self.plan()
        after = copy.deepcopy(before)
        after['assignments'][0]['brief']['task'] = 'Revise the acceptance checks.'
        self.assertEqual(compare_plans(before, after)['recheck_assignments'], ['build', 'requirements', 'review'])
        after = copy.deepcopy(before)
        after['assignments'][1]['depends_on'] = []
        self.assertEqual(compare_plans(before, after)['recheck_assignments'], ['build', 'review'])
        after = copy.deepcopy(before)
        after['objective'] = 'Create a revised fictional internal tool.'
        self.assertEqual(len(compare_plans(before, after)['recheck_assignments']), 3)
        self.assertEqual(compare_plans(before, before)['recheck_assignments'], [])

    def test_ready_batches_observe_declared_parallel_budget(self):
        plan = self.plan()
        for item in plan['assignments']:
            item['depends_on'] = []
        self.assertEqual(inspect_plan(plan)['ready_batches'], [['build', 'requirements'], ['review']])
        plan['budget']['max_parallel'] = 1
        self.assertEqual(inspect_plan(plan)['ready_batches'], [['build'], ['requirements'], ['review']])
        del plan['budget']
        self.assertIsNone(inspect_plan(plan)['ready_batches'])
        self.assertEqual(inspect_plan(self.plan(), blocked=['requirements'])['ready_batches'], [])

    def test_invalidating_an_input_reopens_all_accepted_dependents(self):
        result = inspect_plan(self.plan(), ['requirements', 'build', 'review'], invalidate=['build'])
        self.assertEqual(result['accepted'], ['requirements'])
        self.assertEqual(result['invalidated'], ['build', 'review'])
        self.assertEqual(result['ready'], ['build'])
        for invalid in [['unknown'], ['build', 'build'], ['review']]:
            with self.assertRaises(ValueError):
                inspect_plan(self.plan(), ['requirements', 'build'], invalidate=invalid)

    def test_blocked_work_excludes_downstream_readiness(self):
        plan = self.plan()
        before = copy.deepcopy(plan)
        result = inspect_plan(plan, blocked=['requirements'])
        self.assertEqual(result['ready'], [])
        self.assertEqual(result['blocked'], ['requirements'])
        self.assertEqual(result['blocked_dependents'], ['build', 'review'])
        self.assertEqual(plan, before)
        for blocked in [['missing'], ['build', 'build'], ['requirements']]:
            with self.assertRaises(ValueError):
                inspect_plan(plan, ['requirements'], blocked=blocked)

    def test_audit_inspection_exposes_stale_closure_and_significant_failures(self):
        report = json.loads((ROOT / 'templates/audit-closure.json').read_text())
        self.assertTrue(inspect_audit(report)['closure_ready'])
        result = inspect_audit(report, 'fictional-tool-r3')
        self.assertFalse(result['closure_ready'])
        self.assertEqual(result['remediation_queue'][0]['action'], 'recheck-current-revision')
        report['findings'][0]['disposition'] = 'open'
        result = inspect_audit(report)
        self.assertFalse(result['contract_valid'])
        self.assertFalse(result['closure_ready'])
        self.assertEqual(result['remediation_queue'][0]['owner'], 'maker')

    def test_invalid_audit_cli_keeps_actionable_queue_with_failure_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            report = json.loads((ROOT / 'templates/audit-closure.json').read_text())
            report['findings'][0]['disposition'] = 'open'
            path = Path(directory) / 'audit.json'
            path.write_text(json.dumps(report))
            result = subprocess.run([sys.executable, '-m', 'scripts.inspect_records', 'audit', str(path)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload['ok'])
            self.assertTrue(payload['inspection']['remediation_queue'])

    def test_evidence_impact_preserves_status_and_tracks_unused_sources(self):
        ledger = json.loads((ROOT / 'templates/evidence-ledger.json').read_text())
        extra = copy.deepcopy(ledger['sources'][0])
        extra['id'] = 'unused'
        ledger['sources'].append(extra)
        before = copy.deepcopy(ledger)
        result = inspect_evidence(ledger, ['brief-a'])
        self.assertEqual(result['source_claims']['brief-a'], ['support-hours'])
        self.assertEqual(result['affected_claims'][0]['status'], 'conflicting')
        self.assertEqual(result['unused_sources'], ['unused'])
        self.assertEqual(ledger, before)
        with self.assertRaises(ValueError):
            inspect_evidence(ledger, ['unknown'])

    def test_evidence_cli_shows_reinspection_work(self):
        result = subprocess.run([sys.executable, 'scripts/inspect_records.py', 'evidence',
                                 'templates/evidence-ledger.json', '--changed-source', 'brief-b'],
                                cwd=ROOT, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)['inspection']
        self.assertEqual(report['affected_claims'][0]['id'], 'support-hours')
        self.assertTrue(report['unresolved_claims'][0]['next_step'])

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
