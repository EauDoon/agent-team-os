#!/usr/bin/env python3
"""Check an explicit local packet of operator records without executing them."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

try:
    from .author import write_new_json
    from .check import (
        ROOT,
        check_document,
        load_json,
        parse_json_bytes,
        read_json_bytes,
    )
    from .contracts import violations
    from .evaluate import summarize
except ImportError:
    from author import write_new_json
    from check import ROOT, check_document, load_json, parse_json_bytes, read_json_bytes
    from contracts import violations
    from evaluate import summarize

MAX_PACKET_BYTES = 4 * 1024 * 1024


def record_path(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if relative.is_absolute() or relative.as_posix() != name or '\\' in name or ':' in name or '\0' in name:
        raise ValueError('record path must be canonical and relative')
    if any(part in {'.', '..'} for part in relative.parts) or not relative.parts:
        raise ValueError('record path cannot traverse parents')
    candidate = root
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError('record references cannot use symbolic links')
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError('record must be a file inside the packet directory')
    return resolved


def inspect_closure(packet: dict, records: list[dict], documents: dict,
                    target_revision: str | None) -> dict:
    """Check explicitly selected closure records from the already read snapshots."""
    closure = packet.get('closure')
    failures = []
    if closure is None:
        return {'ready': False, 'requested_revision': target_revision,
                'failure_count': 1,
                'failures': ['closure: expected revision requires a v0.2 packet']}
    target = closure['target_revision']
    if not target.strip():
        failures.append('closure: target revision must not be blank')
    if target_revision is not None and target != target_revision:
        failures.append('closure: target revision does not match the requested revision')
    by_id = {record['id']: record for record in records}
    if any(not record['ok'] for record in records):
        failures.append('closure: all packet records must conform')

    def selected(field, kind):
        key = closure[field]
        record = by_id.get(key)
        if record is None or record['kind'] != kind or not record['ok']:
            failures.append(f'closure.{field}: requires a conforming {kind} record in this packet')
            return None
        return documents[key]

    audit = selected('audit_record', 'audit')
    evidence = selected('evidence_record', 'evidence')
    if audit is not None:
        if audit['target_revision'] != target:
            failures.append('closure.audit_record: audit targets a different revision')
        if audit['recommendation'] != 'pass':
            failures.append('closure.audit_record: audit recommendation must be pass')
    if evidence is not None:
        sources = {source['id']: source for source in evidence['sources']}
        source = sources.get(closure['target_source'])
        if source is None or source['revision'] != target:
            failures.append('closure.target_source: requires an evidence source at the target revision')
        claims = {claim['id']: claim for claim in evidence['claims']}
        for key in closure['required_claims']:
            claim = claims.get(key)
            if claim is None or claim['status'] != 'supported' or closure['target_source'] not in claim['source_ids']:
                failures.append(f'closure.required_claims: {key} must be supported by the target source')
    return {'ready': not failures, 'target_revision': target, 'requested_revision': target_revision,
            'failure_count': len(failures), 'failures': failures[:20],
            'note': 'Closure checks declared support and revision consistency only; they do not inspect artifacts, authenticate review or grant release authority.'}


def inspect_packet(path: Path, schema_root: Path = ROOT, *, target_revision: str | None = None) -> dict:
    if target_revision is not None and (not isinstance(target_revision, str) or not target_revision.strip()):
        raise ValueError('expected target revision must not be blank')
    raw_index = read_json_bytes(path)
    packet = parse_json_bytes(raw_index)
    schema = 'schemas/packet.schema.json'
    if isinstance(packet, dict) and packet.get('packet_version') == 'agent-team-packet/v0.2':
        schema = 'schemas/packet-v0.2.schema.json'
    if violations(packet, load_json(schema_root / schema)):
        raise ValueError('packet index is invalid')
    ids = [item['id'] for item in packet['records']]
    paths = [item['path'].casefold() for item in packet['records']]
    if len(set(ids)) != len(ids) or len(set(paths)) != len(paths):
        raise ValueError('packet record IDs and paths must be unique')
    total = len(raw_index)
    records = []
    documents = {}
    for item in packet['records']:
        result = {**item, 'ok': False, 'sha256': None, 'bytes': None}
        try:
            raw = read_json_bytes(record_path(path.parent, item['path']))
            total += len(raw)
            if total > MAX_PACKET_BYTES:
                raise OverflowError('packet exceeds the total byte budget')
            document = parse_json_bytes(raw)
            result.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
            if item['kind'] == 'evaluation':
                summarize(document, load_json(schema_root / 'evals/tasks.json'))
                failures = []
            else:
                failures = check_document(item['kind'], document, schema_root=schema_root)
            result.update(ok=not failures, failure_count=len(failures), failures=failures[:20])
            if not failures:
                documents[item['id']] = document
        except (OSError, ValueError, RecursionError):
            result.update(failure_count=1, failures=['record is invalid, unreadable or outside the allowed packet paths'])
        records.append(result)
    result = {'ok': all(item['ok'] for item in records), 'packet_version': packet['packet_version'],
            'task_id': packet['task_id'], 'index_sha256': hashlib.sha256(raw_index).hexdigest(),
            'total_bytes': total, 'records': records,
            'note': 'Packet checks establish record conformance, not task completion, authorization or independent review.'}
    if 'closure' in packet or target_revision is not None:
        result['closure'] = inspect_closure(packet, records, documents, target_revision)
        result['ok'] = result['ok'] and result['closure']['ready']
    return result


def make_receipt(result: dict) -> dict:
    if not result['ok']:
        raise ValueError('invalid packets cannot receive receipts')
    return {'receipt_version': 'agent-team-packet-receipt/v0.1',
            'task_id': result['task_id'], 'index_sha256': result['index_sha256'],
            'records': [{key: item[key] for key in ('id', 'kind', 'path', 'sha256', 'bytes')}
                        for item in result['records']]}


def verify_receipt(result: dict, receipt: dict) -> dict:
    if violations(receipt, load_json(ROOT / 'schemas/packet-receipt.schema.json')):
        raise ValueError('receipt is invalid')
    ids = [item['id'] for item in receipt['records']]
    paths = [item['path'].casefold() for item in receipt['records']]
    if len(set(ids)) != len(ids) or len(set(paths)) != len(paths):
        raise ValueError('receipt record IDs and paths must be unique')
    # Compare only the explicitly supplied packet. Receipt paths never trigger reads.
    current = make_receipt(result) if result['ok'] else None
    differences = ['packet_conformance'] if current is None else [
        key for key in ('task_id', 'index_sha256', 'records') if receipt[key] != current[key]]
    old = {item['id']: item for item in receipt['records']}
    new = {item['id']: item for item in result['records']}
    changes = []
    for key in sorted(old.keys() & new.keys()):
        fields = sorted(field for field in ('kind', 'path', 'sha256', 'bytes') if old[key][field] != new[key][field])
        if fields:
            changes.append({'id': key, 'fields': fields})
    report = {'ok': not differences, 'matches': not differences, 'differences': differences,
            'records_added': sorted(new.keys() - old.keys()), 'records_removed': sorted(old.keys() - new.keys()),
            'record_changes': changes, 'invalid_records': sorted(item['id'] for item in result['records'] if not item['ok']),
            'record_order_changed': set(old) == set(new) and list(old) != list(new),
            'note': 'A matching receipt establishes byte consistency, not authenticity, authorization or review.'}
    if 'closure' in result:
        report['closure'] = result['closure']
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--target-revision', help='require v0.2 closure for this independently expected revision')
    output = parser.add_mutually_exclusive_group()
    output.add_argument('--receipt', type=Path, help='write a new exact-byte receipt after all checks pass')
    output.add_argument('--verify-receipt', type=Path, help='compare current checked bytes with a receipt')
    args = parser.parse_args()
    try:
        result = inspect_packet(args.file, target_revision=args.target_revision)
        if args.receipt and result['ok']:
            write_new_json(args.receipt, make_receipt(result))
        if args.verify_receipt:
            result = verify_receipt(result, load_json(args.verify_receipt))
        rendered = json.dumps(result, indent=2, allow_nan=False)
    except (OSError, ValueError, RecursionError, OverflowError):
        print(json.dumps({'ok': False, 'error': 'packet is invalid, unreadable or exceeds its limits'}))
        return 1
    print(rendered)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
