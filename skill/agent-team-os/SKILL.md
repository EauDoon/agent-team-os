---
name: agent-team-os
description: Coordinate complex, multi-step work across task-scoped specialist AI agents by defining roles, access, evidence, output contracts, stop conditions, integration, and independent auditing. Use when a request benefits from distinct discovery, analysis, construction, or verification outputs, or when delegation reduces a specific risk.
---

# Agent Team

## Coordinate the work

1. Restate the requested outcome, constraints, available evidence, authorized actions, and completion test.
2. Keep the task with one agent unless a specialist role will improve a distinct output or reduce a specific risk.
3. Select the minimum useful roles and give each one a complete role brief.
4. Sequence dependent work and run independent work concurrently only when outputs cannot contaminate one another.
5. Require each role to return evidence, assumptions, status, and gaps with its contracted output.
6. Integrate outputs against the original request. Resolve conflicts rather than stacking incompatible conclusions.
7. Run the Auditor on important results, address material findings, and deliver one coherent answer.

## Use task-scoped roles

- Assign the Orchestrator to frame the task, choose roles, sequence work, integrate outputs, and own request satisfaction.
- Assign the Scout to gather and organize permitted evidence. Prevent it from silently converting missing evidence into conclusions.
- Assign the Analyst to interpret evidence, compare options, expose assumptions, and reason about tradeoffs.
- Assign the Maker to create or revise the requested artifact within the authorized write scope.
- Assign the Auditor to independently check the result and identify required corrections.

Treat these roles as temporary assignments, not persistent identities. Do not assume continuity, memory, authority, or trust from one task to another. Treat role separation as a coordination pattern, not a security boundary. Enforce real access limits with explicit permissions and the execution environment.

## Write every role brief

Specify all six fields before delegation:

```text
Role: The selected task-scoped role.
Access scope: The exact sources, tools, actions, and read or write limits allowed.
Task: The distinct question, artifact, or risk the role owns.
Evidence: The inputs to inspect and the traceability required for claims.
Output contract: The format, contents, quality bar, and recipient of the result.
Stop condition: The event that ends work, including completion, blocking gaps, or scope conflict.
```

Reject a brief that omits a field, duplicates another role, or gives broader access than its task needs.

## Apply the delegation gate

- Delegate only when the expected benefit is explicit.
- Name the distinct output or specific risk reduction for each role.
- Keep one owner for every decision and artifact.
- Avoid parallel assignments that produce competing untraceable edits.
- Do not delegate merely to increase activity or role count.
- Do not let a role widen its own access, redefine the request, or invent missing authorization.
- Combine roles when separation adds overhead without improving quality or independence.

## Enforce stop conditions

Stop a role when it completes its contract, exhausts permitted evidence, encounters conflicting instructions, requires wider scope, or reaches diminishing returns. Require a concise partial result with status, evidence inspected, gaps, and the decision needed to continue. Do not keep a role active after its useful work ends.

## Audit independently

Require the Auditor to check:

- correctness against inspected evidence;
- explicit and hidden assumptions;
- contradictions within and across outputs;
- material risks, omissions, and uncertainty;
- satisfaction of the original request, constraints, and output format.

Require the Auditor to distinguish blocking, material, and minor findings. Trace each finding to evidence or a reproducible check. Send material findings to the owning role for correction, then recheck the changed result. Do not treat silence, confidence, or role labels as proof.

## Deliver one result

Have the Orchestrator summarize the outcome, evidence basis, assumptions, unresolved risks, and any uncompleted request. Preserve uncertainty instead of filling gaps. Obtain explicit authorization before any consequential external action that was not already authorized.
