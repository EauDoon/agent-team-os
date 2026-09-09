# Agent Team 0.3.0

This release connects local authoring, inspection and evidence preservation into
a complete operator workflow. It uses Python 3.11 or later and the standard
library. The installed instruction-only skill and role boundaries are unchanged.

- [Authoring](authoring.md) creates complete six-field briefs and explicit v0.2
  handoffs or refusals, with required reasons and next steps.
- [Record inspection](record-inspection.md) explains dependency readiness, plan
  scope changes, source impact and revision-specific audit remediation.
- [Evaluation reports](../evals/README.md) preserve per-task checks and input
  digests, with escaped Markdown for review. Descriptive totals are not evidence
  of superiority; the calibration fixture remains synthetic and unmeasured.
- [Packets](packets.md) check an explicit bounded set of records, write a new
  exact-byte receipt and detect changed bytes when rechecked.

Existing connect v0.1 messages remain valid under their original schema. New
authoring explicitly selects v0.2; no tool silently upgrades a received message.
The package version does not replace the independently versioned wire contracts.

New-file exports require hard-link support in the destination filesystem and
fail safely when unavailable or the destination already exists. Records are
local data, never instructions to execute. Digests establish byte consistency,
not authenticity, permission, task completion or independent review.
