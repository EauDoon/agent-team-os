# Bound work and stop cleanly

Use a budget for expensive or open-ended work. The routing-plan template has an
optional `budget` object, checked by the same plan CLI. It names an observable
`work_unit`, total units, a review reserve, assignment and concurrency limits,
and a maximum number of correction rounds. Omitting this optional object does
not mean unlimited work; the brief's stop condition still applies.

The fictional plan uses bounded role attempts as its work unit. For a real task,
define how attempts, retries and integration consume that unit before starting.
Use a measurable token or elapsed-time budget only when the environment can
report it reliably. Do not fabricate precise usage from an unmeasured estimate.

Track execution with [a checkpoint](../templates/execution-checkpoint.md). Reserve
capacity for integration and review before dispatch. Check remaining capacity
before adding an assignment or granting another revision. Stop when a limit is
reached, the benefit disappears, the scope changes, or a required action lacks
authorization. A budget can stop work; it cannot authorize broader actions.

On stop, cancel pending work and request active workers to stop. Wait for their
acknowledgments before reassigning shared resources. Reconcile uncertain effects
and retain partial evidence. Report what is accepted, what is incomplete, and
the bounded decision needed to continue. Do not claim completion merely because
the budget has ended, and do not continue unchanged revision loops.

These are operator records. The checker validates plan consistency but does not
meter usage, schedule work, cancel processes or enforce runtime limits.
