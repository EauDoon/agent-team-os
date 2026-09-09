import copy
import json
from pathlib import Path
import unittest

from scripts.contracts import violations
from scripts.validate import Checker

ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_every_shipped_connection_case(self):
        schema = json.loads((ROOT / 'schemas/connect.schema.json').read_text())
        suite = json.loads((ROOT / 'conformance/connect/cases.json').read_text())
        for case in suite['cases']:
            with self.subTest(case=case['name']):
                self.assertEqual(not violations(case['message'], schema), case['expect'] == 'valid')

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
        schema = json.loads((ROOT / 'schemas/connect.schema.json').read_text())
        suite = json.loads((ROOT / 'conformance/connect/cases.json').read_text())
        message = next(c['message'] for c in suite['cases'] if c['name'] == 'handoff-valid')
        message['payload']['role_brief']['task'] = []
        self.assertTrue(violations(message, schema))

    def test_unsupported_assertions_and_remote_refs_fail(self):
        for schema in [{'pattern': 'x'}, {'$ref': 'https://example.invalid/schema'}]:
            with self.assertRaises(ValueError):
                violations('x', schema)

    def test_boolean_is_not_number_or_numeric_const(self):
        self.assertTrue(violations(True, {'type': 'number'}))
        self.assertTrue(violations(True, {'const': 1}))


if __name__ == '__main__':
    unittest.main()
