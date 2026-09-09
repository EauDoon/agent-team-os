#!/usr/bin/env python3
"""Check paired evaluation records and print descriptive totals only."""

import argparse
import json
import math
from pathlib import Path

try:
    from .check import load_json, ROOT
    from .contracts import violations
except ImportError:
    from check import load_json, ROOT
    from contracts import violations

MAX_EXACT_INTEGER = 2 ** 53 - 1


def duration_total(rows: list[dict]) -> float:
    """Reject aggregate overflow even when every input measurement is finite."""
    try:
        total = math.fsum(row['duration_seconds'] for row in rows)
    except (OverflowError, ValueError) as exc:
        raise ValueError('duration total is not representable as a finite number') from exc
    if not math.isfinite(total):
        raise ValueError('duration total must be finite')
    return total


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
        tokens = sum(row['tokens'] for row in selected)
        if tokens > MAX_EXACT_INTEGER:
            raise ValueError('token total exceeds the interoperable JSON integer limit')
        totals[arm] = {
            'tasks': len(selected), 'passed': checks.count('pass'),
            'failed': checks.count('fail'), 'unverified': checks.count('unverified'),
            'tokens': tokens,
            'duration_seconds': duration_total(selected),
        }
    task_details = []
    for task in suite['tasks']:
        solo, current = rows[(task['id'], 'solo')], rows[(task['id'], 'current')]
        task_details.append({
            'task_id': task['id'],
            'checks': [{'criterion': criterion, 'solo': solo['checks'][index], 'current': current['checks'][index]}
                       for index, criterion in enumerate(task['acceptance'])],
            'passed_check_difference_current_minus_solo': current['checks'].count('pass') - solo['checks'].count('pass'),
            'prompt_revision': solo['prompt_revision'], 'evidence_revision': solo['evidence_revision'],
            'output_revisions': {'solo': solo['output_revision'], 'current': current['output_revision']},
        })
    return {'status': run['status'], 'arms': totals,
            'tasks': task_details,
            'passed_check_difference_current_minus_solo': totals['current']['passed'] - totals['solo']['passed'],
            'interpretation': 'Descriptive totals for this supplied run only. No general superiority or causal claim.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    try:
        result = summarize(load_json(args.file), load_json(ROOT / 'evals/tasks.json'))
        rendered = json.dumps({'ok': True, **result}, indent=2, allow_nan=False)
    except (OSError, ValueError, OverflowError, RecursionError):
        # Schema diagnostics may contain field names; never include source values.
        print(json.dumps({'ok': False, 'error': 'evaluation record is invalid or unreadable'}, allow_nan=False))
        return 1
    print(rendered)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
