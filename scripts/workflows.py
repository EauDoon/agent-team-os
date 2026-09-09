"""Semantic checks for operator records. These never schedule or execute work."""

MAX_RESOURCES_PER_ASSIGNMENT = 256
MAX_TOTAL_WRITE_RESOURCES = 1024
MAX_ROUTING_DIAGNOSTICS = 32


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
                errors.append(f"write resource has multiple owners: {sorted(conflicts)[0]}, {item['id']}")
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


def audit_violations(report: dict) -> list[str]:
    errors = []
    if report['author'] == report['auditor']:
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
