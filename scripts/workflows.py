"""Semantic checks for operator records. These never schedule or execute work."""

import re
import unicodedata

MAX_RESOURCES_PER_ASSIGNMENT = 256
MAX_TOTAL_WRITE_RESOURCES = 1024
MAX_ROUTING_DIAGNOSTICS = 32
# The connect.md capability vocabulary, in sorted order. validate.py checks
# that the specification's bullet list and this tuple stay identical.
BASELINE_CAPABILITIES = ('audit', 'bounded-scope', 'evidence-trace', 'route', 'structured-gaps')
CAPABILITY_TOKEN = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')


def identity_key(value: str) -> str:
    """Normalize an identity for independence checks.

    Two IDs that differ only by case, surrounding whitespace or a Unicode
    compatibility form (a fullwidth letter, for example) name one person.
    """
    return unicodedata.normalize('NFKC', value).strip().casefold()


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
            normalized = resource.replace('\\', '/').strip('/').casefold()
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
        raise ValueError(f'{label} must be a list of strings')
    return value


def negotiation_sets(request: object, advertised: list[str]) -> tuple[list[str], list[str]]:
    """Return ``(missing, negotiated)`` for a request, as connect.md defines them.

    ``R`` is the request's required capabilities, ``Ci`` the capabilities the
    initiator offers and ``Co`` the capabilities the Orchestrator advertises:
    ``missing = sorted(R - Co)`` and ``negotiated = sorted((Ci | R) & Co)``.
    """
    advertised = _string_list(advertised, 'advertised capabilities')
    if any(CAPABILITY_TOKEN.match(token) is None for token in advertised):
        raise ValueError('advertised capabilities must be lowercase hyphen-separated tokens')
    if len(set(advertised)) != len(advertised):
        raise ValueError('advertised capabilities must be unique')
    if not isinstance(request, dict) or request.get('type') != 'request':
        raise ValueError('negotiation needs a request message')
    payload = request.get('payload')
    if not isinstance(payload, dict):
        raise ValueError('request payload must be an object')
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
