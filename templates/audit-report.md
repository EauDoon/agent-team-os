# Audit report

Use this report for an independent check of an important result. The Auditor
does not become the owner of the artifact and does not widen the approved
scope.

## Audit target

- Artifact or decision:
- Owning role:
- Version or run identifier:

## Role brief coverage

Record the six required fields used by the audited role:

- Role:
- Access scope:
- Task:
- Evidence:
- Output contract:
- Stop condition:

## Evidence inspected

List each source, output, test, or reproducible check inspected. Separate
observed evidence from assumptions.

## Findings

Group findings as **blocking**, **material**, or **minor**. Every finding must
include a source or reproducible check and the owning role.

| ID | Severity | Finding | Evidence or check | Owner | Disposition |
| --- | --- | --- | --- | --- | --- |
| Stable ID | blocking/material/minor | Describe observed issue | Source or reproducible check | Responsible role | open/resolved/accepted risk |

## Closure checks

For every resolved finding, record its ID, corrected artifact revision, recheck
method, observed result and reviewer. Match the rechecked revision to the audit
target. Reopen affected findings when the target changes. Keep unresolved
blocking or material findings visible and do not recommend pass while they
remain. Distinguish the original independent assessment from later discussion.

## Contradictions and uncertainty

Record unresolved contradictions, missing evidence, and uncertainty. Do not
replace a gap with confidence.

## Request and safety checks

- Original request satisfied:
- Scope and permissions respected:
- Third-party effects considered:
- Consequential action separately authorized:

## Recommendation

Choose exactly one: **pass**, **revise**, or **blocked**. Explain the next
bounded decision and identify any required recheck.
