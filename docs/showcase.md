# Agent Team showcase

Agent Team is a contract layer and tool pack for delegated agent work. It ships
a versioned six-field role brief, an interoperability specification for
exchanging work between agent systems, and standard-library tools that check
those records locally. It does not coordinate work: the host runtime that
consumes the skill decides when to delegate, which roles exist and how results
are assembled.

The skill ships as instruction-only files (`skill/agent-team-os/`) and a small
set of Python standard-library tools under `scripts/`. There are no runtime
dependencies, no package manager, and no remote calls.

## What it brings

- A six-field role brief (Role, Access scope, Task, Evidence, Output contract,
  Stop condition) that a host can check before any handoff.
- A versioned connect envelope for requests, handoffs, status, results and
  structured refusals, with deterministic capability negotiation.
- Records for routing plans, evidence ledgers, audit closure and packets, each
  with a schema and semantic checks.
- Conformance suites that pin message shape and negotiation decisions, so
  another implementation can prove agreement.
- A deterministic package whose checksum reproduces from source on any
  supported Python.

Role names such as Scout, Analyst, Maker and Auditor appear in the examples
only. The schemas accept any non-empty role name; the host defines its own
vocabulary and enforces it.

## Where to start

Read the [connect specification](../connect.md) to exchange work with another
agent system, and the [operator quickstart](operator-quickstart.md) for a
checked routing plan, evidence ledger, handoff acceptance and audit closure.
[Contract checking](contract-checking.md) covers input limits and exit codes.

## Evaluation highlights

`evals/` ships a bounded, versioned calibration suite. The published
`results.v0.1.json` is intentionally empty with `calibration_fixture` status;
the suite is a protocol fixture, not evidence that one arm outperforms another.

The suite covers six synthetic task shapes:

| Task | Shape |
| --- | --- |
| brief-001 | evidence-extraction |
| brief-002 | comparative-analysis |
| brief-003 | bounded-construction |
| brief-004 | independent-audit |
| brief-005 | scope-boundary |
| brief-006 | uncertainty |

Each task lists named acceptance checks. A paired run records a strong solo
baseline and the current Agent Team instructions on the same task order,
scoring only the acceptance checks. `scripts/evaluate.py` summarizes per-arm
counts, usage, and the difference in passed checks; it never treats unverified
checks as passes. The summary is descriptive for the supplied run only; no
statistical significance, causal attribution, or general superiority claim is
made.

## Operator tools

| Tool | Local outcome |
| --- | --- |
| `scripts/validate.py` | Contract, conformance, manifest and link checks for the public package. |
| `scripts/check.py brief`, `connect`, `plan`, `evidence`, `audit` | Validate authored JSON and routing plans before handoff. |
| `scripts/author.py` | Compose complete briefs, explicit handoffs, and actionable refusals. |
| `scripts/inspect_records.py` | Inspect readiness, plan changes, evidence impact, and audit remediation. |
| `scripts/inspect_records.py negotiate` | Compute the exact accept or refuse payload for a connect request. |
| `scripts/evaluate.py` | Summarize paired runs and export Markdown reports. |
| `scripts/packet.py` | Check related records and create or verify exact-byte receipts. |
| `scripts/package.py` | Build a deterministic ZIP plus SHA-256 checksum. |
| `scripts/verify_package.py` | Compare a built ZIP against reviewed source bytes before extraction. |

Every tool accepts `--version` and prints `agent-team X.Y.Z`. All checks and
inspections are read-only. Authoring, report exports, and packet receipts write
only explicitly requested new files. They do not send messages, execute role
instructions, authenticate agents, or enforce permissions.

## Provenance and limits

- Released under the MIT License.
- Public package uses fully synthetic scenarios; see `PROVENANCE.md` for the
  creation record.
- The skill is an instruction layer, not an execution engine, storage system,
  authorization mechanism, or isolation boundary.
- A passing check establishes shape and bookkeeping, not truthful evidence,
  real permission enforcement or an independent review.
- Human judgment remains necessary before consequential use.
