# Contributing

Contributions should improve clarity, generality, or verification without making the skill heavier than the work it supports.

## Design requirements

- Keep roles generic and task-scoped.
- Keep the coordination protocol out of the package; it belongs to the host runtime.
- Define role, access scope, task, evidence, output contract, and stop condition for every delegated role.
- A change in a field's meaning needs a new schema or wire version.
- State clearly that role separation is not a security boundary.
- Keep examples fictional and limited to the three documented scenario categories.
- Avoid identifying details, sensitive data, external assets, and runtime dependencies.
- Add every new file under `conformance/`, `docs/`, `evals/`, `examples/`, `schemas/`, `scripts/`, `skill/` or `templates/` to `package-manifest.json`; `scripts/validate.py` fails when a distributable file is left out.
- Write skill instructions in concise imperative language.

## Change process

1. Explain the contract or tooling problem the change addresses.
2. Make the smallest change that resolves it.
3. Update metadata when the triggering behavior changes.
4. Add an entry under `## [Unreleased]` in `CHANGELOG.md`, in the Added, Changed or Fixed section that fits.
5. Run `make ci`, which runs every CI step in order. Without `make` (on Windows, for example), run `py scripts/validate.py`, `py -m unittest discover -s tests -v`, `py evals/runner.py`, `py scripts/package.py --output dist` and `py scripts/verify_package.py dist/agent-team-<version>.zip`, where `py scripts/version.py` prints the version.
6. Check all repository text for unfinished markers, identifying details, disallowed punctuation, and credential-like strings.
7. Review the complete change against the original purpose and safety boundaries.

By contributing, you agree that your contribution is released under the MIT License.
