---
name: agent-team-os
description: Installable skill that ships the six-field role-brief contract, the Agent Team connect specification, and dependency-light validators for both. The coordination protocol lives in the host runtime; this skill ships the wire format and the tooling.
---

# Agent Team

A wire-format and tool pack for bounded, evidence-backed multi-role work.

This skill does not coordinate work by itself. It is an instruction layer that
ships:

- The six-field role-brief contract (`schemas/role-brief.schema.json`).
- The Agent Team connect specification (`connect.md`, `schemas/connect.schema.json`).
- Dependency-light Python validators, a deterministic package builder, and a
  SHA-256 verification step (`scripts/`).
- Calibrated synthetic evaluation fixtures and a connect conformance suite
  (`evals/`, `conformance/`).
- Worked role briefs and three synthetic routing scenarios (`templates/`,
  `examples/`).

The referenced paths live in the Agent Team source package: the
`agent-team-<version>/` folder inside the release ZIP, or a source checkout.
An installed skill folder holds only `SKILL.md` and `agents/openai.yaml`, so
run the tools from the source package, not from the installed skill.

The coordination protocol itself (delegation gates, stop conditions, audit
taxonomy, result delivery) is part of the host runtime that consumes this
skill, not part of the skill. The skill is intentionally thin: it standardizes
how a host expresses a delegated task and how an external agent connects to
the host's coordinator, without prescribing the host's orchestration rules.

## When to install

Install when the host needs to delegate to multiple specialist agents, exchange
work with another agent system, or both. The shipped schemas give the host a
versioned, machine-checkable contract for both directions.

## Use the six-field role brief

Every delegated role receives a brief with six required fields:

```text
Role:           The task-scoped assignment.
Access scope:   The exact sources, tools, actions, and read or write limits allowed.
Task:           The distinct question, artifact, or risk the role owns.
Evidence:       The inputs to inspect and the traceability required for claims.
Output contract: The format, contents, quality bar, and recipient of the result.
Stop condition: The event that ends work, including completion, a blocking gap, or a scope conflict.
```

The `role` field accepts any non-empty string. The host runtime decides which role
names are valid for a given task. Reject a brief that omits a field, duplicates
another role, or grants broader access than its task needs.

The machine-readable contract is `schemas/role-brief.schema.json`. The
dependency-light checker is `scripts/check.py brief`. See `templates/role-brief.md`
for a filled example.

## Use the connect spec to interoperate

If an external agent or system needs to exchange work with a host coordinator,
use the versioned connect specification at `connect.md` (envelope in
`schemas/connect.schema.json`, optional v0.2 authoring contract in
`docs/connect-v0.2.md`). The spec covers capability discovery, message types,
handoffs that reuse the six-field role brief, status and gap semantics, and
the security boundaries that keep a connection bounded.

The connect spec is a contract, not a runtime. The transport (queue, RPC,
files, channel) and the real permission enforcement remain the deployment's
job. The conformance suites at `conformance/connect/`,
`conformance/connect-v0.2/` and `conformance/negotiation/` exercise the spec
against named expected outcomes, and `scripts/validate.py` runs all three in
CI. `scripts/check.py connect` checks one authored message.

## Verify before installing

The shipped package is deterministic. From a reviewed source checkout:

```text
python3 scripts/validate.py
python3 scripts/package.py --output dist
python3 scripts/verify_package.py dist/agent-team-0.5.0.zip
```

The builder emits `<archive>.zip.sha256`. `verify_package.py` compares archive
members against the reviewed source bytes, not only against the checksum
written by the same build. Verify the SHA-256 before copying the skill into a
target project.

## Safety boundaries

These apply regardless of which host runtime consumes this skill.

- Treat role separation as an operating pattern, not a security boundary.
- Enforce real permissions through the execution environment.
- Grant only the access required for the assigned task.
- Do not allow a role to widen its scope, redefine the request, or invent
  authorization.
- Preserve uncertainty when evidence is missing, weak, or contradictory.
- Require explicit authorization before any consequential external action that
  was not already approved.
- Keep human review in the loop for consequential decisions and actions.

## Canonical coordination protocol

The coordination protocol itself is part of the host runtime that consumes
this skill, not part of the skill. This package does not endorse a specific
protocol. Hosts that want a public reference for one possible protocol can
document their choice elsewhere and keep this skill as the contract layer.

## What this skill does not do

- It does not dispatch work, authenticate agents, or enforce access scopes.
- It does not store handoffs, evidence, or audit results.
- It does not produce a coordination result on its own; the host does.
- It does not publish or modify remote metadata; the package builder writes
  only the local archive and its checksum.