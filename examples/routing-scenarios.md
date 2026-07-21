# Synthetic Routing Scenarios

These fictional scenarios show how to add only roles that produce a distinct output or reduce a specific risk. Every assignment defines access scope, task, evidence, output contract, and stop condition.

## 1. Vendor comparison

Goal: compare three fictional vendors using only supplied capability briefs and a fixed set of criteria: functional fit, implementation effort, responsiveness, reliability, and exit effort.

| Role | Access scope | Task | Evidence | Output contract | Stop condition |
| --- | --- | --- | --- | --- | --- |
| Orchestrator | The request and supplied briefs | Confirm criteria, assign bounded work, integrate results | Original request and stated criteria | Decision frame, role briefs, and final comparison | Stop when the audited comparison answers the request or when a missing decision requires clarification |
| Scout | Supplied briefs only, read-only | Extract claims and mark missing information without ranking vendors | Exact statements from the briefs | Source table with claim, source location, and uncertainty | Stop after every criterion is covered or explicitly marked missing |
| Analyst | Scout source table and decision frame | Compare the vendors and explain tradeoffs | Sourced claims and stated criteria | Comparison matrix, reasoning, assumptions, and provisional conclusion | Stop when each conclusion traces to evidence or is labeled unsupported |
| Auditor | Original request, briefs, source table, and analysis | Check accuracy, assumptions, contradictions, risks, and request satisfaction | All supplied material and intermediate outputs | Findings grouped as blocking, material, or minor, plus a pass or revise recommendation | Stop when every material claim has been checked once and unresolved gaps are listed |

Do not add a Maker merely to reformat the Analyst output. That would duplicate work without producing a distinct result or reducing a named risk.

## 2. Customer-support workflow design

Goal: design a fictional support workflow for four supplied request categories with stated response goals and handoff rules.

| Role | Access scope | Task | Evidence | Output contract | Stop condition |
| --- | --- | --- | --- | --- | --- |
| Orchestrator | The request and supplied scenario packet | Define success, sequence discovery before design, and integrate the result | Original request, categories, goals, and constraints | Plan, role briefs, integrated workflow, and decision log | Stop when the audited workflow satisfies every stated constraint or clarification is required |
| Scout | Supplied scenario packet only, read-only | Map request categories, actors, entry points, handoffs, and missing facts | Scenario facts with precise source locations | Current-state map and open-question list | Stop when all supplied facts are mapped and unknowns are separated from facts |
| Analyst | Current-state map and stated goals | Identify failure points, ambiguous ownership, and avoidable handoffs | Scout map, goals, and constraints | Prioritized design requirements with reasoning and assumptions | Stop when each requirement links to a stated goal or identified failure point |
| Maker | Approved design requirements | Draft the future workflow, state transitions, ownership rules, and exception handling | Prioritized requirements and supplied constraints | A complete workflow specification and acceptance checklist | Stop when every requirement has an implemented workflow element or a documented gap |
| Auditor | Original request and all role outputs, read-only | Test correctness, assumptions, contradictions, risks, and request satisfaction | Scenario packet, maps, requirements, workflow, and checklist | Audit findings, failed cases, residual risks, and pass or revise recommendation | Stop after normal, ambiguous, and exception cases are checked against every acceptance item |

## 3. Building a small internal tool

Goal: build a fictional work-item tracker that accepts a title, owner label, status, and note, then supports listing and filtering the submitted items.

| Role | Access scope | Task | Evidence | Output contract | Stop condition |
| --- | --- | --- | --- | --- | --- |
| Orchestrator | The request, approved source area, and test area | Freeze the minimum feature set, assign implementation and audit work, and integrate delivery | Original request and environment constraints | Acceptance criteria, role briefs, delivery summary, and known limitations | Stop when acceptance checks pass or a missing decision blocks safe completion |
| Analyst | The request and environment constraints, read-only | Turn the request into behavior rules and edge cases | Required fields, listing behavior, filtering behavior, and stated constraints | Testable acceptance criteria and edge-case list | Stop when every requested behavior has a measurable check |
| Maker | Approved source area and test area, write access limited to the task | Implement the smallest tool that meets the acceptance criteria and add tests | Acceptance criteria and environment constraints | Working implementation, tests, and concise usage notes | Stop when tests pass, a criterion cannot be met within scope, or wider access would be required |
| Auditor | Original request, implementation, and test results, read-only | Verify behavior and inspect correctness, assumptions, contradictions, risks, and request satisfaction | Acceptance criteria, source, test results, and usage notes | Reproduction record, findings, and pass or revise recommendation | Stop when every acceptance item and listed edge case has a recorded result |

Do not add a Scout when the supplied request already contains the complete feature set and environment constraints. Add one only if evidence discovery becomes a distinct task.
