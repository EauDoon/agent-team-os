#!/usr/bin/env python3
"""Check paired evaluation records and print descriptive totals only."""

import argparse
import json
from pathlib import Path

try:
    from .check import load_json, ROOT
    from .contracts import violations
except ImportError:
    from check import load_json, ROOT
    from contracts import violations


def summarize(run: object, suite: dict) -> dict:
    errors = violations(run, load_json(ROOT / 'evals/run.schema.json'))
    if errors:
        raise ValueError('; '.join(errors))
    if run['runner'] == run['reviewer']:
        raise ValueError('runner and independent reviewer must be distinct')
    if run['suite_version'] != suite['suite_version']:
        raise ValueError('suite version differs from supplied suite')
    expected = {task['id']: len(task['acceptance']) for task in suite['tasks']}
    rows = {}
    for row in run['records']:
        key = (row['task_id'], row['arm'])
        if key in rows:
            raise ValueError('duplicate task and arm record')
        if row['task_id'] not in expected or len(row['checks']) != expected[row['task_id']]:
            raise ValueError('unknown task or wrong acceptance check count')
        rows[key] = row
    if set(rows) != {(task, arm) for task in expected for arm in ('solo', 'current')}:
        raise ValueError('every suite task needs both arms; missing runs cannot be dropped')
    for task in expected:
        solo, current = rows[(task, 'solo')], rows[(task, 'current')]
        for field in ('prompt_revision', 'evidence_revision'):
            if solo[field] != current[field]:
                raise ValueError('paired arms must use identical prompt and evidence revisions')
    totals = {}
    for arm in ('solo', 'current'):
        selected = [row for row in rows.values() if row['arm'] == arm]
        checks = [check for row in selected for check in row['checks']]
        totals[arm] = {
            'tasks': len(selected), 'passed': checks.count('pass'),
            'failed': checks.count('fail'), 'unverified': checks.count('unverified'),
            'tokens': sum(row['tokens'] for row in selected),
            'duration_seconds': sum(row['duration_seconds'] for row in selected),
        }
    return {'status': run['status'], 'arms': totals,
            'passed_check_difference_current_minus_solo': totals['current']['passed'] - totals['solo']['passed'],
            'interpretation': 'Descriptive totals for this supplied run only. No general superiority or causal claim.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    try:
        result = summarize(load_json(args.file), load_json(ROOT / 'evals/tasks.json'))
    except (OSError, ValueError, RecursionError) as exc:
        # Schema diagnostics may contain field names; never include source values.
        print(json.dumps({'ok': False, 'error': 'evaluation record is invalid or unreadable'}))
        return 1
    print(json.dumps({'ok': True, **result}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
