# Operator quickstart

Use only the records the task needs. A simple self-contained task can stay solo
with a concise inline brief. The skill is instruction-only; the optional Python
tools read local files, check records and print results.

## Before dispatch

1. Write the outcome, original acceptance criteria and exact permitted actions.
2. Review the [routing plan](routing-plans.md). Select solo or state a concrete
   delegation benefit, give each output one owner and order its dependencies.
3. Give each delegated role the [six-field brief](../templates/role-brief.md).
   Validate JSON briefs with `scripts/check.py brief` before dispatch.
4. If work is open-ended, define [execution limits](execution-budgets.md) and
   preserve review capacity. The checker does not enforce runtime limits.

The bundled plan is a complete fictional small-internal-tool example. Inspect it:

```sh
python3 scripts/check.py plan templates/routing-plan.json --json
python3 scripts/check.py evidence templates/evidence-ledger.json --json
python3 scripts/check.py audit templates/audit-closure.json --json
```

On Windows, use your verified Python launcher or interpreter in place of
`python3`. No install, account connection or network request is required.

## During work and integration

Carry source revisions and unresolved claims in an [evidence ledger](evidence-ledgers.md).
Accept dependent outputs using the [handoff receipt](handoffs.md). When a worker
reports completion, inspect the contracted artifact before releasing the next
stage. Keep partial results visible when a worker stops or scope changes.

Use [audit closure](audit-closure.md) for important work. Give the Auditor the
original criteria and exact output revision. Correct significant findings and
recheck the delivered revision. The final answer must state incomplete work and
unresolved risks even if a record passes structural validation.

## Evaluate and distribute

For measured comparisons, follow the [paired evaluation protocol](../evals/README.md).
Keep synthetic tool checks distinct from empirical results. Preserve failed and
interrupted runs, shared inputs and independent scoring evidence.

Before installation, [compare package bytes with reviewed source](package-verification.md).
The CLI never installs the skill or grants permissions. Keep production access,
transport authentication and enforcement in the deployment environment.

## Troubleshooting

| Failure | Bounded correction |
| --- | --- |
| Unreadable JSON | Check UTF-8 encoding, unique keys, finite numbers and the 1 MiB limit. |
| Unknown contract field | Correct its spelling against the shipped schema; do not silently discard it. |
| Dependency cycle | Clarify which output must exist first; keep mutually dependent work with one owner. |
| Multiple write owners | Assign one owner and receive proposed changes from other roles. |
| Missing evidence reference | Add the inspected source or preserve the claim as unsupported. |
| Audit revision mismatch | Recheck the revision actually being delivered. |
| Incomplete evaluation pair | Retain the failed or interrupted row and mark unverified checks. |
| Archive mismatch | Stop installation and reconcile the reviewed source revision and archive. |
