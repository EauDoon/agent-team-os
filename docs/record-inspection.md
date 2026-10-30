# Inspect records before the next decision

## Read a failure reason

Every inspection that cannot run prints `ok: false`, the unchanged generic
`error` and exit status 1. When a documented rule failed, the output also
carries `reason`, fixed tool text naming the rule, such as
`unknown accepted assignment`, `accepted assignments must include their
accepted dependencies`, `date must use DD-MM-YYYY` or
`record does not conform`. A non-conforming record adds `failures`: up to 20
schema diagnostics in the JSON-path form `scripts/check.py` prints, with every
field name the schema does not declare shown as `*`. Semantic rule diagnostics,
which can quote record IDs, are left to `scripts/check.py KIND FILE`.

Neither key ever contains input values, argument text or file paths. An
unreadable or oversized file, invalid JSON and other I/O failures keep the
generic `error` alone. Match on `reason`, not on `error`, to tell the rules
apart; the [troubleshooting table](operator-quickstart.md#troubleshooting)
maps the common ones to a correction.

## Check a whole connection

```sh
python3 scripts/inspect_records.py connection request.json response.json handoff.json status.json result.json --advertise bounded-scope --advertise evidence-trace --require-closed
```

Give the connect message files in delivery order: at most 256 files and 8 MiB
in total, each at most 1 MiB. Every message must conform to its declared
version first; the lifecycle rules run only when all of them do. A delivery
whose `message_id` and JSON content repeat an earlier one is listed under
`redelivered` and skipped. The rules, each with its source:

- R1. Every message conforms to its declared version
  ([connect.md](../connect.md#agent-team-connect), "A message must validate
  against its declared version").
- R2. One `connect_version` per connection. This interprets the versioning
  rules; [`handoff`](#compare-a-handoff-and-a-response-envelope) applies the
  same check to a pair.
- R3. One `correlation_id` per connection
  ([lifecycle](../connect.md#connection-lifecycle)).
- R4. A repeated `message_id` with different content is a conflict
  ([handoffs](handoffs.md), step 4).
- R5. Exactly one request, and it is the first message. Its `from` is the
  initiator and its `to` is the Orchestrator
  ([participants](../connect.md#participants)).
- R6. The single response directly follows the request and goes from the
  Orchestrator to the initiator (lifecycle step 2).
- R7. An accepted response carries `negotiated_capabilities`, sorted, holding
  every required capability and only offered or required ones
  ([negotiation](../connect.md#capability-negotiation)). With `--advertise`,
  a response must equal the rules' reply exactly, except that a refusal for
  another reason, such as a scope conflict or an authorization gap, is allowed
  when every required capability is advertised. It is recorded as the
  `non_capability_refusal` observation; a refusal that names missing
  capabilities the advertised set supplies fails.
- R8. Only redeliveries may follow a refusal (lifecycle diagram).
- R9. Every handoff comes from the Orchestrator (lifecycle step 3).
- R10. Every status goes to the Orchestrator from the recipient of an earlier
  handoff (participants table and lifecycle step 4). This attributes a status
  to a recipient, not to a specific handoff.
- R11. At most one result, from the Orchestrator to the initiator, and it is
  the last message (lifecycle step 5).
- R12. The result envelope `capabilities`, compared as a set, equals the
  negotiated set; it may be omitted only when that set is empty
  ([versioning](../connect.md#versioning-and-compatibility)). The 0.6.0
  result example broke this rule.
- R13. With `--require-closed`, the exchange ends in a refusal or a result.

Observations never fail the check. `open_handoffs` names recipients whose last
status is neither `done` nor `blocked` when the result arrives;
`satisfied_with_open_gaps` flags `request_satisfied: true` while a recipient's
last status is `gap` or `blocked`; `gap_without_decision` flags a `gap` status
without a `decision_needed` ([rejections and errors](../connect.md#rejections-and-errors-consumer-ux)).
`sent_at` is not judged.

The output reports the participants, the negotiated set, each handoff with its
recipient and role, whether the connection is `closed`, `request_satisfied`,
`failure_count` and the first 32 failures, each with its rule, position and
`message_id`. Exit status is 0 when the exchange conforms and 1 otherwise; an
unreadable file or a broken limit exits 1 with the generic input error and a
`reason`. The report establishes order and envelope consistency only. It does
not bind a status to a handoff, authenticate senders, prevent replay or grant
access. The [connection conformance suite](../conformance/connection/README.md)
pins the rules for other implementations.

## Compare a handoff and a response envelope

Run `python3 scripts/inspect_records.py handoff handoff.json response.json`.
Both messages must conform, share a version and correlation ID, reverse sender
and recipient, and use distinct message IDs. `contract_valid`, top-level `ok`
and exit status 0 mean only that these envelope checks passed. A mismatch
returns exit status 1 with `contract_valid: false` and the failures.

`recorded_acceptance` copies the response payload's `accepted` value even when
the envelopes mismatch. It is a recorded connection claim, never acceptance of
the supplied handoff. A refusal preserves its reason and next step.
`handoff_binding` is always `"unverified"`: both wire versions allow multiple
handoffs under one correlation ID, and responses identify no handoff message.
For example, `h1` and `h2` can share endpoints and correlation `c1`; a response
`r1` can pass the envelope checks with either handoff without establishing
acceptance of either one.

The new 0.4.0 inspection output has no inferred `accepted` field. Machine
consumers must treat `recorded_acceptance` as response data and must not release
dependent work from it, `contract_valid`, `ok` or exit status alone. Follow the
[handoff acceptance workflow](handoffs.md) to inspect and accept the exact
assignment and output revision. This command checks local bookkeeping only;
transport authentication, replay protection and real permissions remain external
duties. The v0.1 and v0.2 wire schemas are unchanged.

## Compute a capability negotiation

```sh
python3 scripts/inspect_records.py negotiate request.json --advertise evidence-trace --advertise bounded-scope
```

The request must be a conforming connect `request` under its declared version.
Repeat `--advertise` for each capability the Orchestrator advertises; tokens
must be unique, lowercase and hyphen-separated. The command applies the
[negotiation rules](../connect.md#capability-negotiation) and reports
`missing`, the sorted `negotiated` set and the exact `response_payload`, which
is checked against the declared version's response schema. Missing
capabilities are sorted and joined with a comma and a space in both refusal
fields. An accept and a refusal both exit 0; an invalid request, a non-request
message or a malformed token exits 1 with the generic input error and the
`reason` that names it (see [failure reasons](#read-a-failure-reason)).

The result is a decision only. The command sends no response, grants no
permission and does not record the negotiated set anywhere. To write the
response message itself, use
[`author.py response`](authoring.md#response), which applies the same rules to
a v0.2 request. The
[negotiation conformance suite](../conformance/negotiation/README.md) pins the
same rules for other implementations.

## Inspect dependency readiness

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

## Review a revised plan

```sh
python3 scripts/inspect_records.py compare-plans accepted-plan.json revised-plan.json
```

The comparison validates both plans, then reports added/removed assignments,
write resources and dependencies, changed brief fields and output ownership,
and changed objectives or budgets. Reordering assignments is not a change.
Resource names use the validator's case, Unicode and separator normalization. Natural
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

## Inspect audit remediation and stale closure

```sh
python3 scripts/inspect_records.py audit templates/audit-closure.json
python3 scripts/inspect_records.py audit templates/audit-closure.json --target-revision fictional-tool-r3
```

The severity-ordered queue names each open or stale finding, its owner, evidence
and next action. Resolved findings become recheck work when the requested target
revision differs. Accepted risks stay visible separately. A pass recommendation
with an unresolved significant finding returns `ok: false` and exit status 1
while retaining the actionable queue. Structurally malformed reports receive
the generic input error with `reason: "audit report shape is invalid"` and the
masked schema `failures`. `closure_ready` refers only to supplied bookkeeping;
the command does not independently verify the artifact or authorize release.

Use `audit FILE --owner maker` to give one recorded owner their remediation
queue and accepted risks. Unknown or blank owners fail rather than silently
returning no work. `total_remediation_count`, contract failures, exit status and
`closure_ready` still reflect the complete report, so filtering cannot hide a
blocking finding owned by someone else.
