#!/usr/bin/env python3
"""Author bounded local records without overwriting existing files."""

import argparse
import copy
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

try:
    from .check import MAX_BYTES, check_document, load_json
except ImportError:
    from check import MAX_BYTES, check_document, load_json


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


def compose_message(kind: str, version: str, sender: str, recipient: str,
                    message_id: str, correlation_id: str, payload: dict) -> dict:
    if version != 'agent-team-connect/v0.2' or kind not in {'handoff', 'response'}:
        raise ValueError('new messages require the explicit v0.2 authoring contract')
    if any(not isinstance(value, str) or not value.strip()
           for value in (sender, recipient, message_id, correlation_id)):
        raise ValueError('message identifiers must not be blank')
    message = {'connect_version': version, 'type': kind, 'from': sender, 'to': recipient,
               'message_id': message_id, 'correlation_id': correlation_id, 'payload': copy.deepcopy(payload)}
    if check_document('connect', message):
        raise ValueError('message does not conform')
    if kind == 'response' and (payload.get('accepted') is not False or
            any(not payload[field].strip() for field in ('refusal_reason', 'next_step'))):
        raise ValueError('refusal needs an actionable reason and next step')
    return message


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    brief = commands.add_parser('brief', help='compose all six fields explicitly')
    for field in ('role', 'scope', 'task', 'evidence', 'deliver', 'stop'):
        brief.add_argument('--' + field, required=True)
    brief.add_argument('--output', type=Path, required=True)
    for name in ('handoff', 'refusal'):
        command = commands.add_parser(name, help='compose an explicitly negotiated v0.2 message')
        command.add_argument('--version', choices=['agent-team-connect/v0.2'], required=True)
        command.add_argument('--from', dest='sender', required=True)
        command.add_argument('--to', dest='recipient', required=True)
        command.add_argument('--message-id', required=True)
        command.add_argument('--correlation-id', required=True)
        command.add_argument('--output', type=Path, required=True)
        if name == 'handoff':
            command.add_argument('--brief', type=Path, required=True)
        else:
            command.add_argument('--reason', required=True)
            command.add_argument('--next-step', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'brief':
            document = compose_brief(args.role, args.scope, args.task, args.evidence, args.deliver, args.stop)
        else:
            payload = {'role_brief': load_json(args.brief)} if args.command == 'handoff' else {
                'accepted': False, 'refusal_reason': args.reason, 'next_step': args.next_step}
            document = compose_message('handoff' if args.command == 'handoff' else 'response',
                                       args.version, args.sender, args.recipient, args.message_id,
                                       args.correlation_id, payload)
        write_new_json(args.output, document)
    except (OSError, ValueError, UnicodeError, RecursionError):
        print(json.dumps({'ok': False, 'error': 'record could not be authored; check fields and a new writable output path'}))
        return 1
    print(json.dumps({'ok': True, 'kind': args.command}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
