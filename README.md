# Agent Team OS

Agent Team OS is an installable Codex skill for coordinating complex work across task-scoped specialist AI agents. It turns a broad request into bounded role briefs, delegates only when specialization has clear value, integrates the results, and requires an explicit audit for important outputs.

## Purpose

Use Agent Team OS when a request needs distinct evidence gathering, analysis, construction, or verification. Keep simple work with one agent. Add a role only when it improves a separate output or reduces a named risk.

The generic roles are:

- Orchestrator: frame the request, choose roles, sequence work, integrate results, and own delivery.
- Scout: gather and organize permitted evidence without deciding the answer.
- Analyst: interpret evidence, compare options, expose assumptions, and reason about tradeoffs.
- Maker: create the requested artifact and revise it against findings.
- Auditor: independently check correctness, assumptions, contradictions, risks, and satisfaction of the request.

Every delegated role receives an access scope, task, evidence requirement, output contract, and stop condition.

## Safety boundaries

- Treat every agent as a task-scoped worker, not a persistent identity.
- Treat role separation as a coordination technique, not a security boundary.
- Enforce access through the execution environment and explicit permissions.
- Grant only the access needed for the assigned task.
- Require evidence for material claims and preserve uncertainty when evidence is incomplete.
- Stop work when a role reaches its contract, lacks permitted evidence, encounters conflicting instructions, or needs wider scope.
- Require explicit authorization before any consequential external action.
- Keep the Orchestrator responsible for resolving contradictions and satisfying the original request.

## Repository layout

```text
agent-team-os/
|-- README.md
|-- LICENSE
|-- SECURITY.md
|-- CONTRIBUTING.md
|-- PROVENANCE.md
|-- examples/
|   `-- routing-scenarios.md
`-- skill/
    `-- agent-team-os/
        |-- SKILL.md
        `-- agents/
            `-- openai.yaml
```

## Installation

Place the included `skill/agent-team-os` directory under `.agents/skills/` in the target workspace. The installed directory should be `.agents/skills/agent-team-os/`.

Invoke the skill explicitly with `$agent-team-os`. Its metadata also permits implicit invocation when a complex request clearly benefits from specialist routing.

The skill is instruction-only and has no runtime dependencies or external assets.

## Synthetic examples

1. Vendor comparison: route supplied fictional capability briefs to a Scout for extraction, an Analyst for comparison, and an Auditor for evidence and consistency checks.
2. Customer-support workflow design: map fictional request categories, analyze failure points, draft a bounded workflow, and audit the result against the stated service goals.
3. Small internal tool: define acceptance criteria, build a minimal work-item tracker, test its behavior, and audit the result against the original request.

Detailed role briefs for these fictional scenarios are in `examples/routing-scenarios.md`.

## Limitations

- Coordination adds overhead and can reduce quality when roles duplicate work.
- An Auditor is fallible and does not make unsupported claims reliable.
- Missing or weak evidence limits every downstream result.
- Task-scoped roles do not create durable identity, memory, access control, or isolation.
- The skill does not provide an execution engine, storage layer, or authorization mechanism.
- Human review remains necessary before consequential use.

## Authorship

Project direction and requirements are by Oonyl. This public package was drafted and tested with OpenAI Codex. Final evaluation, review, and acceptance remain with Oonyl. See `PROVENANCE.md` for the creation record.

This is an independent community project. It is not an OpenAI product, and OpenAI does not endorse it.

## License

Released under the MIT License. See `LICENSE`.
