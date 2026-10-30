#!/usr/bin/env python3
"""Author bounded local records without overwriting existing files."""

import argparse
import copy
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

try:
    from .check import MAX_BYTES, check_document, load_json, shape_failures
    from .version import add_version_flag
    from .workflows import RecordError, capability_tokens, negotiate
except ImportError:
    from check import MAX_BYTES, check_document, load_json, shape_failures
    from version import add_version_flag
    from workflows import RecordError, capability_tokens, negotiate

GENERIC_ERROR = 'record could not be authored; check fields and a new writable output path'


def conformance_error(reason: str, kind: str, document: object) -> RecordError:
    return RecordError(reason, shape_failures(kind, document))


def write_new_text(path: Path, text: str) -> None:
    """Publish complete UTF-8 bytes exclusively, using a same-directory hard link."""
    raw = text.encode('utf-8')
    if len(raw) > MAX_BYTES:
        raise RecordError('authored record exceeds 1 MiB')
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


WIRE_VERSION = 'agent-team-connect/v0.2'
MESSAGE_KINDS = ('request', 'response', 'handoff', 'status', 'result')


def text_values(values: list[str] | None, label: str, *, unique: bool = False) -> list[str]:
    """Return repeated flag values, refusing blank text and, when asked, repeats."""
    values = [] if values is None else list(values)
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise RecordError(f'{label} must not be blank')
    if unique and len(set(values)) != len(values):
        raise RecordError(f'{label} must be unique')
    return values


def compose_brief(role: str, scope: str, task: str, evidence: str, deliver: str, stop: str,
                  prohibited: list[str] | None = None) -> dict:
    fields = ['role', 'access_scope', 'task', 'evidence', 'output_contract', 'stop_condition']
    values = [role, scope, task, evidence, deliver, stop]
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise RecordError('each brief field needs meaningful text')
    brief = dict(zip(fields, values))
    brief['role_brief_version'] = 'agent-team-role-brief/v0.1'
    if prohibited:
        brief['prohibited_actions'] = text_values(prohibited, 'prohibited actions')
    if check_document('brief', brief):
        raise conformance_error('brief does not conform', 'brief', brief)
    return brief


def compose_message(kind: str, version: str, sender: str, recipient: str,
                    message_id: str, correlation_id: str, payload: dict, *,
                    capabilities: list[str] | None = None) -> dict:
    if version != WIRE_VERSION or kind not in MESSAGE_KINDS:
        raise RecordError('new messages require the explicit v0.2 authoring contract')
    if any(not isinstance(value, str) or not value.strip()
           for value in (sender, recipient, message_id, correlation_id)):
        raise RecordError('message identifiers must not be blank')
    message = {'connect_version': version, 'type': kind, 'from': sender, 'to': recipient,
               'message_id': message_id, 'correlation_id': correlation_id}
    if capabilities is not None:
        message['capabilities'] = list(capabilities)
    message['payload'] = copy.deepcopy(payload)
    if check_document('connect', message):
        raise conformance_error('message does not conform', 'connect', message)
    if kind == 'response' and payload.get('accepted') is False and any(
            not payload[field].strip() for field in ('refusal_reason', 'next_step')):
        raise RecordError('refusal needs an actionable reason and next step')
    return message


def compose_handoff(sender: str, recipient: str, message_id: str, correlation_id: str, brief: object,
                    evidence: list[str] | None = None) -> dict:
    payload = {'role_brief': brief}
    if evidence:
        payload['evidence'] = text_values(evidence, 'handoff evidence identifiers', unique=True)
    return compose_message('handoff', WIRE_VERSION, sender, recipient, message_id, correlation_id, payload)


def compose_request(sender: str, recipient: str, message_id: str, correlation_id: str, objective: str,
                    completion_test: str, *, constraints: list[str] | None = None,
                    required: list[str] | None = None, offered: list[str] | None = None) -> dict:
    if any(not isinstance(value, str) or not value.strip() for value in (objective, completion_test)):
        raise RecordError('a request needs a meaningful objective and completion test')
    payload = {'objective': objective, 'completion_test': completion_test}
    if constraints:
        payload['constraints'] = text_values(constraints, 'request constraints')
    if required:
        payload['required_capabilities'] = capability_tokens(required, 'required capabilities')
    return compose_message('request', WIRE_VERSION, sender, recipient, message_id, correlation_id, payload,
                           capabilities=capability_tokens(offered, 'offered capabilities') if offered else None)


def compose_response(request: object, advertised: list[str] | None, message_id: str) -> dict:
    """Write the reply the negotiation rules owe a conforming v0.2 request."""
    if (not isinstance(request, dict) or request.get('connect_version') != WIRE_VERSION
            or request.get('type') != 'request' or check_document('connect', request)):
        raise RecordError('a response needs a conforming v0.2 request')
    payload = negotiate(request, [] if advertised is None else advertised)
    return compose_message('response', WIRE_VERSION, request['to'], request['from'], message_id,
                           request['correlation_id'], payload)


