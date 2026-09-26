#!/usr/bin/env python3
"""Run a fully synthetic local operator journey; no worker or real tool is run."""

import argparse
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'fictional-tool-r2'


def write(path, document):
    path.write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8')


def walkthrough(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    complete = output / 'complete'
    complete.mkdir()
    checks = []

    def run(label, tool, *args, expected=0, closure_ready=None, difference=None, failure=None):
        command = [sys.executable, str(ROOT / 'scripts' / tool), *map(str, args)]
        result = subprocess.run(command, cwd=output, capture_output=True, text=True, timeout=10)
        report = json.loads(result.stdout)
        checks.append({'case': label, 'command': command, 'exit_code': result.returncode, 'report': report})
        write(output / 'transcript.json', checks)
        if result.returncode != expected or report['ok'] != (expected == 0) or result.stderr:
            raise ValueError('unexpected walkthrough result: ' + label)
        closure = report.get('closure', {})
        if closure_ready is not None and closure.get('ready') is not closure_ready:
            raise ValueError('unexpected closure readiness: ' + label)
        if difference is not None and report.get('differences') != [difference]:
            raise ValueError('unexpected receipt difference: ' + label)
        if failure is not None and not any(failure in item for item in closure.get('failures', [])):
            raise ValueError('missing closure diagnostic: ' + label)
        return report

    run('author-brief', 'author.py', 'brief', '--role', 'Maker',
        '--scope', 'Fictional tool and synthetic tests only.',
        '--task', 'Reject empty work-item titles in the fictional tracker.',
        '--evidence', 'Synthetic acceptance case empty-title.',
        '--deliver', 'A revision with the empty-title result recorded.',
        '--stop', 'Stop after the synthetic acceptance case is recorded.',
        '--output', complete / 'brief.json')
    run('check-brief', 'check.py', 'brief', complete / 'brief.json', '--json')
    run('author-handoff', 'author.py', 'handoff', '--version', 'agent-team-connect/v0.2',
        '--from', 'orchestrator', '--to', 'maker', '--message-id', 'synthetic-h1',
        '--correlation-id', 'synthetic-tool', '--brief', complete / 'brief.json',
        '--output', complete / 'handoff.json')
    run('check-handoff', 'check.py', 'connect', complete / 'handoff.json', '--json')

    evidence = {
        'ledger_version': 'agent-team-evidence/v0.1',
        'sources': [{'id': 'output', 'locator': 'Synthetic tracker acceptance record',
                     'revision': TARGET, 'inspected_on': '26-09-2026'}],
        'claims': [{'id': 'empty-title', 'statement': 'The fictional tracker rejects an empty title.',
                    'status': 'supported', 'source_ids': ['output'],
                    'reasoning': 'Illustrative declared result only; no tracker was executed.', 'next_step': ''}],
    }
    audit = {
        'audit_version': 'agent-team-audit/v0.1', 'target_revision': TARGET,
        'author': 'maker', 'auditor': 'auditor', 'recommendation': 'pass',
        'findings': [{'id': 'empty-title', 'severity': 'material',
                      'finding': 'Earlier synthetic revision accepted an empty title.', 'owner': 'maker',
                      'evidence': 'Synthetic empty-title case.', 'disposition': 'resolved',
                      'checked_revision': TARGET,
                      'recheck_evidence': 'Illustrative recheck says the case passed; no independent audit occurred.'}],
    }
    packet = {
        'packet_version': 'agent-team-packet/v0.2', 'task_id': 'synthetic-tool',
        'records': [{'id': name, 'kind': kind, 'path': name + '.json'} for name, kind in
                    [('brief', 'brief'), ('handoff', 'connect'), ('evidence', 'evidence'), ('audit', 'audit')]],
        'closure': {'audit_record': 'audit', 'evidence_record': 'evidence',
                    'target_revision': TARGET, 'target_source': 'output', 'required_claims': ['empty-title']},
    }
    for name, value in [('evidence', evidence), ('audit', audit), ('packet', packet)]:
        write(complete / (name + '.json'), value)
    run('check-evidence', 'check.py', 'evidence', complete / 'evidence.json', '--json')
    run('check-audit', 'check.py', 'audit', complete / 'audit.json', '--json')
    run('inspect-evidence', 'inspect_records.py', 'evidence', complete / 'evidence.json')
    run('inspect-audit', 'inspect_records.py', 'audit', complete / 'audit.json', '--target-revision', TARGET)
    run('complete-receipt', 'packet.py', complete / 'packet.json', '--target-revision', TARGET,
        '--receipt', complete / 'receipt.json', closure_ready=True)
    run('complete-verify', 'packet.py', complete / 'packet.json', '--target-revision', TARGET,
        '--verify-receipt', complete / 'receipt.json', closure_ready=True)

    failures = {'incomplete-claim': 'must be supported by the target source',
                'stale-audit': 'audit targets a different revision',
                'stale-source': 'requires an evidence source at the target revision',
                'missing-record': 'requires a conforming evidence record',
                'unrelated-support': 'must be supported by the target source'}
    for label, failure in failures.items():
        case = output / label
        shutil.copytree(complete, case)
        ledger, report = copy.deepcopy(evidence), copy.deepcopy(audit)
        if label == 'incomplete-claim':
            ledger['claims'][0].update(status='unsupported', next_step='Run the synthetic case on r2.')
        elif label == 'stale-audit':
            report['target_revision'] = report['findings'][0]['checked_revision'] = 'fictional-tool-r1'
        elif label == 'stale-source':
            ledger['sources'][0]['revision'] = 'fictional-tool-r1'
        elif label == 'unrelated-support':
            ledger['sources'].append({**ledger['sources'][0], 'id': 'other'})
            ledger['claims'][0]['source_ids'] = ['other']
        write(case / 'evidence.json', ledger)
        write(case / 'audit.json', report)
        if label == 'missing-record':
            (case / 'evidence.json').unlink()
        result = run(label, 'packet.py', case / 'packet.json', '--target-revision', TARGET,
                     '--receipt', case / 'new-receipt.json', expected=1, closure_ready=False, failure=failure)
        invalid_records = [item['id'] for item in result['records'] if not item['ok']]
        if invalid_records != (['evidence'] if label == 'missing-record' else []):
            raise ValueError('unexpected record conformance: ' + label)
        if (case / 'new-receipt.json').exists():
            raise ValueError('failed closure created a receipt')

    altered = output / 'altered-bytes'
    shutil.copytree(complete, altered)
    record = altered / 'evidence.json'
    record.write_bytes(record.read_bytes() + b'\n')
    run('altered-bytes', 'packet.py', altered / 'packet.json', '--target-revision', TARGET,
        '--verify-receipt', altered / 'receipt.json', expected=1, closure_ready=True, difference='records')

    replay = output / 'replayed-packet'
    shutil.copytree(complete, replay)
    # A coherent older packet can have a valid receipt. The receiver supplies r2.
    packet['closure']['target_revision'] = 'fictional-tool-r1'
    audit['target_revision'] = audit['findings'][0]['checked_revision'] = 'fictional-tool-r1'
    evidence['sources'][0]['revision'] = 'fictional-tool-r1'
    for name, value in [('packet', packet), ('audit', audit), ('evidence', evidence)]:
        write(replay / (name + '.json'), value)
    run('old-packet-receipt', 'packet.py', replay / 'packet.json', '--target-revision', 'fictional-tool-r1',
        '--receipt', replay / 'old-receipt.json', closure_ready=True)
    run('replayed-packet', 'packet.py', replay / 'packet.json', '--target-revision', TARGET,
        '--verify-receipt', replay / 'old-receipt.json', expected=1, closure_ready=False,
        difference='packet_conformance', failure='target revision does not match the requested revision')
    summary = {'ok': True, 'synthetic': True, 'checks': len(checks),
               'outcomes': [{'case': check['case'], 'exit_code': check['exit_code']} for check in checks],
               'note': 'These fixtures test record handling only; they are not tool performance or independent review evidence.'}
    write(output / 'summary.json', summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new directory for synthetic records and transcript')
    args = parser.parse_args()
    print(json.dumps(walkthrough(args.output.resolve()), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
