import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check import contract_schema, masked_diagnostics
from scripts.inspect_records import inspect_evidence, inspect_plan, inspection_date
from scripts.workflows import MAX_ERROR_FAILURES, RecordError

ROOT = Path(__file__).resolve().parents[1]
SENTINEL = 'zq-sentinel-4471'
INSPECT_ERROR = 'records or inspection arguments are invalid or unreadable'
EVALUATE_ERROR = 'evaluation record is invalid or unreadable'
AUTHOR_ERROR = 'record could not be authored; check fields and a new writable output path'


def run_cli(module: str, args: list[str], *, module_mode: bool = False) -> tuple[int, dict, str, str]:
    entry = ['-m', f'scripts.{module}'] if module_mode else [f'scripts/{module}.py']
    result = subprocess.run([sys.executable, *entry, *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
    return result.returncode, json.loads(result.stdout), result.stdout, result.stderr


class RecordErrorTests(unittest.TestCase):
    def test_record_error_is_a_value_error_with_bounded_failures(self):
        error = RecordError('fixed rule', [f'$.field{index}: required field missing' for index in range(30)])
        self.assertIsInstance(error, ValueError)
        self.assertEqual(str(error), 'fixed rule')
        self.assertEqual(len(error.failures), MAX_ERROR_FAILURES)
        self.assertEqual(error.details()['reason'], 'fixed rule')
        self.assertEqual(RecordError('no diagnostics').details(), {'reason': 'no diagnostics'})

    def test_masking_hides_undeclared_keys_and_semantic_diagnostics(self):
        message = {'connect_version': 'agent-team-connect/v0.2', 'type': 'handoff', 'message_id': 'm1',
                   'correlation_id': 'c1', 'from': 'owner', 'to': 'maker',
                   'payload': {'role_brief': {'role': 'Maker', SENTINEL + ': note': SENTINEL}}}
        schema = contract_schema('connect', message)
        errors = ['$.payload.role_brief.' + SENTINEL + ': note: unknown field',
                  '$.payload.role_brief.task: required field missing',
                  '$.payload.role_brief.task: required field missing',
                  SENTINEL + ': unknown dependency other',
                  '$.payload: message quoting ' + SENTINEL.upper()]
        masked = masked_diagnostics(errors, schema)
        self.assertEqual(masked, ['$.payload.role_brief.*: unknown field',
                                  '$.payload.role_brief.task: required field missing'])
        self.assertNotIn(SENTINEL, json.dumps(masked))

    def test_rules_raise_named_reasons(self):
        plan = json.loads((ROOT / 'templates/routing-plan.json').read_text(encoding='utf-8'))
        ledger = json.loads((ROOT / 'templates/evidence-ledger.json').read_text(encoding='utf-8'))
        cases = [(lambda: inspect_plan(plan, ['missing']), 'unknown accepted assignment'),
                 (lambda: inspect_plan(plan, ['build']), 'accepted assignments must include their accepted dependencies'),
                 (lambda: inspect_plan(plan, blocked=['missing']), 'blocked IDs must be unique known unaccepted assignments'),
                 (lambda: inspect_evidence(ledger, ['missing']), 'unknown changed source'),
                 (lambda: inspection_date(SENTINEL), 'date must use DD-MM-YYYY'),
                 (lambda: inspect_plan({'plan_version': SENTINEL}), 'record does not conform')]
        for call, reason in cases:
            with self.subTest(reason=reason), self.assertRaises(RecordError) as raised:
                call()
            self.assertEqual(raised.exception.reason, reason)
            self.assertNotIn(SENTINEL, str(raised.exception))

    def test_inspection_cli_reports_reasons_in_both_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / 'plan.json'
            invalid.write_text(json.dumps({'plan_version': 'agent-team-plan/v0.1', 'objective': SENTINEL}),
                               encoding='utf-8')
            cases = [(['plan', 'templates/routing-plan.json', '--accepted', 'nonexistent'], 'unknown accepted assignment'),
                     (['plan', 'templates/routing-plan.json', '--accepted', 'build'],
                      'accepted assignments must include their accepted dependencies'),
                     (['evidence', 'templates/evidence-ledger.json', '--as-of', '2026-09-12', '--max-age-days', '2'],
                      'date must use DD-MM-YYYY'),
                     (['plan', str(invalid)], 'record does not conform')]
            for module_mode in (False, True):
                for args, reason in cases:
                    with self.subTest(args=args, module_mode=module_mode):
                        code, payload, stdout, stderr = run_cli('inspect_records', args, module_mode=module_mode)
                        self.assertEqual(code, 1)
                        self.assertEqual(payload['error'], INSPECT_ERROR)
                        self.assertEqual(payload['reason'], reason)
                        self.assertEqual(stderr, '')
                        self.assertNotIn(SENTINEL, stdout)
            code, payload, _, _ = run_cli('inspect_records', ['plan', str(invalid)])
            self.assertIn('$.route: required field missing', payload['failures'])

    def test_unreadable_input_keeps_the_generic_error_only(self):
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / (SENTINEL + '.json')
            broken.write_text('{"objective": "' + SENTINEL, encoding='utf-8')
            code, payload, stdout, stderr = run_cli('inspect_records', ['plan', str(broken)])
            self.assertEqual((code, payload), (1, {'ok': False, 'error': INSPECT_ERROR}))
            self.assertNotIn(SENTINEL, stdout + stderr)
            code, payload, stdout, stderr = run_cli('inspect_records', ['plan', str(Path(directory) / 'absent.json')])
            self.assertEqual((code, payload), (1, {'ok': False, 'error': INSPECT_ERROR}))

    def test_evaluation_cli_names_the_rule_and_masks_schema_diagnostics(self):
        suite = json.loads((ROOT / 'evals/tasks.json').read_text(encoding='utf-8'))
        run = {'run_version': 'agent-team-run/v0.1', 'suite_version': suite['suite_version'],
               'status': 'synthetic', 'runner': 'runner', 'reviewer': 'reviewer', 'records': []}
        for task in suite['tasks']:
            for arm in ('solo', 'current'):
                run['records'].append({'task_id': task['id'], 'arm': arm, 'prompt_revision': 'p1',
                                       'evidence_revision': 'e1', 'output_revision': 'o1',
                                       'review_evidence': 'Synthetic check record.',
                                       'configuration': 'Synthetic runner configuration.',
                                       'checks': ['pass'] * len(task['acceptance']),
                                       'tokens': 1, 'duration_seconds': 1})
        wrong_count = copy.deepcopy(run)
        wrong_count['records'][0]['checks'] = ['pass']
        unknown_field = copy.deepcopy(run)
        unknown_field[SENTINEL] = SENTINEL
        with tempfile.TemporaryDirectory() as directory:
            paths = {}
            for name, record in (('count', wrong_count), ('field', unknown_field)):
                paths[name] = Path(directory) / f'{name}-{SENTINEL}.json'
                paths[name].write_text(json.dumps(record), encoding='utf-8')
            for module_mode in (False, True):
                code, payload, stdout, stderr = run_cli('evaluate', [str(paths['count'])], module_mode=module_mode)
                self.assertEqual((code, payload['error']), (1, EVALUATE_ERROR))
                self.assertEqual(payload['reason'], 'unknown task or wrong acceptance check count')
                self.assertNotIn(SENTINEL, stdout + stderr)
            code, payload, stdout, stderr = run_cli('evaluate', [str(paths['field'])])
            self.assertEqual(payload['reason'], 'evaluation record does not match its schema')
            self.assertEqual(payload['failures'], ['$.*: unknown field'])
            self.assertNotIn(SENTINEL, stdout + stderr)

    def test_author_cli_names_the_rule_without_echoing_input(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / (SENTINEL + '.json')
            cases = [(['brief', '--role', ' ', '--scope', SENTINEL, '--task', 't', '--evidence', 'e',
                       '--deliver', 'd', '--stop', 's', '--output', str(output)], 'each brief field needs meaningful text'),
                     (['plan-brief', 'templates/routing-plan.json', '--assignment', SENTINEL, '--output', str(output)],
                      'assignment is not in the routing plan'),
                     (['refusal', '--version', 'agent-team-connect/v0.2', '--from', SENTINEL, '--to', 'b',
                       '--message-id', 'm1', '--correlation-id', 'c1', '--reason', ' ', '--next-step', 'n',
                       '--output', str(output)], 'message does not conform')]
            for module_mode in (False, True):
                for args, reason in cases:
                    with self.subTest(reason=reason, module_mode=module_mode):
                        code, payload, stdout, stderr = run_cli('author', args, module_mode=module_mode)
                        self.assertEqual((code, payload['error'], payload['reason']), (1, AUTHOR_ERROR, reason))
                        self.assertNotIn(SENTINEL, stdout + stderr)
                        self.assertFalse(output.exists())
            code, payload, _, _ = run_cli('author', cases[2][0])
            self.assertEqual(payload['failures'], ['$.payload.refusal_reason: refusal text must not be blank'])


if __name__ == '__main__':
    unittest.main()
