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

`ready_batches` groups currently ready IDs alphabetically into batches no larger
than the declared `max_parallel`. With no concurrency budget it is `null`,
not an assumed unlimited batch. Empty readiness produces no batches. These
are review suggestions, not a scheduler or a claim that capacity is available;
finish or stop existing work and inspect actual tool limits before dispatch.

When an accepted output changes, repeat `--accepted` for the original accepted
set and pass `--invalidate ID`. Inspection removes that acceptance and all
accepted downstream dependents before recomputing readiness. `invalidated`
lists the resulting recheck scope. Unknown, duplicate and unaccepted seed IDs
fail. No saved plan or acceptance record is rewritten.

Use `plan FILE --blocked requirements` to identify a blocked assignment and all
its transitive dependents. Repeat the flag for multiple blockers. Blocked work
cannot appear ready; an accepted assignment cannot also be blocked. These are
operator assertions for inspection and never change execution state.

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

`recheck_assignments` includes surviving changed assignments and transitive
dependents in either the old or new dependency graph. Removed inputs still
trigger rechecks of their former consumers. Global objective, completion or
budget changes conservatively flag every surviving assignment. This is an
impact review queue, not automatic rejection of previously accepted work.

## Trace changed evidence to affected claims

```sh
python3 scripts/inspect_records.py evidence templates/evidence-ledger.json --changed-source brief-a
```

The report maps sources to claim IDs and lists unresolved claims, assumptions,
unused sources and claims affected by the explicitly named source changes.
Repeat `--changed-source` for multiple sources, or omit it for a coverage view.
Unknown or duplicate source IDs fail. An affected supported claim is flagged
for reinspection, not silently relabeled unsupported. The ledger stays unchanged;
the operator must inspect the new evidence and revise claims deliberately.

## Inspect audit remediation and stale closure

Add `evidence FILE --as-of 12-09-2026 --max-age-days 2` for reproducible date
review. Dates use DD-MM-YYYY, both options are required, and age equal to the
limit remains current. Older, future and unparseable inspection dates are
separate lists and their claims enter `affected_claims` via `review_sources`.
`changed_sources` still means only explicitly named changes. With no date
options, `freshness` is `null`. No system clock, source retrieval or implicit
freshness policy is used; success means the inspection ran, not fresh evidence.

Compare two saved ledgers with `compare-evidence old.json new.json`. The report
lists added, removed and changed sources and claims, ignoring record and source
reference order. `recheck_claims` links changed source metadata to surviving
claims from either snapshot, plus new or edited claims. Source locator,
revision and inspection-date changes all count. No referenced source is opened.

```sh
python3 scripts/inspect_records.py audit templates/audit-closure.json
python3 scripts/inspect_records.py audit templates/audit-closure.json --target-revision fictional-tool-r3
```

The severity-ordered queue names each open or stale finding, its owner, evidence
and next action. Resolved findings become recheck work when the requested target
revision differs. Accepted risks stay visible separately. A pass recommendation
with an unresolved significant finding returns `ok: false` and exit status 1
while retaining the actionable queue. Structurally malformed reports receive
the generic input error. `closure_ready` refers only to supplied bookkeeping;
the command does not independently verify the artifact or authorize release.

Use `audit FILE --owner maker` to give one recorded owner their remediation
queue and accepted risks. Unknown or blank owners fail rather than silently
returning no work. `total_remediation_count`, contract failures, exit status and
`closure_ready` still reflect the complete report, so filtering cannot hide a
blocking finding owned by someone else.
