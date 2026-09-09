"""Semantic checks for operator records. These never schedule or execute work."""


def routing_violations(plan: dict) -> list[str]:
    assignments = plan['assignments']
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
    owners = []
    for item in assignments:
        for resource in item['write_resources']:
            normalized = resource.replace('\\', '/').strip('/').casefold()
            if not normalized or any(part in {'.', '..', ''} for part in normalized.split('/')):
                errors.append(f"{item['id']}: use an unambiguous write resource name")
            for previous, owner in owners:
                if owner != item['id'] and (normalized == previous or normalized.startswith(previous + '/') or previous.startswith(normalized + '/')):
                    errors.append(f"write resource has multiple owners: {owner}, {item['id']}")
            owners.append((normalized, item['id']))
    if plan['route'] == 'solo' and len(assignments) != 1:
        errors.append('solo route requires exactly one assignment')
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
