#!/usr/bin/env python3
"""Inspect local operator records without scheduling or changing their state."""

import argparse
import json
from pathlib import Path

try:
    from .check import check_document, load_json
except ImportError:
    from check import check_document, load_json


def require_record(kind: str, document: object) -> None:
    if check_document(kind, document):
        raise ValueError('record does not conform')


def inspect_plan(plan: object, accepted: list[str] | None = None) -> dict:
    require_record('plan', plan)
    by_id = {item['id']: item for item in plan['assignments']}
    accepted = [] if accepted is None else accepted
    if any(not isinstance(item, str) for item in accepted) or len(set(accepted)) != len(accepted):
        raise ValueError('accepted assignment IDs must be unique strings')
    accepted_ids = set(accepted)
    if not accepted_ids <= by_id.keys():
        raise ValueError('unknown accepted assignment')
    if any(not set(by_id[item]['depends_on']) <= accepted_ids for item in accepted_ids):
        raise ValueError('accepted assignments must include their accepted dependencies')
    remaining = {key: set(item['depends_on']) for key, item in by_id.items()}
    stages = []
    while remaining:
        ready = sorted(key for key, dependencies in remaining.items() if not dependencies)
        if not ready:
            raise ValueError('routing dependency cycle')
        stages.append(ready)
        remaining = {key: dependencies - set(ready) for key, dependencies in remaining.items() if key not in ready}
    waiting = [{'id': key, 'unaccepted_dependencies': sorted(set(item['depends_on']) - accepted_ids)}
               for key, item in sorted(by_id.items()) if key not in accepted_ids]
    return {'route': plan['route'], 'stages': stages, 'accepted': sorted(accepted_ids),
            'ready': [item['id'] for item in waiting if not item['unaccepted_dependencies']],
            'waiting': [item for item in waiting if item['unaccepted_dependencies']],
            'max_parallel': plan.get('budget', {}).get('max_parallel'),
            'note': 'Readiness means dependency acceptance only; it does not authorize or start work.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('plan')
    plan.add_argument('file', type=Path)
    plan.add_argument('--accepted', action='append', default=[])
    args = parser.parse_args()
    try:
        result = inspect_plan(load_json(args.file), args.accepted)
        rendered = json.dumps({'ok': True, 'inspection': result}, indent=2, allow_nan=False)
    except (OSError, ValueError, RecursionError, OverflowError):
        print(json.dumps({'ok': False, 'error': 'records or inspection arguments are invalid or unreadable'}))
        return 1
    print(rendered)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
