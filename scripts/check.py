#!/usr/bin/env python3
"""Check an authored contract without sending data or executing instructions."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

try:
    from .contracts import violations
    from .version import add_version_flag
    from .workflows import audit_violations, evidence_violations, refusal_text_violations, routing_violations
except ImportError:
    from contracts import violations
    from version import add_version_flag
    from workflows import audit_violations, evidence_violations, refusal_text_violations, routing_violations

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = {
    'audit': 'schemas/audit-closure.schema.json',
    'evidence': 'schemas/evidence-ledger.schema.json',
    'plan': 'schemas/routing-plan.schema.json',
    'brief': 'schemas/role-brief.schema.json',
    'connect': 'schemas/connect.schema.json',
}
CONNECT_CONTRACTS = {
    'agent-team-connect/v0.1': 'schemas/connect.schema.json',
    'agent-team-connect/v0.2': 'schemas/connect-v0.2.schema.json',
}
MAX_BYTES = 1024 * 1024
_PATH_SEGMENT = re.compile(r'\.([^.\[]*)|\[([0-9]+)\]')
_FIXED_MESSAGE = re.compile(r'[a-z][a-z ]*')


def parse_json_bytes(raw: bytes) -> object:
    """Decode bounded bytes, rejecting duplicate keys and non-JSON numbers."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON object key')
            result[key] = value
        return result

    def constant(_value):
        raise ValueError('non-finite JSON number')

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('non-finite JSON number')
        return number

    if len(raw) > MAX_BYTES:
        raise ValueError('JSON input exceeds 1 MiB')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant, parse_float=finite_float)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('input must be a bounded UTF-8 JSON document') from exc


def load_json_snapshot(path: Path) -> tuple[object, str]:
    """Parse and hash the same bounded byte snapshot, without a second read."""
    raw = read_json_bytes(path)
    return parse_json_bytes(raw), hashlib.sha256(raw).hexdigest()


def read_json_bytes(path: Path) -> bytes:
    with path.open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('JSON input exceeds 1 MiB')
    return raw


def load_json(path: Path) -> object:
    return load_json_snapshot(path)[0]


def contract_schema(kind: str, document: object, *, schema_root: Path = ROOT) -> dict:
    """Load the schema a document is checked against, by kind and declared version."""
    relative = CONTRACTS[kind]
    if kind == 'connect' and isinstance(document, dict):
        version = document.get('connect_version')
        if isinstance(version, str):
            relative = CONNECT_CONTRACTS.get(version, relative)
    return load_json(schema_root / relative)


def declared_names(schema: object) -> set[str]:
    """Collect every property name a schema declares, at any depth."""
    names: set[str] = set()
    stack = [schema]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            properties = node.get('properties')
            if isinstance(properties, dict):
                names.update(key for key in properties if isinstance(key, str))
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return names


def masked_diagnostics(errors: list[str], schema: object) -> list[str]:
    """Return schema diagnostics that are safe to print beside a fixed reason.

    Only ``$``-path diagnostics are kept. Their messages are fixed checker text,
    and a path key the schema does not declare, such as the name of an unknown
    field, is replaced with ``*`` so no input text is echoed. Semantic
    diagnostics can quote record IDs, so they are left to ``check.py``.
    """
    names = declared_names(schema)
    masked = []
    for error in errors:
        path, separator, message = error.rpartition(': ')
        if not separator or not path.startswith('$') or _FIXED_MESSAGE.fullmatch(message) is None:
            continue
        parts = ['$']
        position = 1
        while position < len(path):
            match = _PATH_SEGMENT.match(path, position)
            if match is None:
                parts.append('.*')
                break
            if match.group(2) is not None:
                parts.append(f'[{match.group(2)}]')
            else:
                parts.append('.' + (match.group(1) if match.group(1) in names else '*'))
            position = match.end()
        text = ''.join(parts) + ': ' + message
        if text not in masked:
            masked.append(text)
    return masked


def shape_failures(kind: str, document: object, *, schema_root: Path = ROOT) -> list[str]:
    """Return the masked schema diagnostics for a document, safe to print with a reason.

    Semantic diagnostics (routing, evidence and audit rules) are excluded
    because they can quote record IDs; ``check.py`` reports them in full.
    """
    schema = contract_schema(kind, document, schema_root=schema_root)
    errors = violations(document, schema)
    if kind == 'connect':
        errors.extend(refusal_text_violations(document))
    return masked_diagnostics(errors, schema)


def check_document(kind: str, document: object, *, schema_root: Path = ROOT) -> list[str]:
    schema = contract_schema(kind, document, schema_root=schema_root)
    errors = violations(document, schema)
    if kind == 'connect':
        errors.extend(refusal_text_violations(document))
    if not errors and kind == 'plan':
        errors.extend(routing_violations(document))
    if not errors and kind == 'evidence':
        errors.extend(evidence_violations(document))
    if not errors and kind == 'audit':
        errors.extend(audit_violations(document))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_version_flag(parser)
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
        print('\n'.join('FAIL ' + json.dumps(error, ensure_ascii=True)[1:-1] for error in errors))
    else:
        print('PASS ' + args.kind)
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
