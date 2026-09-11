# Agent Team 0.4.0

This release makes changed inputs and blocked work actionable in the existing
local operator workflow. Python 3.11 or later and the standard library suffice.

- [Record inspection](record-inspection.md) propagates blockers, reopens dependent
  acceptance and groups ready work within a declared concurrency budget.
- Plan comparisons trace downstream rechecks through old and new dependencies.
  Evidence comparisons identify changed sources, claims and their review scope.
- Explicit review dates flag stale, future or unknown source inspection dates.
  Owner filters preserve global audit failures and closure status.
- [Authoring](authoring.md) copies exact assignment briefs from checked plans.
  Handoff inspection checks response correlation, version and endpoints, reports
  recorded response acceptance and leaves handoff-specific binding unverified.
  Its output grants no acceptance or release of dependent work.
- [Packet receipts](packets.md) name added, removed, invalid and changed records
  while preserving strict byte and order checks.

These are local inspection and authoring tools. They do not dispatch work,
authenticate agents, enforce permissions, inspect referenced sources or establish
performance superiority. No installed skill or wire schema changed. Dates and
acceptance remain explicit operator assertions; no saved state is rewritten.
