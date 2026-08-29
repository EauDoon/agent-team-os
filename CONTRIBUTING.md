# Contributing

Contributions should improve clarity, generality, or verification without making the skill heavier than the tasks it coordinates.

## Design requirements

- Keep roles generic and task-scoped.
- Delegate only for a distinct output or a specific risk reduction.
- Define role, access scope, task, evidence, output contract, and stop condition for every delegated role.
- Preserve the Auditor checks for correctness, assumptions, contradictions, risks, and request satisfaction.
- State clearly that role separation is not a security boundary.
- Keep examples fictional and limited to the three documented scenario categories.
- Avoid identifying details, sensitive data, external assets, and runtime dependencies.
- Write skill instructions in concise imperative language.

## Change process

1. Explain the coordination problem the change addresses.
2. Make the smallest change that resolves it.
3. Update metadata when the triggering behavior changes.
4. Run `python3 scripts/validate.py` and inspect the generated package checksum when packaging is part of the change.
5. Check all repository text for unfinished markers, identifying details, disallowed punctuation, and credential-like strings.
6. Review the complete change against the original purpose and safety boundaries.

By contributing, you agree that your contribution is released under the MIT License.
