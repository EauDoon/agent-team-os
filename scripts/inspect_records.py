#!/usr/bin/env python3
"""Inspect local operator records without scheduling or changing their state."""

import argparse
import json
from pathlib import Path

try:
    from .check import ROOT, check_document, load_json
    from .contracts import violations
except ImportError:
    from check import ROOT, check_document, load_json
    from contracts import violations


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


def compare_plans(before: object, after: object) -> dict:
    require_record('plan', before)
    require_record('plan', after)
    old = {item['id']: item for item in before['assignments']}
    new = {item['id']: item for item in after['assignments']}
    normalize = lambda values: {value.replace('\\', '/').strip('/').casefold() for value in values}
    changes = []
    for key in sorted(old.keys() & new.keys()):
        left, right = old[key], new[key]
        entry = {'id': key,
                 'write_resources_added': sorted(normalize(right['write_resources']) - normalize(left['write_resources'])),
                 'write_resources_removed': sorted(normalize(left['write_resources']) - normalize(right['write_resources'])),
                 'dependencies_added': sorted(set(right['depends_on']) - set(left['depends_on'])),
                 'dependencies_removed': sorted(set(left['depends_on']) - set(right['depends_on'])),
                 'brief_changes': {field: {'before': left['brief'].get(field), 'after': right['brief'].get(field)}
                                   for field in sorted(left['brief'].keys() | right['brief'].keys())
                                   if left['brief'].get(field) != right['brief'].get(field)}}
        if left['output'] != right['output']:
            entry['output_change'] = {'before': left['output'], 'after': right['output']}
        if any(value for field, value in entry.items() if field != 'id'):
            changes.append(entry)
    global_changes = {field: {'before': before.get(field), 'after': after.get(field)}
                      for field in sorted(before.keys() | after.keys()) if field != 'assignments'
                      and before.get(field) != after.get(field)}
    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    return {'changed': bool(added or removed or changes or global_changes), 'assignments_added': added,
            'assignments_removed': removed, 'assignment_changes': changes, 'plan_changes': global_changes,
            'note': 'Compare scope and ownership before continuing; a delta grants no new authorization.'}


def inspect_evidence(ledger: object, changed_sources: list[str] | None = None) -> dict:
    require_record('evidence', ledger)
    changed_sources = [] if changed_sources is None else changed_sources
    sources = {source['id']: source for source in ledger['sources']}
    if any(not isinstance(item, str) for item in changed_sources) or len(set(changed_sources)) != len(changed_sources):
        raise ValueError('changed source IDs must be unique strings')
    if not set(changed_sources) <= sources.keys():
        raise ValueError('unknown changed source')
    references = {key: [] for key in sources}
    affected = []
    unresolved = []
    assumptions = []
    for claim in sorted(ledger['claims'], key=lambda item: item['id']):
        for source in claim['source_ids']:
            references[source].append(claim['id'])
        if set(claim['source_ids']) & set(changed_sources):
            affected.append({'id': claim['id'], 'status': claim['status'],
                             'changed_sources': sorted(set(claim['source_ids']) & set(changed_sources)),
                             'statement': claim['statement'], 'next_step': claim['next_step']})
        if claim['status'] in {'unsupported', 'conflicting'}:
            unresolved.append({'id': claim['id'], 'status': claim['status'], 'next_step': claim['next_step']})
        if claim['status'] == 'assumption':
            assumptions.append(claim['id'])
    return {'source_claims': dict(sorted(references.items())), 'affected_claims': affected,
            'unresolved_claims': unresolved, 'assumptions': assumptions,
            'unused_sources': sorted(key for key, claims in references.items() if not claims),
            'note': 'Affected claims need reinspection; their recorded status has not been changed.'}


def inspect_audit(report: object, target_revision: str | None = None) -> dict:
    if violations(report, load_json(ROOT / 'schemas/audit-closure.schema.json')):
        raise ValueError('audit report shape is invalid')
    target = report['target_revision'] if target_revision is None else target_revision
    if not isinstance(target, str) or not target.strip():
        raise ValueError('target revision must not be blank')
    failures = check_document('audit', report)
    revision_changed = target != report['target_revision']
    queue = []
    accepted_risks = []
    severity_order = {'blocking': 0, 'material': 1, 'minor': 2}
    for finding in sorted(report['findings'], key=lambda item: (severity_order[item['severity']], item['id'])):
        stale = finding['disposition'] == 'resolved' and (finding['checked_revision'] != target or not finding['recheck_evidence'].strip())
        if finding['disposition'] == 'open' or stale:
            queue.append({'id': finding['id'], 'severity': finding['severity'], 'owner': finding['owner'],
                          'finding': finding['finding'], 'evidence': finding['evidence'],
                          'action': 'recheck-current-revision' if stale else 'address-finding'})
        elif finding['disposition'] == 'accepted_risk':
            accepted_risks.append({'id': finding['id'], 'severity': finding['severity'], 'owner': finding['owner']})
    return {'contract_valid': not failures, 'contract_failures': failures,
            'recorded_revision': report['target_revision'], 'requested_revision': target,
            'revision_changed': revision_changed,
            'closure_ready': not failures and not revision_changed and report['recommendation'] == 'pass',
            'recommendation': report['recommendation'], 'remediation_queue': queue, 'accepted_risks': accepted_risks,
            'note': 'Readiness reflects supplied audit bookkeeping, not independent verification or release authority.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('plan')
    plan.add_argument('file', type=Path)
    plan.add_argument('--accepted', action='append', default=[])
    comparison = commands.add_parser('compare-plans')
    comparison.add_argument('before', type=Path)
    comparison.add_argument('after', type=Path)
    evidence = commands.add_parser('evidence')
    evidence.add_argument('file', type=Path)
    evidence.add_argument('--changed-source', action='append', default=[])
    audit = commands.add_parser('audit')
    audit.add_argument('file', type=Path)
    audit.add_argument('--target-revision')
    args = parser.parse_args()
    try:
        if args.command == 'compare-plans':
            result = compare_plans(load_json(args.before), load_json(args.after))
        elif args.command == 'evidence':
            result = inspect_evidence(load_json(args.file), args.changed_source)
        elif args.command == 'audit':
            result = inspect_audit(load_json(args.file), args.target_revision)
        else:
            result = inspect_plan(load_json(args.file), args.accepted)
        rendered = json.dumps({'ok': result.get('contract_valid', True), 'inspection': result}, indent=2, allow_nan=False)
    except (OSError, ValueError, RecursionError, OverflowError):
        print(json.dumps({'ok': False, 'error': 'records or inspection arguments are invalid or unreadable'}))
        return 1
    print(rendered)
    return 0 if result.get('contract_valid', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
