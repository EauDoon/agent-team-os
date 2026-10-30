import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.inspect_records import inspect_dispatch
from scripts.workflows import RecordError

ROOT = Path(__file__).resolve().parents[1]
WIDER_SCOPE = 'Write src and deploy configuration. No external actions.'


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((ROOT / 'templates/routing-plan.json').read_text(encoding='utf-8'))
        self.briefs = {item['id']: item['brief'] for item in self.plan['assignments']}

    def handoff(self, assignment, to, message_id, *, brief=None, version='agent-team-connect/v0.2'):
        role_brief = copy.deepcopy(self.briefs[assignment] if brief is None else brief)
        if version == 'agent-team-connect/v0.2':
            role_brief['role_brief_version'] = 'agent-team-role-brief/v0.1'
        return {'connect_version': version, 'type': 'handoff', 'from': 'orchestrator', 'to': to,
                'message_id': message_id, 'correlation_id': 'c1', 'payload': {'role_brief': role_brief}}

    def failures(self, report):
        return [failure['failure'] for failure in report['failures']]

    def test_exact_plan_briefs_bind_to_their_assignments(self):
        handoffs = [self.handoff('requirements', 'analyst-1', 'h1'),
                    self.handoff('build', 'maker-1', 'h2', version='agent-team-connect/v0.1'),
                    self.handoff('review', 'auditor-1', 'h3')]
        report = inspect_dispatch(self.plan, handoffs, ['requirements', 'build'])
        self.assertTrue(report['contract_valid'], report['failures'])
        self.assertEqual([(item['assignment'], item['to']) for item in report['dispatched']],
                         [('requirements', 'analyst-1'), ('build', 'maker-1'), ('review', 'auditor-1')])
        self.assertEqual(report['recipients'], {'build': ['maker-1'], 'requirements': ['analyst-1'],
                                                'review': ['auditor-1']})
        self.assertEqual([item['observation'] for item in report['observations']],
                         ['already_accepted', 'already_accepted'])
        self.assertIn('does not authorize', report['note'])

    def test_widened_scope_fails_and_names_only_the_field(self):
        brief = copy.deepcopy(self.briefs['build'])
        brief['access_scope'] = WIDER_SCOPE
        report = inspect_dispatch(self.plan, [self.handoff('build', 'maker-1', 'h1', brief=brief)], ['requirements'])
        self.assertFalse(report['contract_valid'])
        self.assertEqual(self.failures(report), ['role brief matches no planned assignment'])
        self.assertEqual(report['failures'][0]['candidates'], [{'assignment': 'build',
                                                                'differing_fields': ['access_scope']}])
        self.assertNotIn(WIDER_SCOPE, json.dumps(report))
        self.assertEqual(report['dispatched'], [])
        prohibited = copy.deepcopy(self.briefs['build'])
        prohibited['prohibited_actions'] = ['No deployment.']
        added = inspect_dispatch(self.plan, [self.handoff('build', 'maker-1', 'h1', brief=prohibited)],
                                 ['requirements'])
        self.assertEqual(added['failures'][0]['candidates'][0]['differing_fields'], ['prohibited_actions'])
        renamed = copy.deepcopy(self.briefs['build'])
        renamed['role'] = 'Builder'
        report = inspect_dispatch(self.plan, [self.handoff('build', 'maker-1', 'h1', brief=renamed)], ['requirements'])
        self.assertEqual(report['failures'][0]['candidates'], [])

    def test_one_owner_per_assignment(self):
        handoffs = [self.handoff('build', 'maker-2', 'h1'), self.handoff('build', 'maker-3', 'h2')]
        report = inspect_dispatch(self.plan, handoffs, ['requirements'])
        self.assertEqual(self.failures(report), ['assignment is handed to more than one recipient'])
        self.assertEqual(report['recipients'], {'build': ['maker-2', 'maker-3']})
        again = inspect_dispatch(self.plan, [self.handoff('build', 'maker-2', 'h1'),
                                             self.handoff('build', 'maker-2', 'h2')], ['requirements'])
        self.assertTrue(again['contract_valid'], again['failures'])
        self.assertEqual([item['observation'] for item in again['observations']], ['redispatched'])

    def test_dependencies_and_blocks_gate_dispatch(self):
        early = inspect_dispatch(self.plan, [self.handoff('build', 'maker-1', 'h1')])
        self.assertEqual(self.failures(early), ['assignment is dispatched before its dependencies are accepted'])
        self.assertEqual(early['failures'][0]['unaccepted_dependencies'], ['requirements'])
        self.assertEqual(early['undispatched_ready'], ['requirements'])
        self.assertTrue(inspect_dispatch(self.plan, [self.handoff('build', 'maker-1', 'h1')],
                                         ['requirements'])['contract_valid'])
        held = inspect_dispatch(self.plan, [self.handoff('requirements', 'analyst-1', 'h1')],
                                blocked=['requirements'])
        self.assertEqual(self.failures(held), ['assignment is dispatched while blocked'])
        for accepted, blocked, reason in ((['missing'], [], 'unknown accepted assignment'),
                                          (['build'], [], 'accepted assignments must include their accepted dependencies'),
                                          ([], ['missing'], 'blocked IDs must be unique known unaccepted assignments')):
            with self.assertRaises(RecordError) as raised:
                inspect_dispatch(self.plan, [self.handoff('requirements', 'analyst-1', 'h1')], accepted,
                                 blocked=blocked)
            self.assertEqual(raised.exception.reason, reason)

    def test_duplicate_plan_briefs_are_ambiguous(self):
        plan = copy.deepcopy(self.plan)
        plan['assignments'][2]['brief'] = copy.deepcopy(plan['assignments'][1]['brief'])
        report = inspect_dispatch(plan, [self.handoff('build', 'maker-1', 'h1')], ['requirements'])
        self.assertEqual(self.failures(report), ['role brief matches more than one planned assignment'])
        self.assertEqual([item['assignment'] for item in report['failures'][0]['candidates']], ['build', 'review'])

    def test_messages_must_be_conforming_handoffs(self):
        status = {'connect_version': 'agent-team-connect/v0.2', 'type': 'status', 'from': 'maker-1',
                  'to': 'orchestrator', 'message_id': 's1', 'correlation_id': 'c1', 'payload': {'state': 'done'}}
        broken = self.handoff('requirements', 'analyst-1', 'h2')
        del broken['payload']['role_brief']['task']
        report = inspect_dispatch(self.plan, [self.handoff('requirements', 'analyst-1', 'h1'), status, broken])
        self.assertEqual(self.failures(report), ['message is not a handoff',
                                                 'message does not conform to its declared connect version'])
        self.assertEqual(report['dispatched'], [])
        with self.assertRaises(RecordError):
            inspect_dispatch({'plan_version': 'agent-team-plan/v0.1'}, [status])

    def test_redelivery_and_conflict(self):
        first = self.handoff('requirements', 'analyst-1', 'h1')
        changed = self.handoff('requirements', 'analyst-2', 'h1')
        report = inspect_dispatch(self.plan, [first, copy.deepcopy(first)])
        self.assertTrue(report['contract_valid'])
        self.assertEqual(report['redelivered'], [{'position': 2, 'message_id': 'h1'}])
        self.assertEqual(len(report['dispatched']), 1)
        conflict = inspect_dispatch(self.plan, [first, changed])
        self.assertEqual(self.failures(conflict), ['message_id was delivered again with different content'])

    def test_limits(self):
        handoff = self.handoff('requirements', 'analyst-1', 'h1')
        self.assertTrue(inspect_dispatch(self.plan, [handoff] * 256)['contract_valid'])
        for handoffs in ([handoff] * 257, []):
            with self.assertRaises(RecordError):
                inspect_dispatch(self.plan, handoffs)

    def test_cli_in_script_and_module_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for index, (assignment, to) in enumerate((('build', 'maker-2'), ('build', 'maker-3')), 1):
                path = root / f'h{index}.json'
                path.write_text(json.dumps(self.handoff(assignment, to, f'h{index}')), encoding='utf-8')
                paths.append(str(path))
            for entry in (['scripts/inspect_records.py'], ['-m', 'scripts.inspect_records']):
                for args, code in (([paths[0], '--accepted', 'requirements'], 0),
                                   (paths + ['--accepted', 'requirements'], 1)):
                    result = subprocess.run([sys.executable, *entry, 'dispatch', 'templates/routing-plan.json', *args],
                                            cwd=ROOT, capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                    payload = json.loads(result.stdout)
                    self.assertEqual(payload['ok'], code == 0)
                    self.assertEqual(set(payload['inspection']), {
                        'contract_valid', 'route', 'dispatched', 'recipients', 'undispatched_ready', 'redelivered',
                        'failure_count', 'failures', 'observations', 'note'})
            result = subprocess.run([sys.executable, 'scripts/inspect_records.py', 'dispatch',
                                     'templates/routing-plan.json', paths[0], '--accepted', 'missing'],
                                    cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual((result.returncode, json.loads(result.stdout)['reason']),
                             (1, 'unknown accepted assignment'))


if __name__ == '__main__':
    unittest.main()
