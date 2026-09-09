#!/usr/bin/env python3
"""Author bounded local records without overwriting existing files."""

import argparse
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

try:
    from .check import check_document, MAX_BYTES
except ImportError:
    from check import check_document, MAX_BYTES


def write_new_text(path: Path, text: str) -> None:
    """Publish complete UTF-8 bytes exclusively, using a same-directory hard link."""
    raw = text.encode('utf-8')
    if len(raw) > MAX_BYTES:
        raise ValueError('authored record exceeds 1 MiB')
    staged = None
    try:
        with NamedTemporaryFile(dir=path.parent, prefix='.agent-team-', delete=False) as handle:
            staged = Path(handle.name)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(staged, path)
    finally:
        if staged is not None:
            staged.unlink()


def write_new_json(path: Path, value: object) -> None:
    write_new_text(path, json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + '\n')


def compose_brief(role: str, scope: str, task: str, evidence: str, deliver: str, stop: str) -> dict:
    fields = ['role', 'access_scope', 'task', 'evidence', 'output_contract', 'stop_condition']
    values = [role, scope, task, evidence, deliver, stop]
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError('each brief field needs meaningful text')
    brief = dict(zip(fields, values))
    brief['role_brief_version'] = 'agent-team-role-brief/v0.1'
    if check_document('brief', brief):
        raise ValueError('brief does not conform')
    return brief


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    brief = commands.add_parser('brief', help='compose all six fields explicitly')
    for field in ('role', 'scope', 'task', 'evidence', 'deliver', 'stop'):
        brief.add_argument('--' + field, required=True)
    brief.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        document = compose_brief(args.role, args.scope, args.task, args.evidence, args.deliver, args.stop)
        write_new_json(args.output, document)
    except (OSError, ValueError, UnicodeError, RecursionError):
        print(json.dumps({'ok': False, 'error': 'record could not be authored; check fields and a new writable output path'}))
        return 1
    print(json.dumps({'ok': True, 'kind': args.command}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