def compose_status(sender: str, recipient: str, message_id: str, correlation_id: str, state: str, *,
                   evidence_inspected: list[str] | None = None, gaps: list[str] | None = None,
                   decision_needed: str | None = None) -> dict:
    payload = {'state': state}
    if evidence_inspected:
        payload['evidence_inspected'] = text_values(evidence_inspected, 'inspected evidence identifiers', unique=True)
    if gaps:
        payload['gaps'] = text_values(gaps, 'status gaps')
    if decision_needed is not None:
        if not isinstance(decision_needed, str) or not decision_needed.strip():
            raise RecordError('a decision needed must not be blank')
        payload['decision_needed'] = decision_needed
    if state == 'gap' and decision_needed is None:
        raise RecordError('a gap status needs the decision required to continue')
    return compose_message('status', WIRE_VERSION, sender, recipient, message_id, correlation_id, payload)


def result_capabilities(response: object, capabilities: list[str] | None, sender: str, recipient: str,
                        correlation_id: str) -> list[str]:
    """Return the negotiated set a result records, from exactly one source."""
    if (response is None) == (capabilities is None):
        raise RecordError('a result needs exactly one capability source: a response or capabilities')
    if capabilities is not None:
        return sorted(capability_tokens(capabilities, 'result capabilities'))
    if (not isinstance(response, dict) or response.get('connect_version') != WIRE_VERSION
            or response.get('type') != 'response' or check_document('connect', response)
            or response['payload']['accepted'] is not True
            or 'negotiated_capabilities' not in response['payload']):
        raise RecordError('a result needs an accepted v0.2 response that records negotiated capabilities')
    if response['correlation_id'] != correlation_id:
        raise RecordError('result correlation must match the response')
    if response['from'] != sender or response['to'] != recipient:
        raise RecordError('result endpoints must match the response')
    return list(response['payload']['negotiated_capabilities'])


def compose_result(sender: str, recipient: str, message_id: str, correlation_id: str, summary: str,
                   satisfied: bool, *, response: object = None, capabilities: list[str] | None = None,
                   evidence_basis: list[str] | None = None, assumptions: list[str] | None = None,
                   risks: list[str] | None = None) -> dict:
    if not isinstance(summary, str) or not summary.strip():
        raise RecordError('a result needs a meaningful summary')
    if not isinstance(satisfied, bool):
        raise RecordError('a result must state whether the request is satisfied')
    recorded = result_capabilities(response, capabilities, sender, recipient, correlation_id)
    payload = {'summary': summary, 'request_satisfied': satisfied}
    if evidence_basis:
        payload['evidence_basis'] = text_values(evidence_basis, 'evidence basis identifiers', unique=True)
    if assumptions:
        payload['assumptions'] = text_values(assumptions, 'result assumptions')
    if risks:
        payload['unresolved_risks'] = text_values(risks, 'unresolved risks')
    return compose_message('result', WIRE_VERSION, sender, recipient, message_id, correlation_id, payload,
                           capabilities=recorded)


def brief_from_plan(plan: object, assignment_id: str) -> dict:
    if check_document('plan', plan):
        raise conformance_error('routing plan does not conform', 'plan', plan)
    for assignment in plan['assignments']:
        if assignment['id'] == assignment_id:
            return copy.deepcopy(assignment['brief'])
    raise RecordError('assignment is not in the routing plan')


