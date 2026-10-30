import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.author import (compose_brief, compose_handoff, compose_request, compose_response, compose_result,
                            compose_status, write_new_json)
from scripts.check import check_document
from scripts.inspect_records import inspect_connection
from scripts.workflows import RecordError, negotiate

ROOT = Path(__file__).resolve().parents[1]
V02 = 'agent-team-connect/v0.2'
# Bytes written by the 0.6.0 composer for these exact arguments. New flags must
# not change what the existing invocations produce.
BRIEF_BYTES = (b'{\n  "role": "Maker",\n  "access_scope": "Supplied files only.",\n'
               b'  "task": "Build the fictional tool.",\n  "evidence": "Supplied requirements.",\n'
               b'  "output_contract": "Tool and acceptance checks.",\n  "stop_condition": "Acceptance or scope gap.",\n'
               b'  "role_brief_version": "agent-team-role-brief/v0.1"\n}\n')
HANDOFF_BYTES = (b'{\n  "connect_version": "agent-team-connect/v0.2",\n  "type": "handoff",\n  "from": "owner",\n'
                 b'  "to": "maker",\n  "message_id": "m1",\n  "correlation_id": "task1",\n  "payload": {\n'
                 b'    "role_brief": {\n      "role": "Maker",\n      "access_scope": "Supplied files only.",\n'
                 b'      "task": "Build the fictional tool.",\n      "evidence": "Supplied requirements.",\n'
                 b'      "output_contract": "Tool and acceptance checks.",\n'
                 b'      "stop_condition": "Acceptance or scope gap.",\n'
                 b'      "role_brief_version": "agent-team-role-brief/v0.1"\n    }\n  }\n}\n')
BRIEF_ARGS = ['--role', 'Maker', '--scope', 'Supplied files only.', '--task', 'Build the fictional tool.',
              '--evidence', 'Supplied requirements.', '--deliver', 'Tool and acceptance checks.',
              '--stop', 'Acceptance or scope gap.']


