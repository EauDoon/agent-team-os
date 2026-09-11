import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.inspect_records import (
    compare_plans,
    inspect_audit,
    inspect_evidence,
    inspect_plan,
)

ROOT = Path(__file__).resolve().parents[1]


class InspectionTests(unittest.TestCase):
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