def envelope_arguments(command: argparse.ArgumentParser, *, endpoints: bool = True) -> None:
    command.add_argument('--version', choices=[WIRE_VERSION], required=True,
                         help='the connect wire version both participants agreed; only v0.2 is authored')
    if endpoints:
        command.add_argument('--from', dest='sender', required=True)
        command.add_argument('--to', dest='recipient', required=True)
        command.add_argument('--correlation-id', required=True)
    command.add_argument('--message-id', required=True)
    command.add_argument('--output', type=Path, required=True, help='a new file; never replaces existing work')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # Package version on the top-level parser only: the message subcommands
    # keep their own --version for the connect wire version.
    add_version_flag(parser)
    commands = parser.add_subparsers(dest='command', required=True)
    brief = commands.add_parser('brief', help='compose all six fields explicitly')
    for field in ('role', 'scope', 'task', 'evidence', 'deliver', 'stop'):
        brief.add_argument('--' + field, required=True)
    brief.add_argument('--prohibit', action='append', metavar='TEXT',
                       help='an action the role must not take, written to prohibited_actions; repeat for each')
    brief.add_argument('--output', type=Path, required=True)
    plan = commands.add_parser('plan-brief', help='copy one exact brief from a validated routing plan')
    plan.add_argument('file', type=Path)
    plan.add_argument('--assignment', required=True)
    plan.add_argument('--output', type=Path, required=True)

    request = commands.add_parser('request', help='compose a v0.2 connection request')
    envelope_arguments(request)
    request.add_argument('--objective', required=True)
    request.add_argument('--completion-test', required=True)
    request.add_argument('--constraint', action='append', metavar='TEXT', help='a hard limit; repeat for each')
    request.add_argument('--require', action='append', metavar='CAP',
                         help='a capability the connection must support; repeat for each')
    request.add_argument('--offer', action='append', metavar='CAP',
                         help='a capability the initiator offers, written to the envelope; repeat for each')
    response = commands.add_parser('response', help='compose the reply the negotiation rules owe a v0.2 request')
    envelope_arguments(response, endpoints=False)
    response.add_argument('--request', type=Path, required=True, help='the conforming v0.2 request to answer')
    response.add_argument('--advertise', action='append', metavar='CAP',
                          help='a capability the Orchestrator advertises; repeat for each')
    for name in ('handoff', 'refusal'):
        command = commands.add_parser(name, help='compose an explicitly negotiated v0.2 message')
        envelope_arguments(command)
        if name == 'handoff':
            command.add_argument('--brief', type=Path, required=True)
            command.add_argument('--evidence', action='append', metavar='ID',
                                 help='an input the role may inspect, written to payload.evidence; repeat for each')
        else:
            command.add_argument('--reason', required=True)
            command.add_argument('--next-step', required=True)
    status = commands.add_parser('status', help='compose a v0.2 progress, gap, blocked or done status')
    envelope_arguments(status)
    status.add_argument('--state', choices=['working', 'gap', 'blocked', 'done'], required=True)
    status.add_argument('--evidence-inspected', action='append', metavar='ID', help='an input inspected; repeat')
    status.add_argument('--gap', action='append', metavar='TEXT', help='missing or weak evidence; repeat')
    status.add_argument('--decision-needed', metavar='TEXT', help='the decision required to continue; required for gap')
    result = commands.add_parser('result', help='compose the final v0.2 result with the negotiated set')
    envelope_arguments(result)
    result.add_argument('--summary', required=True)
    result.add_argument('--satisfied', choices=['yes', 'no'], required=True,
                        help='whether the objective and completion test are met')
    result.add_argument('--evidence-basis', action='append', metavar='ID', help='evidence the result rests on; repeat')
    result.add_argument('--assumption', action='append', metavar='TEXT', help='an assumption made; repeat')
    result.add_argument('--risk', action='append', metavar='TEXT', help='a risk or gap still open; repeat')
    source = result.add_mutually_exclusive_group(required=True)
    source.add_argument('--response', type=Path,
                        help='the accepted v0.2 response whose negotiated set the result records')
    source.add_argument('--capability', action='append', metavar='CAP',
                        help='a negotiated capability to record when no response file is at hand; repeat')
    args = parser.parse_args()
    try:
        if args.command == 'brief':
            document = compose_brief(args.role, args.scope, args.task, args.evidence, args.deliver, args.stop,
                                     args.prohibit)
        elif args.command == 'plan-brief':
            document = brief_from_plan(load_json(args.file), args.assignment)
        elif args.command == 'handoff':
            document = compose_handoff(args.sender, args.recipient, args.message_id, args.correlation_id,
                                       load_json(args.brief), args.evidence)
        elif args.command == 'refusal':
            document = compose_message('response', args.version, args.sender, args.recipient, args.message_id,
                                       args.correlation_id, {'accepted': False, 'refusal_reason': args.reason,
                                                             'next_step': args.next_step})
        elif args.command == 'request':
            document = compose_request(args.sender, args.recipient, args.message_id, args.correlation_id,
                                       args.objective, args.completion_test, constraints=args.constraint,
                                       required=args.require, offered=args.offer)
        elif args.command == 'response':
            document = compose_response(load_json(args.request), args.advertise, args.message_id)
        elif args.command == 'status':
            document = compose_status(args.sender, args.recipient, args.message_id, args.correlation_id, args.state,
                                      evidence_inspected=args.evidence_inspected, gaps=args.gap,
                                      decision_needed=args.decision_needed)
        else:
            document = compose_result(args.sender, args.recipient, args.message_id, args.correlation_id,
                                      args.summary, args.satisfied == 'yes',
                                      response=None if args.response is None else load_json(args.response),
                                      capabilities=args.capability, evidence_basis=args.evidence_basis,
                                      assumptions=args.assumption, risks=args.risk)
        write_new_json(args.output, document)
    except RecordError as exc:
        print(json.dumps({'ok': False, 'error': GENERIC_ERROR, **exc.details()}))
        return 1
    except (OSError, ValueError, UnicodeError, RecursionError):
        print(json.dumps({'ok': False, 'error': GENERIC_ERROR}))
        return 1
    print(json.dumps({'ok': True, 'kind': args.command}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
