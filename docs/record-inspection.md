# Inspect records before the next decision

Show dependency stages and which assignments have accepted inputs:

```sh
python3 scripts/inspect_records.py plan templates/routing-plan.json
python3 scripts/inspect_records.py plan templates/routing-plan.json --accepted requirements
```

The fictional plan first makes requirements ready, then construction, then
review. `--accepted` is an explicit operator assertion, not a claim inferred from
a worker's completion status. Repeat it for each accepted assignment. Unknown,
duplicate or dependency-inconsistent accepted IDs fail the inspection.

Output includes deterministic stages, ready and waiting assignments, missing
accepted dependencies and any declared concurrency limit. Ready means only that
the supplied dependency assertions are sufficient. Scope, permission, capacity
and output acceptance still need the operator's review. The command never
dispatches work or writes acceptance state. Both script and module invocation
are supported, with JSON output and exit status 0 for success or 1 for invalid
input.

## Review a revised plan

```sh
python3 scripts/inspect_records.py compare-plans accepted-plan.json revised-plan.json
```

The comparison validates both plans, then reports added/removed assignments,
write resources and dependencies, changed brief fields and output ownership,
and changed objectives or budgets. Reordering assignments is not a change.
Resource names use the validator's case and separator normalization. Natural
language scope is shown as before/after text; the tool cannot decide whether a
rewrite grants permission or is semantically equivalent. Review changed scope
and stop obsolete owners before resuming work under a revised plan.
