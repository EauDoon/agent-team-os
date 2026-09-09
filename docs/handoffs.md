# Accept and resume work deliberately

A sender's `done` status means it stopped its assignment. It does not establish
that the receiving Orchestrator accepted the output or that the whole request
is satisfied. Use [a receipt](../templates/handoff-receipt.md) for important or
interrupted work. Small read-only handoffs can include the same facts inline.

1. Match the result to the task, assignment and brief revision. Treat an unknown
   or superseded assignment as needing reconciliation before integration.
2. Inspect the exact output revision against the brief's acceptance criteria.
   Record inspected evidence, not only the sender's confidence or claimed tests.
3. Accept the output, request a bounded correction, or preserve a blocking gap.
   Release dependent work only after the output it needs is accepted.
4. Track duplicate delivery by message ID within the task. A repeated ID with
   different content is a conflict. Do not repeat side effects on retry. The
   transport must implement durable idempotency if the deployment needs it.
5. On interruption, save completed effects and the last accepted revision.
   Reconcile current state before retrying a write whose outcome is uncertain.

For example, an internal-tool Maker can return `done` with a test failure
explicitly disclosed. The receiver records correction required and keeps the
dependent release step pending. After correction, the Auditor checks the new
revision, and the receiver records acceptance of that revision only.

Resumption does not extend permission, revive a revoked action, or turn a
partial result into completion. The Orchestrator must stop obsolete workers
before assigning the same write resource to a replacement.
