# Agent Team showcase

Agent Team is an installable skill that turns a broad request into bounded role assignments, evidence-backed handoffs, and, for important work, an independently audited result. The skill applies a delegation gate: every role must own a distinct output or reduce a named risk. Straightforward work stays with one agent.

The skill ships as instruction-only files (`skill/agent-team-os/`) and a small set of Python standard-library tools under `scripts/`. There are no runtime dependencies, no package manager, and no remote calls.

## What it brings

- One owner for each decision and artifact.
- Bounded access with explicit read, write, tool, and action scope per role.
- Traceable reasoning: claims, assumptions, gaps, and evidence travel with each handoff.
- Deliberate sequencing for dependent work, with safe parallel runs for independent work.
- Independent review by an Auditor before important results ship.
- One coherent result assembled by the Orchestrator.

The task-scoped roles are Orchestrator, Scout, Analyst, Maker, and Auditor. Each role receives a six-field brief (Role, Access scope, Task, Evidence, Output contract, Stop condition) before work starts.

## Workflow

```
Request -> frame -> route -> execute -> integrate -> audit -> deliver
```

The full operating model and repository map are in `README.md`. Operator entry points live in `docs/operator-quickstart.md`, `docs/contract-checking.md`, and `docs/handoffs.md`.

## Evaluation highlights

`evals/` ships a bounded, versioned calibration suite. The published `results.v0.1.json` is intentionally empty with `calibration_fixture` status; the README explicitly states the suite is a protocol fixture, not evidence that one arm outperforms another.

The suite covers six synthetic task shapes:

| Task | Shape |
| --- | --- |
| brief-001 | evidence-extraction |
| brief-002 | comparative-analysis |
| brief-003 | bounded-construction |
| brief-004 | independent-audit |
| brief-005 | scope-boundary |
| brief-006 | uncertainty |

Each task lists named acceptance checks. A paired run records a strong solo baseline and the current Agent Team instructions on the same task order, scoring only the acceptance checks. `scripts/evaluate.py` summarizes per-arm counts, usage, and the difference in passed checks; it never treats unverified checks as passes. Successful summaries also include a task-level breakdown so per-criterion differences reconcile to the overall difference. The summary is descriptive for the supplied run only; no statistical significance, causal attribution, or general superiority claim is made.

Result and run shapes are versioned through `evals/result.schema.json` and `evals/run.schema.json`. Reports can be exported as Markdown with escaped table cells and SHA-256 digests of the exact input and suite bytes.

## Operator tools

| Tool | Local outcome |
| --- | --- |
| `scripts/validate.py` | Dependency-light contract and link checker for the public package. |
| `scripts/check.py brief`, `connect`, `plan`, `evidence`, `audit` | Validate authored JSON and routing plans before handoff. |
| `scripts/author.py` | Compose complete briefs, explicit handoffs, and actionable refusals. |
| `scripts/inspect_records.py` | Inspect readiness, plan changes, evidence impact, and audit remediation. |
| `scripts/evaluate.py` | Summarize paired runs and export Markdown reports. |
| `scripts/packet.py` | Check related records and create or verify exact-byte receipts. |
| `scripts/package.py` | Build a deterministic ZIP plus SHA-256 checksum. |
| `scripts/verify_package.py` | Compare a built ZIP against reviewed source bytes before extraction. |

All checks and inspections are read-only. Authoring, report exports, and packet receipts write only explicitly requested new files. They do not send messages, execute role instructions, authenticate agents, or enforce permissions.

## Provenance and limits

- Released under the MIT License.
- Public package uses fully synthetic scenarios; see `PROVENANCE.md` for the creation record.
- The skill is an instruction layer, not an execution engine, storage system, authorization mechanism, or isolation boundary.
- An Auditor is an independent check, not a guarantee.
- Delegation adds overhead when roles overlap or the task is too small.
- Human judgment remains necessary before consequential use.