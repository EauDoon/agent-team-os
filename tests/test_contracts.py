import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check import check_document
from scripts.contracts import keyword_value_problems, violations
from scripts.validate import Checker, schema_problems

ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_every_shipped_connection_case(self):
        for schema_file, suite_file in [('schemas/connect.schema.json', 'conformance/connect/cases.json'),
                                        ('schemas/connect-v0.2.schema.json', 'conformance/connect-v0.2/cases.json')]:
            schema = json.loads((ROOT / schema_file).read_text())
            suite = json.loads((ROOT / suite_file).read_text())
            for case in suite['cases']:
                with self.subTest(suite=suite_file, case=case['name']):
                    # Same path as CI: schema violations plus connect semantics.
                    actual = Checker(ROOT).connect_violations(case['message'], schema)
                    self.assertEqual(not actual, case['expect'] == 'valid')

    def test_declared_version_preserves_legacy_handoff_acceptance(self):
        suite = json.loads((ROOT / 'conformance/connect/cases.json').read_text())
        message = next(case['message'] for case in suite['cases'] if case['name'] == 'handoff-valid')
        message['payload']['role_brief'].update(task=[], consumer_note='Legacy extension.')
        self.assertEqual(check_document('connect', message), [])
        message['connect_version'] = 'agent-team-connect/v0.2'
        self.assertTrue(check_document('connect', message))
        message['connect_version'] = 'agent-team-connect/v999'
        self.assertTrue(check_document('connect', message))

    def test_v02_refusals_require_both_actionable_fields(self):
        suite = json.loads((ROOT / 'conformance/connect-v0.2/cases.json').read_text())
        refused = next(case['message'] for case in suite['cases'] if case['name'] == 'response-refuse-valid')
        self.assertEqual(check_document('connect', refused), [])
        for field in ('refusal_reason', 'next_step'):
            for missing in (True, False):
                message = copy.deepcopy(refused)
                if missing:
                    del message['payload'][field]
                else:
                    message['payload'][field] = ''
                self.assertTrue(check_document('connect', message))
                # The previous published wire contract remains unchanged.
                message['connect_version'] = 'agent-team-connect/v0.1'
                self.assertEqual(check_document('connect', message), [])
        accepted = copy.deepcopy(refused)
        accepted['payload'] = {'accepted': True}
        self.assertEqual(check_document('connect', accepted), [])

    def test_v02_refusal_text_cannot_be_only_whitespace(self):
        suite = json.loads((ROOT / 'conformance/connect-v0.2/cases.json').read_text())
        schema = json.loads((ROOT / 'schemas/connect-v0.2.schema.json').read_text())
        refused = next(case['message'] for case in suite['cases'] if case['name'] == 'response-refuse-valid')
        for field in ('refusal_reason', 'next_step'):
            message = copy.deepcopy(refused)
            message['payload'][field] = ' \t '
            errors = check_document('connect', message)
            self.assertTrue(any('must not be blank' in error for error in errors), errors)
            self.assertTrue(any('must not be blank' in error for error in Checker(ROOT).connect_violations(message, schema)), errors)
            message['connect_version'] = 'agent-team-connect/v0.1'
            self.assertEqual(check_document('connect', message), [])

    def test_connection_rejects_malformed_envelope_and_nested_values(self):
        schema = json.loads((ROOT / 'schemas/connect.schema.json').read_text())
        suite = json.loads((ROOT / 'conformance/connect/cases.json').read_text())
        good = suite['cases'][0]['message']
        for key, value in [('message_id', ''), ('payload', []), ('type', []),
                           ('capabilities', ['x', 'x']), ('extra', True)]:
            broken = copy.deepcopy(good)
            broken[key] = value
            self.assertTrue(Checker(ROOT).connect_violations(broken, schema))
        broken = copy.deepcopy(good)
        broken['payload']['objective'] = False
        self.assertTrue(violations(broken, schema))

    def test_handoff_uses_full_role_brief_contract(self):
        schema = json.loads((ROOT / 'schemas/connect-v0.2.schema.json').read_text())
        suite = json.loads((ROOT / 'conformance/connect-v0.2/cases.json').read_text())
        message = next(c['message'] for c in suite['cases'] if c['name'] == 'handoff-valid')
        message['payload']['role_brief']['task'] = []
        self.assertTrue(violations(message, schema))

    def test_unsupported_assertions_and_remote_refs_fail(self):
        for schema in [{'format': 'date'}, {'$ref': 'https://example.invalid/schema'}]:
            with self.assertRaises(ValueError):
                violations('x', schema)

    def test_malformed_keyword_values_raise_value_error(self):
        # A nullable type list used to escape every handler as a TypeError, and
        # a string `required` was iterated one character at a time.
        for schema in [{'type': ['string', 'null']}, {'type': 'strng'}, {'minLength': '2'},
                       {'minimum': '3'}, {'maxItems': -1}, {'minLength': True},
                       {'required': 'a'}, {'enum': 'a'}, {'uniqueItems': 1},
                       {'pattern': 3}, {'pattern': '('}, {'items': []},
                       {'properties': ['a']}, {'maximum': float('nan')}]:
            with self.subTest(schema=schema), self.assertRaises(ValueError):
                violations({'a': 'x'} if 'required' in schema or 'properties' in schema else 'x', schema)
        self.assertEqual(keyword_value_problems({'type': 'string', 'minLength': 1, 'maximum': 1.5,
                                                 'required': [], 'items': True}), [])

    def test_pattern_dollar_anchors_only_at_the_end_of_input(self):
        # ECMA-262 `$` never matches before a trailing newline; Python's does.
        self.assertEqual(violations('ab', {'type': 'string', 'pattern': '^ab$'}), [])
        self.assertEqual(violations('ab\n', {'type': 'string', 'pattern': '^ab$'}),
                         ['$: does not match pattern'])
        self.assertEqual(violations('a$', {'pattern': '^a[$]$'}), [])
        self.assertEqual(violations('a$', {'pattern': '^a\\$$'}), [])
        self.assertEqual(violations('a]$', {'pattern': '^a[]$]+$'}), [])
        self.assertEqual(violations('ab', {'pattern': '^a[^]$]$'}), [])
        self.assertEqual(violations('a$\n', {'pattern': '^a[$]$'}), ['$: does not match pattern'])
        digest = 'ab' * 32
        receipt = {'pattern': '^[0-9a-fA-F]{64}$'}
        self.assertEqual(violations(digest, receipt), [])
        self.assertEqual(violations(digest + '\n', receipt), ['$: does not match pattern'])

    def test_schema_walk_reports_malformed_values_at_schema_positions_only(self):
        schema = {'type': 'object',
                  'properties': {'type': {'enum': ['request']},
                                 'a': {'type': ['string', 'null']},
                                 'b': {'minLength': '2'}},
                  'required': 'a'}
        self.assertEqual(schema_problems(schema), [
            '$: required must be an array of strings',
            '$.properties.a: type must be one supported type name',
            '$.properties.b: minLength must be a non-negative integer',
        ])
        # The shipped connect schemas use a property named `type`; it is data.
        for name in ('connect.schema.json', 'connect-v0.2.schema.json'):
            self.assertEqual(schema_problems(json.loads((ROOT / 'schemas' / name).read_text())), [])

    def test_malformed_schema_fails_cleanly_in_the_check_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'scripts', root / 'scripts',
                            ignore=shutil.ignore_patterns('__pycache__'))
            (root / 'schemas').mkdir()
            (root / 'schemas/role-brief.schema.json').write_text(
                json.dumps({'type': ['object', 'null']}), encoding='utf-8')
            with self.assertRaises(ValueError):
                check_document('brief', {}, schema_root=root)
            brief = root / 'brief.json'
            brief.write_text('{}', encoding='utf-8')
            result = subprocess.run([sys.executable, str(root / 'scripts/check.py'), 'brief', str(brief)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertTrue(result.stdout.startswith('FAIL input could not be checked'), result.stdout)

    def test_additional_properties_schema_constrains_unknown_fields(self):
        schema = {'type': 'object', 'properties': {'known': {'type': 'string'}},
                  'additionalProperties': {'type': 'integer'}}
        self.assertEqual(violations({'known': 'ok', 'extra': 2}, schema), [])
        self.assertEqual(violations({'extra': 'nope'}, schema), ['$.extra: expected integer'])
        self.assertEqual(violations({'extra': 1}, {'additionalProperties': False}),
                         ['$.extra: unknown field'])

    def test_boolean_subschemas_accept_or_reject_without_crashing(self):
        self.assertEqual(violations(1, {'allOf': [True]}), [])
        self.assertEqual(violations(1, {'allOf': [False]}), ['$: value is not allowed'])
        self.assertEqual(violations({'a': 1}, {'properties': {'a': False}}), ['$.a: value is not allowed'])
        self.assertEqual(violations({'a': 1}, {'properties': {'a': True}}), [])
        self.assertEqual(violations({'k': 'a'}, {'if': False, 'else': {'required': ['k']}}), [])
        self.assertEqual(violations(1, {'if': True, 'then': {'const': 2}}), ['$: does not match const'])
        with self.assertRaises(ValueError):
            violations(1, {'allOf': [[]]})

    def test_boolean_is_not_number_or_numeric_const(self):
        self.assertTrue(violations(True, {'type': 'number'}))
        self.assertTrue(violations(True, {'const': 1}))

    def test_assertion_keywords_reject_and_accept(self):
        # These keywords are all used by a shipped schema and each one is the
        # only thing standing between a malformed record and a clean check.
        rejected = [
            ('minLength', 'ab', {'minLength': 3}),
            ('minItems', [], {'minItems': 1}),
            ('maxItems', [1, 2, 3], {'maxItems': 2}),
            ('uniqueItems', [1, 1], {'uniqueItems': True}),
            ('allOf', {'a': 1}, {'allOf': [{'required': ['a']},
                                           {'properties': {'a': {'type': 'string'}}}]}),
            ('minimum', 0, {'minimum': 1}),
            ('maximum', 2, {'minimum': 1, 'maximum': 1.5}),
            ('maxLength', 'abcd', {'maxLength': 3}),
            ('pattern', 'zz', {'pattern': '^[0-9a-f]{2}$'}),
        ]
        accepted = [
            ('minLength', 'abc', {'minLength': 3}),
            ('minItems', [1], {'minItems': 1}),
            ('maxItems', [1, 2], {'maxItems': 2}),
            ('uniqueItems', [1, 2], {'uniqueItems': True}),
            ('allOf', {'a': 'x'}, {'allOf': [{'required': ['a']},
                                             {'properties': {'a': {'type': 'string'}}}]}),
            ('minimum', 1.5, {'minimum': 1, 'maximum': 1.5}),
            ('maxLength', 'ab', {'maxLength': 3}),
            ('pattern', 'ab', {'pattern': '^[0-9a-f]{2}$'}),
        ]
        for keyword, value, schema in rejected:
            with self.subTest(keyword=keyword, expectation='rejected'):
                self.assertEqual(len(violations(value, schema)), 1, violations(value, schema))
        for keyword, value, schema in accepted:
            with self.subTest(keyword=keyword, expectation='accepted'):
                self.assertEqual(violations(value, schema), [])

    def test_oversized_collections_and_json_equality_are_bounded(self):
        # An oversized collection is rejected on its size alone, without one
        # diagnostic per item, so a hostile array cannot inflate the report.
        self.assertEqual(violations([1, 2, 3], {'maxItems': 2, 'items': {'type': 'string'}}),
                         ['$: too many items'])
        # JSON equality keeps 1 and true distinct inside a collection.
        self.assertEqual(violations([1, True], {'uniqueItems': True}), [])
        # 1 and 1.0 are the same JSON number, including inside a nested value.
        self.assertEqual(violations([1, 1.0], {'uniqueItems': True}), ['$: duplicate items'])
        self.assertEqual(violations([[1], [1.0]], {'uniqueItems': True}), ['$: duplicate items'])
        self.assertEqual(violations(1.0, {'const': 1}), [])
        self.assertEqual(violations(1, {'enum': [1.0]}), [])
        # Draft 2020-12 integers include whole numbers such as 1.0 and -0.
        self.assertEqual(violations(1.0, {'type': 'integer', 'minimum': 1, 'maximum': 1}), [])
        self.assertEqual(violations(-0.0, {'type': 'integer', 'minimum': 0}), [])
        self.assertTrue(violations(1.5, {'type': 'integer'}))
        self.assertTrue(violations(True, {'type': 'integer'}))
        self.assertEqual(violations({'n': 1.0}, {'const': {'n': 1}}), [])
        self.assertTrue(violations(False, {'const': 0}))

    def test_conditional_payloads_apply_the_matching_branch(self):
        schema = {'properties': {'kind': {'const': 'a'}},
                  'if': {'properties': {'kind': {'const': 'b'}}},
                  'then': {'required': ['b_note']},
                  'else': {'required': ['a_note']}}
        self.assertEqual(violations({'kind': 'a', 'a_note': 'n'}, schema), [])
        self.assertEqual(violations({'kind': 'a'}, schema), ['$.a_note: required field missing'])
        self.assertEqual(violations({'kind': 'b', 'b_note': 'n'}, schema),
                         ['$.kind: does not match const'])

    def test_excessive_contract_depth_is_refused(self):
        schema, value = {'type': 'object'}, {}
        for _ in range(70):
            schema = {'type': 'object', 'properties': {'a': schema}}
            value = {'a': value}
        errors = violations(value, schema)
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].endswith('maximum contract depth exceeded'), errors)

    def test_conditional_depth_limit_is_not_a_failed_condition(self):
        # A depth-limit failure inside `if` used to be read as "condition does
        # not apply". The permissive `else` then matched and the document passed.
        schema = {'else': {}}
        value = {}
        for _ in range(80):
            schema = {
                'if': {'type': 'object', 'properties': {'a': schema}, 'required': ['a']},
                'else': {},
            }
            value = {'a': value}
        errors = violations(value, schema)
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(errors[0].endswith('maximum contract depth exceeded'), errors)


if __name__ == '__main__':
    unittest.main()
