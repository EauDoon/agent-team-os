#!/usr/bin/env python3
"""Check an authored contract without sending data or executing instructions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .contracts import violations
    from .workflows import routing_violations, evidence_violations, audit_violations
except ImportError:
    from contracts import violations
    from workflows import routing_violations, evidence_violations, audit_violations

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = {'audit': 'schemas/audit-closure.schema.json', 'evidence': 'schemas/evidence-ledger.schema.json', 'plan': 'schemas/routing-plan.schema.json', 'brief': 'schemas/role-brief.schema.json', 'connect': 'schemas/connect.schema.json'}
MAX_BYTES = 1024 * 1024


def load_json(path: Path) -> object:
    """Bound reads and reject duplicate keys and non-JSON numeric constants."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON object key')
            result[key] = value
        return result

    def constant(_value):
        raise ValueError('non-finite JSON number')

    with path.open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('JSON input exceeds 1 MiB')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('input must be a bounded UTF-8 JSON document') from exc


def check_document(kind: str, document: object) -> list[str]:
    schema = load_json(ROOT / CONTRACTS[kind])
    errors = violations(document, schema)
    if not errors and kind == 'plan':
        errors.extend(routing_violations(document))
    if not errors and kind == 'evidence':
        errors.extend(evidence_violations(document))
    if not errors and kind == 'audit':
        errors.extend(audit_violations(document))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=sorted(CONTRACTS))
    parser.add_argument('file', type=Path)
    parser.add_argument('--json', action='store_true', dest='as_json')
    args = parser.parse_args()
    try:
        errors = check_document(args.kind, load_json(args.file))
    except (OSError, ValueError, RecursionError):
        # Do not echo source content, exception context or private paths.
        errors = ['input could not be checked; use a readable UTF-8 JSON file of at most 1 MiB with unique keys and finite numbers']
    result = {'ok': not errors, 'kind': args.kind, 'failures': errors}
    if args.as_json:
        print(json.dumps(result, indent=2))
    elif errors:
        print('\n'.join('FAIL ' + error for error in errors))
    else:
        print('PASS ' + args.kind)
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
