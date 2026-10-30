"""Semantic checks for operator records. These never schedule or execute work."""

import re
import unicodedata

try:
    from .contracts import json_equal
except ImportError:
    from contracts import json_equal

MAX_RESOURCES_PER_ASSIGNMENT = 256
MAX_TOTAL_WRITE_RESOURCES = 1024
MAX_ROUTING_DIAGNOSTICS = 32
# The connect.md capability vocabulary, in sorted order. validate.py checks
# that the specification's bullet list and this tuple stay identical.
BASELINE_CAPABILITIES = ('audit', 'bounded-scope', 'evidence-trace', 'route', 'structured-gaps')
CAPABILITY_TOKEN = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
MAX_ERROR_FAILURES = 20


class RecordError(ValueError):
    """A documented record or argument rule failed.

    The message names the rule in fixed tool text and never contains input.
    ``failures`` optionally carries schema diagnostics whose undeclared keys
    are already masked; at most 20 are kept. The class lives here, not in
    check.py, because check.py imports this module, and this module imports
    only contracts.py, which imports no sibling. Every tool can raise it
    without an import cycle.
    """

    def __init__(self, reason: str, failures: list[str] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.failures = [str(item) for item in (failures or [])][:MAX_ERROR_FAILURES]

    def details(self) -> dict:
        """Return the additive ``reason`` and optional ``failures`` keys for CLI output."""
        details = {'reason': self.reason}
        if self.failures:
            details['failures'] = self.failures
        return details


def identity_key(value: str) -> str:
    """Normalize an identity for independence checks.

    Two IDs that differ only by case, surrounding whitespace or a Unicode
    compatibility form (a fullwidth letter, for example) name one person.
    """
    return unicodedata.normalize('NFKC', value).strip().casefold()


def resource_key(value: str) -> str:
    """Normalize a write resource name for ownership comparison.

    Separators are unified and names compare without case. A precomposed
    accent and a base letter with a combining accent render identically, so
    canonically equivalent spellings are one name: the NFC form of the case
    fold of the NFD form, which is Unicode canonical caseless matching.
    """
    folded = unicodedata.normalize('NFD', value.replace('\\', '/').strip('/')).casefold()
    return unicodedata.normalize('NFC', folded)


def routing_violations(plan: dict) -> list[str]:
    assignments = plan['assignments']
    if any(len(item['write_resources']) > MAX_RESOURCES_PER_ASSIGNMENT for item in assignments):
        return ['assignments: at most 256 write resources are allowed per assignment']
    if sum(len(item['write_resources']) for item in assignments) > MAX_TOTAL_WRITE_RESOURCES:
        return ['assignments: at most 1024 total write resources are allowed']
    errors = []
    by_id = {item['id']: item for item in assignments}
    if len(by_id) != len(assignments):
        errors.append('assignments: duplicate ID')
    outputs = [item['output'] for item in assignments]
    if len(set(outputs)) != len(outputs):
        errors.append('assignments: each output must have one owner')
    for item in assignments:
        for dependency in item['depends_on']:
            if dependency not in by_id:
                errors.append(f"{item['id']}: unknown dependency {dependency}")
    remaining = {key: set(item['depends_on']) for key, item in by_id.items()}
    while remaining:
        ready = {key for key, dependencies in remaining.items() if not dependencies}
        if not ready:
            errors.append('assignments: dependency cycle or unresolved dependency')
            break
        remaining = {key: dependencies - ready for key, dependencies in remaining.items() if key not in ready}
    # Index path components instead of comparing every pair of resources. An
    # exact owner detects a parent conflict; subtree owners detect descendants.
    def node():
        return {'children': {}, 'exact': set(), 'owners': set()}

    resources = node()
    for item in assignments:
        for resource in item['write_resources']:
            normalized = resource_key(resource)
            if not normalized or any(part in {'.', '..', ''} for part in normalized.split('/')):
                errors.append(f"{item['id']}: use an unambiguous write resource name")
                continue
            current = resources
            visited = [current]
            conflicts = set()
            for part in normalized.split('/'):
                conflicts.update(current['exact'] - {item['id']})
                if part not in current['children']:
                    current['children'][part] = node()
                current = current['children'][part]
                visited.append(current)
            conflicts.update(current['owners'] - {item['id']})
            if conflicts:
                errors.append(f"write resource has multiple owners: {min(conflicts)}, {item['id']}")
            current['exact'].add(item['id'])
            for prefix in visited:
                prefix['owners'].add(item['id'])
    if plan['route'] == 'solo' and len(assignments) != 1:
        errors.append('solo route requires exactly one assignment')
    budget = plan.get('budget')
    if budget:
        if len(assignments) > budget['max_assignments']:
            errors.append('budget: plan exceeds assignment limit')
        if budget['max_parallel'] > budget['max_assignments']:
            errors.append('budget: concurrency exceeds assignment limit')
        if budget['review_reserve'] >= budget['total_work_units']:
            errors.append('budget: review reserve must leave capacity for task work')
    if len(errors) > MAX_ROUTING_DIAGNOSTICS:
        return errors[:MAX_ROUTING_DIAGNOSTICS] + ['additional routing diagnostics omitted']
    return errors


def evidence_violations(ledger: dict) -> list[str]:
    errors = []
    source_ids = [source['id'] for source in ledger['sources']]
    claim_ids = [claim['id'] for claim in ledger['claims']]
    if len(set(source_ids)) != len(source_ids):
        errors.append('sources: duplicate ID')
    if len(set(claim_ids)) != len(claim_ids):
        errors.append('claims: duplicate ID')
    for claim in ledger['claims']:
        for reference in claim['source_ids']:
            if reference not in source_ids:
                errors.append(f"{claim['id']}: unknown source {reference}")
        if claim['status'] == 'supported' and not claim['source_ids']:
            errors.append(f"{claim['id']}: supported claim needs an inspected source")
        if claim['status'] == 'conflicting' and len(claim['source_ids']) < 2:
            errors.append(f"{claim['id']}: conflicting claim needs both source references")
        if claim['status'] in {'conflicting', 'unsupported'} and not claim['next_step'].strip():
            errors.append(f"{claim['id']}: unresolved evidence needs a next step")
    return errors


def refusal_text_violations(message: object) -> list[str]:
    """Reject a v0.2 refusal whose reason or next step is only whitespace.

    ``minLength: 1`` accepts a string of spaces. v0.1 stays permissive.
    """
    if not isinstance(message, dict) or message.get('connect_version') != 'agent-team-connect/v0.2':
        return []
    if message.get('type') != 'response':
        return []
    payload = message.get('payload')
    if not isinstance(payload, dict) or payload.get('accepted') is not False:
        return []
    errors = []
    for field in ('refusal_reason', 'next_step'):
        value = payload.get(field)
        if isinstance(value, str) and value and not value.strip():
            errors.append(f'$.payload.{field}: refusal text must not be blank')
    return errors


def _string_list(value: object, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RecordError(f'{label} must be a list of strings')
    return value


def negotiation_sets(request: object, advertised: list[str]) -> tuple[list[str], list[str]]:
    """Return ``(missing, negotiated)`` for a request, as connect.md defines them.

    ``R`` is the request's required capabilities, ``Ci`` the capabilities the
    initiator offers and ``Co`` the capabilities the Orchestrator advertises:
    ``missing = sorted(R - Co)`` and ``negotiated = sorted((Ci | R) & Co)``.
    """
    advertised = capability_tokens(advertised, 'advertised capabilities')
    if not isinstance(request, dict) or request.get('type') != 'request':
        raise RecordError('negotiation needs a request message')
    payload = request.get('payload')
    if not isinstance(payload, dict):
        raise RecordError('request payload must be an object')
    required = set(_string_list(payload.get('required_capabilities'), 'required capabilities'))
    offered = set(_string_list(request.get('capabilities'), 'offered capabilities'))
    supported = set(advertised)
    return sorted(required - supported), sorted((offered | required) & supported)


def negotiate(request: object, advertised: list[str]) -> dict:
    """Compute the response payload an Orchestrator owes a connect request.

    This is the reference implementation of the connect.md negotiation rules.
    It decides only; it sends nothing and grants no permission.
    """
    missing, negotiated = negotiation_sets(request, advertised)
    if missing:
        joined = ', '.join(missing)
        return {'accepted': False,
                'refusal_reason': 'missing required capabilities: ' + joined,
                'next_step': 'authorize or remove: ' + joined}
    return {'accepted': True, 'negotiated_capabilities': negotiated}


def audit_violations(report: dict) -> list[str]:
    errors = []
    if isinstance(report.get('target_revision'), str) and not report['target_revision'].strip():
        errors.append('audit: target revision must not be blank')
    if not report['author'].strip() or not report['auditor'].strip():
        errors.append('audit: author and auditor must not be blank')
    if identity_key(report['author']) == identity_key(report['auditor']):
        errors.append('audit: author and independent auditor must be distinct')
    ids = [finding['id'] for finding in report['findings']]
    if len(set(ids)) != len(ids):
        errors.append('findings: duplicate ID')
    for finding in report['findings']:
        if finding['disposition'] == 'resolved':
            if finding['checked_revision'] != report['target_revision'] or not finding['recheck_evidence'].strip():
                errors.append(f"{finding['id']}: resolution needs a recheck of the target revision")
        elif report['recommendation'] == 'pass' and finding['severity'] in {'blocking', 'material'}:
            errors.append(f"{finding['id']}: unresolved significant finding prevents pass")
    return errors


MAX_CONNECTION_MESSAGES = 256
MAX_CONNECTION_FAILURES = 32
CONNECTION_NOTE = ('Checks message order and envelope consistency against the connect.md lifecycle only. '
                   'A status is attributed to a handoff recipient, not to a specific handoff, because '
                   'neither wire version names one. Negotiated-set presence, status senders and one wire '
                   'version per connection interpret the lifecycle and participants table. The report '
                   'authenticates no sender, prevents no replay and grants no permission.')


def distinct_messages(messages: list) -> tuple[list[tuple[int, dict]], list[dict], list[dict]]:
    """Split delivered messages by ``message_id``, keeping delivery order.

    Returns ``(distinct, redelivered, conflicts)``. ``distinct`` holds each
    first delivery as ``(position, message)`` with 1-based positions. A later
    delivery with identical JSON content is a redelivery; one with different
    content is a conflict (docs/handoffs.md step 4). Neither enters
    ``distinct``.
    """
    first: dict[str, dict] = {}
    distinct, redelivered, conflicts = [], [], []
    for position, message in enumerate(messages, 1):
        message_id = message['message_id']
        if message_id not in first:
            first[message_id] = message
            distinct.append((position, message))
        elif json_equal(first[message_id], message):
            redelivered.append({'position': position, 'message_id': message_id})
        else:
            conflicts.append({'position': position, 'message_id': message_id})
    return distinct, redelivered, conflicts


def capability_tokens(values: object, label: str) -> list[str]:
    """Validate a list of unique, lowercase, hyphen-separated capability tokens."""
    tokens = _string_list(values, label)
    if any(CAPABILITY_TOKEN.match(token) is None for token in tokens):
        raise RecordError(f'{label} must be lowercase hyphen-separated tokens')
    if len(set(tokens)) != len(tokens):
        raise RecordError(f'{label} must be unique')
    return tokens


def connection_report(messages: list, *, check, advertised: list[str] | None = None,
                      require_closed: bool = False) -> dict:
    """Check one recorded connect exchange against the connect.md lifecycle.

    ``messages`` are supplied in delivery order. ``check`` returns the
    conformance failures of one message under its declared version; the
    lifecycle rules run only when every message conforms. Rule numbers match
    docs/record-inspection.md. Nothing is sent, stored or authorized.
    """
    if not isinstance(messages, list) or not messages:
        raise RecordError('supply at least one connect message')
    if len(messages) > MAX_CONNECTION_MESSAGES:
        raise RecordError('a connection inspection accepts at most 256 messages')
    if advertised is not None:
        advertised = capability_tokens(advertised, 'advertised capabilities')
    failures: list[dict] = []
    observations: list[dict] = []

    def fail(rule: str, position: int, message: object, text: str) -> None:
        message_id = message.get('message_id') if isinstance(message, dict) else None
        failures.append({'rule': rule, 'position': position,
                         'message_id': message_id if isinstance(message_id, str) else None,
                         'failure': text})

    def observe(kind: str, position: int, message: dict, **detail) -> None:
        observations.append({'observation': kind, 'position': position,
                             'message_id': message['message_id'], **detail})

    report = {'contract_valid': False, 'connect_version': None, 'correlation_id': None,
              'initiator': None, 'orchestrator': None, 'messages': len(messages),
              'distinct_messages': None, 'accepted': None, 'negotiated': None, 'handoffs': [],
              'open_handoffs': [], 'closed': False, 'request_satisfied': None, 'redelivered': [],
              'failure_count': 0, 'failures': [], 'observations': observations, 'note': CONNECTION_NOTE}

    for position, message in enumerate(messages, 1):
        if check(message):
            fail('R1', position, message, 'message does not conform to its declared connect version')
    if not failures:
        _connection_lifecycle(messages, report, fail, observe, advertised, require_closed)
    report['failure_count'] = len(failures)
    report['failures'] = failures[:MAX_CONNECTION_FAILURES]
    report['contract_valid'] = not failures
    return report


def _connection_lifecycle(messages, report, fail, observe, advertised, require_closed) -> None:
    distinct, redelivered, conflicts = distinct_messages(messages)
    report['distinct_messages'] = len(distinct)
    report['redelivered'] = redelivered
    for conflict in conflicts:
        fail('R4', conflict['position'], messages[conflict['position'] - 1],
             'message_id was delivered again with different content')
    first = messages[0]
    report['connect_version'] = first['connect_version']
    report['correlation_id'] = first['correlation_id']
    for position, message in enumerate(messages, 1):
        if message['connect_version'] != first['connect_version']:
            fail('R2', position, message, 'connect_version differs from the first message')
        if message['correlation_id'] != first['correlation_id']:
            fail('R3', position, message, 'correlation_id differs from the first message')

    position, request = distinct[0]
    if request['type'] != 'request':
        fail('R5', position, request, 'the first message must be the request')
        return
    initiator, orchestrator = request['from'], request['to']
    report['initiator'], report['orchestrator'] = initiator, orchestrator
    required = request['payload'].get('required_capabilities', [])
    offered = request.get('capabilities', [])
    expected = negotiate(request, advertised) if advertised is not None else None

    response = result = None
    recipients: set[str] = set()
    last_state: dict[str, str] = {}
    for index, (position, message) in enumerate(distinct[1:], 1):
        kind = message['type']
        if result is not None and kind != 'result':
            fail('R11', position, message, 'the result must be the last message')
        elif response is not None and response['payload']['accepted'] is False:
            fail('R8', position, message, 'only redeliveries may follow a refusal')
        if kind == 'request':
            fail('R5', position, message, 'a connection has exactly one request')
        elif kind == 'response':
            if index != 1 or response is not None:
                fail('R6', position, message, 'the single response must directly follow the request')
                continue
            response = message
            if message['from'] != orchestrator or message['to'] != initiator:
                fail('R6', position, message, 'the response must go from the Orchestrator to the initiator')
            _check_response(position, message, required, offered, advertised, expected, fail, observe, report)
        elif index == 1:
            fail('R6', position, message, 'the second message must be the response')
        elif kind == 'handoff':
            if message['from'] != orchestrator:
                fail('R9', position, message, 'a handoff must come from the Orchestrator')
            recipients.add(message['to'])
            report['handoffs'].append({'position': position, 'message_id': message['message_id'],
                                       'to': message['to'], 'role': message['payload']['role_brief']['role']})
        elif kind == 'status':
            if message['to'] != orchestrator or message['from'] not in recipients:
                fail('R10', position, message,
                     'a status must go to the Orchestrator from the recipient of an earlier handoff')
            payload = message['payload']
            last_state[message['from']] = payload['state']
            if payload['state'] == 'gap' and not str(payload.get('decision_needed', '')).strip():
                observe('gap_without_decision', position, message)
        else:
            if result is not None:
                fail('R11', position, message, 'a connection has at most one result')
                continue
            result = message
            if message['from'] != orchestrator or message['to'] != initiator:
                fail('R11', position, message, 'the result must go from the Orchestrator to the initiator')
            report['request_satisfied'] = message['payload']['request_satisfied']
            open_now = sorted(name for name in recipients if last_state.get(name) not in {'done', 'blocked'})
            report['open_handoffs'] = open_now
            if open_now:
                observe('open_handoffs', position, message, recipients=open_now)
            unresolved = sorted(name for name, state in last_state.items() if state in {'gap', 'blocked'})
            if message['payload']['request_satisfied'] is True and unresolved:
                observe('satisfied_with_open_gaps', position, message, recipients=unresolved)
            if response is not None and response['payload']['accepted'] is True:
                negotiated = response['payload'].get('negotiated_capabilities', [])
                recorded = message.get('capabilities')
                if (recorded is None and negotiated) or (recorded is not None and set(recorded) != set(negotiated)):
                    fail('R12', position, message, 'result capabilities differ from the negotiated set')
    if result is None:
        report['open_handoffs'] = sorted(name for name in recipients
                                         if last_state.get(name) not in {'done', 'blocked'})
    refused = response is not None and response['payload']['accepted'] is False
    report['closed'] = refused or result is not None
    if require_closed and not report['closed']:
        position, message = distinct[-1]
        fail('R13', position, message, 'the connection must end in a refusal or a result')


def _check_response(position, message, required, offered, advertised, expected, fail, observe, report) -> None:
    payload = message['payload']
    report['accepted'] = payload['accepted']
    if payload['accepted']:
        negotiated = payload.get('negotiated_capabilities')
        report['negotiated'] = negotiated
        if negotiated is None:
            fail('R7', position, message, 'an accepted response must carry negotiated_capabilities')
        else:
            if negotiated != sorted(negotiated):
                fail('R7', position, message, 'negotiated_capabilities must be sorted')
            if not set(required) <= set(negotiated) <= set(offered) | set(required):
                fail('R7', position, message,
                     'negotiated_capabilities must include every required and only offered or required capabilities')
    if expected is None:
        return
    if expected['accepted'] is False or payload['accepted'] is True:
        if payload != expected:
            fail('R7', position, message, 'the response differs from the negotiation rules for the advertised set')
    elif payload['refusal_reason'].startswith('missing required capabilities:'):
        fail('R7', position, message, 'the refusal names missing capabilities the advertised set supplies')
    else:
        observe('non_capability_refusal', position, message)
