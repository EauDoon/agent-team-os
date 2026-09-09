#!/usr/bin/env python3
"""Check an explicit local packet of operator records without executing them."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

try:
    from .check import ROOT, check_document, load_json, parse_json_bytes, read_json_bytes
    from .contracts import violations
    from .evaluate import summarize
except ImportError:
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


def inspect_packet(path: Path) -> dict:
    raw_index = read_json_bytes(path)
    packet = parse_json_bytes(raw_index)
    if violations(packet, load_json(ROOT / 'schemas/packet.schema.json')):
        raise ValueError('packet index is invalid')
    ids = [item['id'] for item in packet['records']]
    paths = [item['path'].casefold() for item in packet['records']]
    if len(set(ids)) != len(ids) or len(set(paths)) != len(paths):
        raise ValueError('packet record IDs and paths must be unique')
    total = len(raw_index)
    records = []
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
                summarize(document, load_json(ROOT / 'evals/tasks.json'))
                failures = []
            else:
                failures = check_document(item['kind'], document)
            result.update(ok=not failures, failure_count=len(failures), failures=failures[:20])
        except (OSError, ValueError, RecursionError):
            result.update(failure_count=1, failures=['record is invalid, unreadable or outside the allowed packet paths'])
        records.append(result)
    return {'ok': all(item['ok'] for item in records), 'packet_version': packet['packet_version'],
            'task_id': packet['task_id'], 'index_sha256': hashlib.sha256(raw_index).hexdigest(),
            'total_bytes': total, 'records': records,
            'note': 'Packet checks establish record conformance, not task completion, authorization or independent review.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    try:
        result = inspect_packet(args.file)
        rendered = json.dumps(result, indent=2, allow_nan=False)
    except (OSError, ValueError, RecursionError, OverflowError):
        print(json.dumps({'ok': False, 'error': 'packet is invalid, unreadable or exceeds its limits'}))
        return 1
    print(rendered)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
