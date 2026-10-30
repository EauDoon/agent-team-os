import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import inspect_records
from scripts.inspect_records import inspect_connection, load_records
from scripts.workflows import BASELINE_CAPABILITIES, RecordError, distinct_messages

ROOT = Path(__file__).resolve().parents[1]
WITHOUT_SCOPE = [token for token in BASELINE_CAPABILITIES if token != 'bounded-scope']


def examples() -> dict:
    spec = (ROOT / 'connect.md').read_text(encoding='utf-8')
    found = {}
    for block in re.findall(r'```json\s*(.*?)```', spec, flags=re.DOTALL):
        message = json.loads(block)
        found[message['message_id']] = message
    return found


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.examples = examples()

    def m(self, source_id, **changes):
        message = copy.deepcopy(self.examples[source_id])
        for key, value in changes.items():
            if value is None:
                message.pop(key, None)
            else:
                message[key] = value
        return message

    def accepted(self):
        return [self.m(f'msg-000{index}') for index in range(1, 6)]

    def rules(self, report):
        return [failure['rule'] for failure in report['failures']]

    def test_connect_md_paths_conform_and_report_participants(self):
        for advertised in (None, list(BASELINE_CAPABILITIES)):
            report = inspect_connection(self.accepted(), advertised, require_closed=True)
            self.assertTrue(report['contract_valid'], report['failures'])
            self.assertEqual((report['initiator'], report['orchestrator']), ('vendor-intake-agent', 'orchestrator'))
            self.assertEqual(report['negotiated'], ['bounded-scope', 'evidence-trace'])
            self.assertEqual(report['handoffs'], [{'position': 3, 'message_id': 'msg-0003', 'to': 'scout-1',
                                                   'role': 'Scout'}])
            self.assertEqual(report['open_handoffs'], ['scout-1'])
            self.assertTrue(report['closed'])
            self.assertTrue(report['request_satisfied'])
            self.assertEqual([item['observation'] for item in report['observations']],
                             ['open_handoffs', 'satisfied_with_open_gaps'])
        refused = inspect_connection([self.m('msg-0001'), self.m('msg-0006')], WITHOUT_SCOPE, require_closed=True)
        self.assertTrue(refused['contract_valid'], refused['failures'])
        self.assertEqual((refused['accepted'], refused['closed'], refused['negotiated']), (False, True, None))
        note = inspect_connection(self.accepted())['note']
        self.assertIn('not to a specific handoff', note)
        self.assertIn('grants no permission', note)

    def test_each_lifecycle_rule_fails_on_its_own(self):
        accepted = self.accepted()
        incomplete = self.m('msg-0003')
        del incomplete['payload']['role_brief']['task']
        changed = self.m('msg-0003')
        changed['payload']['evidence'] = ['brief-a.txt']
        bare = self.m('msg-0002')
        bare['payload'] = {'accepted': True}
        unsorted = self.m('msg-0002')
        unsorted['payload']['negotiated_capabilities'] = ['evidence-trace', 'bounded-scope']
        widened = self.m('msg-0002')
        widened['payload']['negotiated_capabilities'] = ['audit', 'bounded-scope', 'evidence-trace']
        # A 0.6.0-style result: correct payload, no negotiated set in the envelope.
        legacy_result = self.m('msg-0005', capabilities=None)
        late = self.m('msg-0004', message_id='msg-0007')
        second_result = self.m('msg-0005', message_id='msg-0008')
        cases = {
            'R1': [self.m('msg-0001'), self.m('msg-0002'), incomplete],
            'R2': accepted[:3] + [self.m('msg-0004', connect_version='agent-team-connect/v0.2')],
            'R3': accepted[:3] + [self.m('msg-0004', correlation_id='conn-43')],
            'R4': accepted[:3] + [changed],
            'R5': [self.m('msg-0002'), self.m('msg-0001')],
            'R6': [self.m('msg-0001'), self.m('msg-0003')],
            'R7': [self.m('msg-0001'), bare],
            'R8': [self.m('msg-0001'), self.m('msg-0006'), self.m('msg-0003')],
            'R9': accepted[:2] + [self.m('msg-0003', **{'from': 'analyst-1'})],
            'R10': accepted[:3] + [self.m('msg-0004', **{'from': 'scout-2'})],
            'R11': accepted + [late],
            'R12': accepted[:4] + [legacy_result],
        }
        for rule, messages in cases.items():
            with self.subTest(rule=rule):
                report = inspect_connection(messages)
                self.assertFalse(report['contract_valid'])
                self.assertEqual(set(self.rules(report)), {rule}, report['failures'])
                self.assertEqual(report['failure_count'], len(report['failures']))
        closure = inspect_connection(accepted[:4], require_closed=True)
        self.assertEqual(self.rules(closure), ['R13'])
        self.assertTrue(inspect_connection(accepted[:4])['contract_valid'])
        for messages in ([self.m('msg-0001'), unsorted], [self.m('msg-0001'), widened]):
            self.assertEqual(self.rules(inspect_connection(messages)), ['R7'])
        two_results = inspect_connection(accepted + [second_result])
        self.assertEqual([item['failure'] for item in two_results['failures']], ['a connection has at most one result'])
        second_request = inspect_connection(accepted[:2] + [self.m('msg-0001', message_id='msg-0009')])
        self.assertIn('a connection has exactly one request', [item['failure'] for item in second_request['failures']])
        misrouted = inspect_connection([self.m('msg-0001'), self.m('msg-0002', to='scout-1')])
        self.assertEqual(self.rules(misrouted), ['R6'])
        failure = closure['failures'][0]
        self.assertEqual((failure['position'], failure['message_id']), (4, 'msg-0004'))

    def test_lifecycle_rules_wait_until_every_message_conforms(self):
        report = inspect_connection([self.m('msg-0002'), {'type': 'request'}])
        self.assertEqual(self.rules(report), ['R1'])
        self.assertEqual(report['failures'][0], {'rule': 'R1', 'position': 2, 'message_id': None,
                                                 'failure': 'message does not conform to its declared connect version'})
        self.assertIsNone(report['initiator'])

    def test_redelivery_is_skipped_and_conflict_is_reported(self):
        accepted = self.accepted()
        report = inspect_connection(accepted[:2] + [accepted[1]] + accepted[2:])
        self.assertTrue(report['contract_valid'], report['failures'])
        self.assertEqual(report['redelivered'], [{'position': 3, 'message_id': 'msg-0002'}])
        self.assertEqual((report['messages'], report['distinct_messages']), (6, 5))
        rebuilt = self.m('msg-0002')
        rebuilt['payload']['negotiated_capabilities'] = ['bounded-scope', 'evidence-trace']
        distinct, redelivered, conflicts = distinct_messages([accepted[1], rebuilt])
        self.assertEqual((len(distinct), len(redelivered), conflicts), (1, 1, []))
        float_context = self.m('msg-0001')
        float_context['payload']['context'] = {'count': 1}
        same_number = copy.deepcopy(float_context)
        same_number['payload']['context'] = {'count': 1.0}
        boolean = copy.deepcopy(float_context)
        boolean['payload']['context'] = {'count': True}
        self.assertEqual(distinct_messages([float_context, same_number])[1], [{'position': 2, 'message_id': 'msg-0001'}])
        self.assertEqual(distinct_messages([float_context, boolean])[2], [{'position': 2, 'message_id': 'msg-0001'}])

    def test_advertised_set_holds_the_response_to_the_rules(self):
        scope = self.m('msg-0006')
        scope['payload'] = {'accepted': False, 'refusal_reason': 'The objective needs records no brief supplies.',
                            'next_step': 'Supply the records or narrow the objective.'}
        allowed = inspect_connection([self.m('msg-0001'), scope], list(BASELINE_CAPABILITIES))
        self.assertTrue(allowed['contract_valid'], allowed['failures'])
        self.assertEqual([item['observation'] for item in allowed['observations']], ['non_capability_refusal'])
        wrong_text = self.m('msg-0006')
        wrong_text['payload']['next_step'] = 'Authorize bounded-scope.'
        claimed = self.m('msg-0006')
        for messages, advertised, failure in (
                ([self.m('msg-0001'), wrong_text], WITHOUT_SCOPE, 'differs from the negotiation rules'),
                ([self.m('msg-0001'), self.m('msg-0002')], WITHOUT_SCOPE, 'differs from the negotiation rules'),
                ([self.m('msg-0001'), claimed], list(BASELINE_CAPABILITIES), 'names missing capabilities')):
            report = inspect_connection(messages, advertised)
            self.assertEqual(self.rules(report), ['R7'])
            self.assertIn(failure, report['failures'][0]['failure'])
        for advertised in (['Route'], ['route', 'route'], 'route'):
            with self.assertRaises(RecordError):
                inspect_connection(self.accepted(), advertised)

    def test_result_capabilities_compare_as_a_set_and_may_be_omitted_only_when_empty(self):
        accepted = self.accepted()
        reordered = self.m('msg-0005', capabilities=['evidence-trace', 'bounded-scope'])
        self.assertTrue(inspect_connection(accepted[:4] + [reordered])['contract_valid'])
        request = self.m('msg-0001', capabilities=None)
        request['payload'].pop('required_capabilities')
        empty = self.m('msg-0002')
        empty['payload']['negotiated_capabilities'] = []
        result = self.m('msg-0005', capabilities=None)
        self.assertTrue(inspect_connection([request, empty, result])['contract_valid'])
        extra = self.m('msg-0005', capabilities=['audit'])
        self.assertEqual(self.rules(inspect_connection([request, empty, extra])), ['R12'])

    def test_status_observations(self):
        accepted = self.accepted()
        undecided = self.m('msg-0004')
        undecided['payload']['decision_needed'] = '   '
        done = self.m('msg-0004', message_id='msg-0010')
        done['payload'] = {'state': 'done'}
        report = inspect_connection(accepted[:3] + [undecided, done, accepted[4]])
        self.assertTrue(report['contract_valid'], report['failures'])
        self.assertEqual([item['observation'] for item in report['observations']], ['gap_without_decision'])
        self.assertEqual(report['open_handoffs'], [])

    def test_limits(self):
        request = self.m('msg-0001')
        with self.assertRaises(RecordError) as raised:
            inspect_connection([request] * 257)
        self.assertEqual(raised.exception.reason, 'a connection inspection accepts at most 256 messages')
        self.assertTrue(inspect_connection([request] * 256)['contract_valid'])
        with self.assertRaises(RecordError):
            inspect_connection([])
        self.assertEqual(inspect_records.MAX_TOTAL_BYTES, 8 * 1024 * 1024)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'request.json'
            path.write_text(json.dumps(request), encoding='utf-8')
            size = path.stat().st_size
            with patch.object(inspect_records, 'MAX_TOTAL_BYTES', size * 2):
                self.assertEqual(len(load_records([path, path])), 2)
                with self.assertRaises(RecordError) as raised:
                    load_records([path, path, path])
            self.assertEqual(raised.exception.reason, 'record files exceed 8 MiB in total')
            with self.assertRaises(RecordError):
                load_records([path] * 257)

    def test_cli_in_script_and_module_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for message in self.accepted():
                path = root / (message['message_id'] + '.json')
                path.write_text(json.dumps(message), encoding='utf-8')
                paths.append(str(path))
            advertise = [flag for token in BASELINE_CAPABILITIES for flag in ('--advertise', token)]
            for entry in (['scripts/inspect_records.py'], ['-m', 'scripts.inspect_records']):
                for args, code in ((paths + advertise + ['--require-closed'], 0), (paths[:4] + ['--require-closed'], 1)):
                    result = subprocess.run([sys.executable, *entry, 'connection', *args], cwd=ROOT,
                                            capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                    payload = json.loads(result.stdout)
                    self.assertEqual(payload['ok'], code == 0)
                    self.assertEqual(set(payload['inspection']), {
                        'contract_valid', 'connect_version', 'correlation_id', 'initiator', 'orchestrator',
                        'messages', 'distinct_messages', 'accepted', 'negotiated', 'handoffs', 'open_handoffs',
                        'closed', 'request_satisfied', 'redelivered', 'failure_count', 'failures',
                        'observations', 'note'})
            result = subprocess.run([sys.executable, 'scripts/inspect_records.py', 'connection', paths[0],
                                     '--advertise', 'Bad Token'], cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['reason'],
                             'advertised capabilities must be lowercase hyphen-separated tokens')
            self.assertNotIn('Bad Token', result.stdout)


if __name__ == '__main__':
    unittest.main()