def author(args: list[str], *, module_mode: bool = False) -> tuple[int, dict]:
    entry = ['-m', 'scripts.author'] if module_mode else ['scripts/author.py']
    result = subprocess.run([sys.executable, *entry, *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
    return result.returncode, json.loads(result.stdout)


class MessageAuthoringTests(unittest.TestCase):
    def request(self, **overrides):
        values = dict(constraints=['Use only the supplied briefs.'], required=['bounded-scope'],
                      offered=['evidence-trace'])
        values.update(overrides)
        return compose_request('initiator', 'orchestrator', 'm1', 'c1', 'Compare the supplied briefs.',
                               'Every conclusion cites a brief.', **values)

    def test_request_writes_offer_to_envelope_and_requirements_to_payload(self):
        request = self.request()
        self.assertEqual(check_document('connect', request), [])
        self.assertEqual(request['capabilities'], ['evidence-trace'])
        self.assertEqual(request['payload']['required_capabilities'], ['bounded-scope'])
        self.assertEqual(request['payload']['constraints'], ['Use only the supplied briefs.'])
        bare = self.request(constraints=None, required=None, offered=None)
        self.assertNotIn('capabilities', bare)
        self.assertEqual(set(bare['payload']), {'objective', 'completion_test'})
        for overrides, reason in ((dict(required=['Bounded-Scope']), 'required capabilities must be lowercase'),
                                  (dict(offered=['audit', 'audit']), 'offered capabilities must be unique'),
                                  (dict(required=[' ']), 'required capabilities must be lowercase'),
                                  (dict(constraints=['  ']), 'request constraints must not be blank')):
            with self.subTest(overrides=overrides), self.assertRaises(RecordError) as raised:
                self.request(**overrides)
            self.assertIn(reason, raised.exception.reason)
        with self.assertRaises(RecordError):
            compose_request('initiator', 'orchestrator', 'm1', 'c1', ' ', 'test')

    def test_response_is_the_negotiation_reply_with_reversed_endpoints(self):
        request = self.request()
        for advertised in (['bounded-scope', 'evidence-trace', 'route'], ['route']):
            response = compose_response(request, advertised, 'm2')
            self.assertEqual(response['payload'], negotiate(request, advertised))
            self.assertEqual((response['from'], response['to'], response['correlation_id']),
                             ('orchestrator', 'initiator', 'c1'))
            self.assertEqual(check_document('connect', response), [])
        self.assertEqual(compose_response(request, None, 'm2')['payload']['refusal_reason'],
                         'missing required capabilities: bounded-scope')
        legacy = dict(request, connect_version='agent-team-connect/v0.1')
        handoff = compose_handoff('orchestrator', 'maker', 'm3', 'c1', self.brief())
        for record in (legacy, handoff, {}, [], dict(request, payload={})):
            with self.assertRaises(RecordError) as raised:
                compose_response(record, ['bounded-scope'], 'm2')
            self.assertEqual(raised.exception.reason, 'a response needs a conforming v0.2 request')
        with self.assertRaises(RecordError):
            compose_response(request, ['Route'], 'm2')

    def test_status_requires_a_decision_for_a_gap(self):
        gap = compose_status('maker', 'orchestrator', 'm4', 'c1', 'gap', gaps=['Brief C is missing.'],
                             decision_needed='Proceed without brief C, or supply it.')
        self.assertEqual(check_document('connect', gap), [])
        done = compose_status('maker', 'orchestrator', 'm5', 'c1', 'done', evidence_inspected=['brief-a.txt'])
        self.assertEqual(done['payload'], {'state': 'done', 'evidence_inspected': ['brief-a.txt']})
        for kwargs, reason in ((dict(state='gap'), 'a gap status needs the decision required to continue'),
                               (dict(state='gap', decision_needed=' '), 'a decision needed must not be blank'),
                               (dict(state='working', gaps=['']), 'status gaps must not be blank'),
                               (dict(state='done', evidence_inspected=['a', 'a']),
                                'inspected evidence identifiers must be unique'),
                               (dict(state='paused'), 'message does not conform')):
            state = kwargs.pop('state')
            with self.subTest(state=state, kwargs=kwargs), self.assertRaises(RecordError) as raised:
                compose_status('maker', 'orchestrator', 'm4', 'c1', state, **kwargs)
            self.assertEqual(raised.exception.reason, reason)

    def test_result_records_the_negotiated_set_from_one_source(self):
        request = self.request()
        accepted = compose_response(request, ['bounded-scope', 'evidence-trace'], 'm2')
        refused = compose_response(request, ['route'], 'm2')
        result = compose_result('orchestrator', 'initiator', 'm5', 'c1', 'Done.', True, response=accepted,
                                evidence_basis=['table'], assumptions=['Equal weights.'], risks=['C unverified.'])
        self.assertEqual(result['capabilities'], ['bounded-scope', 'evidence-trace'])
        self.assertEqual(set(result['payload']), {'summary', 'request_satisfied', 'evidence_basis', 'assumptions',
                                                  'unresolved_risks'})
        explicit = compose_result('orchestrator', 'initiator', 'm5', 'c1', 'Done.', False,
                                  capabilities=['evidence-trace', 'bounded-scope'])
        self.assertEqual(explicit['capabilities'], ['bounded-scope', 'evidence-trace'])
        empty = dict(accepted, payload={'accepted': True, 'negotiated_capabilities': []})
        self.assertEqual(compose_result('orchestrator', 'initiator', 'm5', 'c1', 'Done.', True,
                                        response=empty)['capabilities'], [])
        cases = [(dict(response=refused), 'accepted v0.2 response'),
                 (dict(response=dict(accepted, payload={'accepted': True})), 'accepted v0.2 response'),
                 (dict(response=dict(accepted, correlation_id='c2')), 'result correlation must match the response'),
                 (dict(response=dict(accepted, to='someone')), 'result endpoints must match the response'),
                 (dict(), 'exactly one capability source'),
                 (dict(response=accepted, capabilities=['audit']), 'exactly one capability source'),
                 (dict(capabilities=['Audit']), 'result capabilities must be lowercase')]
        for kwargs, reason in cases:
            with self.subTest(reason=reason), self.assertRaises(RecordError) as raised:
                compose_result('orchestrator', 'initiator', 'm5', 'c1', 'Done.', True, **kwargs)
            self.assertIn(reason, raised.exception.reason)

    def brief(self, **kwargs):
        return compose_brief('Maker', 'Supplied files only.', 'Build the fictional tool.', 'Supplied requirements.',
                             'Tool and acceptance checks.', 'Acceptance or scope gap.', **kwargs)

    def test_prohibitions_and_handoff_evidence_are_written_in_order(self):
        brief = self.brief(prohibited=['No external writes.', 'No deployment.'])
        self.assertEqual(brief['prohibited_actions'], ['No external writes.', 'No deployment.'])
        self.assertNotIn('prohibited_actions', self.brief())
        handoff = compose_handoff('owner', 'maker', 'm1', 'task1', brief, ['brief-a.txt', 'brief-b.txt'])
        self.assertEqual(handoff['payload']['evidence'], ['brief-a.txt', 'brief-b.txt'])
        self.assertEqual(check_document('connect', handoff), [])
        with self.assertRaises(RecordError):
            self.brief(prohibited=['  '])
        for evidence in (['a', ' '], ['a', 'a']):
            with self.assertRaises(RecordError):
                compose_handoff('owner', 'maker', 'm1', 'task1', brief, evidence)

    def test_existing_invocations_keep_their_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code, _ = author(['brief', *BRIEF_ARGS, '--output', str(root / 'brief.json')])
            self.assertEqual(code, 0)
            self.assertEqual((root / 'brief.json').read_bytes(), BRIEF_BYTES)
            code, _ = author(['handoff', '--version', V02, '--from', 'owner', '--to', 'maker', '--message-id', 'm1',
                              '--correlation-id', 'task1', '--brief', str(root / 'brief.json'),
                              '--output', str(root / 'handoff.json')])
            self.assertEqual(code, 0)
            self.assertEqual((root / 'handoff.json').read_bytes(), HANDOFF_BYTES)
            code, _ = author(['brief', *BRIEF_ARGS, '--prohibit', 'No external writes.',
                              '--output', str(root / 'prohibited.json')], module_mode=True)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads((root / 'prohibited.json').read_text(encoding='utf-8'))['prohibited_actions'],
                             ['No external writes.'])

    def test_authored_exchange_passes_the_connection_inspector_in_both_modes(self):
        advertised = ['bounded-scope', 'evidence-trace']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_new_json(root / 'brief.json', self.brief())
            for module_mode in (False, True):
                folder = root / ('module' if module_mode else 'script')
                folder.mkdir()
                envelope = ['--version', V02, '--correlation-id', 'c1']
                steps = [
                    ('request', ['request', *envelope, '--from', 'initiator', '--to', 'orchestrator',
                                 '--message-id', 'm1', '--objective', 'Compare the supplied briefs.',
                                 '--completion-test', 'Every conclusion cites a brief.', '--require', 'bounded-scope',
                                 '--offer', 'evidence-trace']),
                    ('response', ['response', '--version', V02, '--request', str(folder / 'request.json'),
                                  '--advertise', advertised[0], '--advertise', advertised[1], '--message-id', 'm2']),
                    ('handoff', ['handoff', *envelope, '--from', 'orchestrator', '--to', 'maker', '--message-id', 'm3',
                                 '--brief', str(root / 'brief.json'), '--evidence', 'brief-a.txt']),
                    ('status', ['status', *envelope, '--from', 'maker', '--to', 'orchestrator', '--message-id', 'm4',
                                '--state', 'done', '--evidence-inspected', 'brief-a.txt']),
                    ('result', ['result', *envelope, '--from', 'orchestrator', '--to', 'initiator',
                                '--message-id', 'm5', '--summary', 'The comparison is complete.', '--satisfied', 'yes',
                                '--response', str(folder / 'response.json')]),
                ]
                for name, args in steps:
                    code, payload = author([*args, '--output', str(folder / f'{name}.json')], module_mode=module_mode)
                    self.assertEqual((code, payload), (0, {'ok': True, 'kind': name}))
                    code, payload = author([*args, '--output', str(folder / f'{name}.json')], module_mode=module_mode)
                    self.assertEqual(code, 1)
                messages = [json.loads((folder / f'{name}.json').read_text(encoding='utf-8')) for name, _ in steps]
                report = inspect_connection(messages, advertised, require_closed=True)
                self.assertTrue(report['contract_valid'], report['failures'])
                self.assertEqual(report['open_handoffs'], [])
            code, payload = author(['status', '--version', V02, '--from', 'maker', '--to', 'orchestrator',
                                    '--message-id', 'm6', '--correlation-id', 'c1', '--state', 'gap',
                                    '--output', str(root / 'gap.json')])
            self.assertEqual((code, payload['reason']), (1, 'a gap status needs the decision required to continue'))
            self.assertFalse((root / 'gap.json').exists())


if __name__ == '__main__':
    unittest.main()
