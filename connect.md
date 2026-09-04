# Agent Team Connect

A versioned interoperability specification for how an external agent or system
**connects to** an `agent-team-os` Orchestrator and exchanges work with it.

This is a **contract and protocol**, not a runtime. Agent Team is instruction-only
and has no server, endpoint, or persistent identity. `connect.md` defines the
message shape, the capability handshake, the handoff and status lifecycle, and the
security boundaries that any two conforming agents must follow to interoperate.
If you build a transport (queue, RPC, files, a channel), the transport is not
part of this contract; only the message content and its rules are.

The machine-readable message shape is [`schemas/connect.schema.json`](schemas/connect.schema.json).
A conforming message must validate against it. The delegation inside a handoff
reuses the six-field role brief in [`schemas/role-brief.schema.json`](schemas/role-brief.schema.json).

## Why a connect contract

Agent Team coordinates work by giving each role a bounded brief and evidence-backed
handoffs. An external agent that wants to join that coordination must agree to the
same discipline, or it will reintroduce the failure modes the skill exists to
prevent: unbounded access, untraceable claims, and conflicting ownership. This
spec makes that agreement explicit and machine-checkable, so a third party can
plug in without being trusted blindly.

## Design principles

- **Bounded, not trusted.** A connection grants no access by itself. Every scope is
  stated in the message and must be enforced by the execution environment.
- **Evidence travels with the message.** Claims, assumptions, gaps, and the
  evidence behind them are part of the payload, not left implicit.
- **One owner per artifact.** Every handoff names the owning role; the Orchestrator
  owns request satisfaction.
- **Uncertainty is preserved.** A gap, contradiction, or missing capability is
  reported as such, never silently converted into a conclusion or a refusal reason.
- **Least privilege, no self-escalation.** A participant cannot widen its own
  scope, redefine the objective, or invent authorization.
- **Graceful degradation.** A missing capability or authorization produces a
  structured refusal or a gap, not a silent failure.

## Participants

| Participant | Responsibility |
| --- | --- |
| **Initiator** | The external agent or system that opens a connection and states an objective. |
| **Orchestrator** | The `agent-team-os` coordinator that frames the request, routes work, integrates outputs, and owns request satisfaction. |
| **Role** | A temporary specialist (Scout, Analyst, Maker, Auditor) that receives a handoff and returns evidence-backed output. |

Participants are temporary, task-scoped identifiers. A `from` or `to` value is not
a durable identity, memory, or trust grant across connections.

## Connection lifecycle

```text
discover -> negotiate -> accept|refuse
                        |-> brief (handoff) -> work -> status... -> result -> closed
```

1. **Discover.** Each side advertises its `capabilities`.
2. **Negotiate.** The Orchestrator checks the initiator's `required_capabilities`
   against what it can provide and replies with a `response` that either accepts
   (with the negotiated capability set) or refuses with a reason.
3. **Handoff.** For each delegated unit of work the Orchestrator sends a `handoff`
   carrying a complete six-field role brief plus the evidence to inspect.
4. **Work / status.** A role reports `status` as it works, surfacing gaps and
   blocking conditions as they arise.
5. **Result.** When work completes, a `result` reports the outcome, its evidence
   basis, assumptions, and unresolved risks.

Messages are correlated by `correlation_id` so a whole exchange is traceable as one
connection.

## Message envelope

Every message is a single JSON object conforming to
[`schemas/connect.schema.json`](schemas/connect.schema.json).

| Field | Required | Meaning |
| --- | --- | --- |
| `connect_version` | yes | Must be `agent-team-connect/v0.1`. |
| `type` | yes | One of `request`, `response`, `handoff`, `status`, `result`. |
| `message_id` | yes | Unique id for this message; delivery should be idempotent on it. |
| `correlation_id` | yes | The connection or request this message belongs to. |
| `from` | yes | Sender identifier. |
| `to` | yes | Recipient identifier. |
| `sent_at` | no | ISO-8601 timestamp of the message. |
| `capabilities` | no | Capabilities the sender advertises or the connection supports. |
| `payload` | yes | Type-specific body, typed by `type`. |

The payload is typed per message type (see below). Keep payloads minimal: include
only the fields your message needs. Extra top-level fields are rejected by the
schema, so a sender cannot smuggle undeclared data across the boundary.

### Capability vocabulary

Capabilities are lowercase, hyphen-separated tokens. The baseline set a conforming
Orchestrator should advertise:

- `route` - selects and sequences task-scoped roles.
- `audit` - runs an independent Auditor on important results.
- `evidence-trace` - requires claims to carry a source or an uncertainty label.
- `bounded-scope` - enforces per-role read/write/action scope.
- `structured-gaps` - reports gaps and contradictions explicitly instead of
  filling them.

An initiator may require any subset via `required_capabilities`. Unknown or
missing capabilities are the reason for a refusal, not a reason to guess.

## Capability negotiation

Negotiation is deterministic so two conforming participants always reach the same
decision for the same inputs. A conforming Orchestrator applies these rules when
it receives a `request`:

- `R` = `request.payload.required_capabilities` (the capabilities the connection
  must support), or the empty list.
- `Ci` = `request.capabilities` (what the initiator offers), or the empty list.
- `Co` = the capabilities the Orchestrator advertises.

```text
missing    = sorted(R - Co)          # required capabilities we cannot provide
negotiated = sorted((Ci ∪ R) ∩ Co)   # capabilities both sides will actually use

if missing is not empty:
    reply response(accepted = false,
                   refusal_reason = "missing required capabilities: " + join(missing),
                   next_step      = "authorize or remove: " + join(missing))
else:
    reply response(accepted = true, negotiated_capabilities = negotiated)
```

Rules and edge cases:

- A connection is accepted if and only if every required capability is supported
  (`missing` is empty). A capability the initiator *offers* (`Ci`) but does not
  require never causes a refusal.
- An offered capability the Orchestrator does not support is simply not negotiated;
  it is dropped from `negotiated` rather than treated as an error.
- All sets are sorted lexicographically so `negotiated_capabilities` and the
  refusal reason are reproducible byte-for-byte.
- On refusal, `refusal_reason` names exactly the missing capabilities and
  `next_step` states the bounded action (authorize them or remove them from
  `required_capabilities`). Never refuse without a reason.
- Record `negotiated_capabilities` in the final `result` context so a connection
  is reproducible.

## Message types and payloads

### `request`
The initiator's objective and completion bar.

| Key | Required | Meaning |
| --- | --- | --- |
| `objective` | yes | What the initiator wants, as an outcome. |
| `completion_test` | yes | The check that shows the objective is met. |
| `constraints` | no | Hard limits the work must respect. |
| `required_capabilities` | no | Capabilities the connection must support. |
| `context` | no | Key/value context, for example supplied evidence references. |

### `response`
The Orchestrator's accept or refuse.

| Key | Required | Meaning |
| --- | --- | --- |
| `accepted` | yes | Whether the connection is accepted. |
| `negotiated_capabilities` | no | The capability set both sides will honor. |
| `refusal_reason` | no | Present when not accepted: the missing capability, scope conflict, or authorization gap. |
| `next_step` | no | The bounded action that would unblock the connection. |

### `handoff`
A delegation of one unit of work to a role.

| Key | Required | Meaning |
| --- | --- | --- |
| `role_brief` | yes | The complete six-field role brief (see the role brief schema). |
| `evidence` | no | Identifiers of the inputs the role may inspect. |

A handoff with a missing role brief field is invalid and must be rejected, not
completed with guesses.

### `status`
Progress and problems during work.

| Key | Required | Meaning |
| --- | --- | --- |
| `state` | yes | One of `working`, `gap`, `blocked`, `done`. |
| `evidence_inspected` | no | Inputs inspected so far. |
| `gaps` | no | Missing or weak evidence, stated as gaps. |
| `decision_needed` | no | The specific decision required to continue. |

### `result`
The final, integrated delivery for the connection.

| Key | Required | Meaning |
| --- | --- | --- |
| `summary` | yes | The outcome in one place. |
| `request_satisfied` | yes | Whether the original objective and completion test are met. |
| `evidence_basis` | no | The evidence the result rests on. |
| `assumptions` | no | Assumptions made, stated explicitly. |
| `unresolved_risks` | no | Risks or gaps that remain open. |

## Handoff and the role brief contract

The `handoff.payload.role_brief` is the same six-field contract used inside Agent
Team: `role`, `access_scope`, `task`, `evidence`, `output_contract`,
`stop_condition`. This keeps external delegation subject to the same discipline as
internal delegation. A conforming Orchestrator must not accept a handoff whose role
brief omits a field, duplicates another role, or grants broader access than the task
requires.

## Authorization and security boundaries

A connection is a coordination protocol, **not** an access-control mechanism.

- Capability advertisement is a negotiation aid, not a permission.
- Enforce real permissions in the execution environment; the message only declares
  the intended scope.
- Grant each role the least access its task requires.
- A participant may not widen its own scope, redefine the objective, or invent
  authorization.
- Require explicit authorization before any consequential external action that was
  not already approved.
- An Auditor is an independent check, not a guarantee; confidence and silence are
  not evidence.

See [`SECURITY.md`](SECURITY.md) for safe-use and reporting guidance.

## Versioning and compatibility

- The contract is versioned by `connect_version`, currently `agent-team-connect/v0.1`.
- A receiver should ignore unknown **payload** keys it does not understand where the
  schema allows it, and reject a message whose `connect_version` it does not
  support rather than guess at meaning.
- Additive changes (new optional fields, new capability tokens) should not bump the
  minor-incompatible surface; changes that alter the meaning of an existing field
  must bump the version.
- Record the `connect_version` and the negotiated capability set in the result so a
  connection is reproducible.

## Rejections and errors (consumer UX)

Every "no" must be structured and actionable. A conforming participant does not
drop a message silently. Use:

- **Refused connection** - a `response` with `accepted: false` and a
  `refusal_reason` naming the missing capability, scope conflict, or authorization
  gap, plus a `next_step`.
- **Invalid handoff** - reject a handoff with an incomplete role brief; state the
  missing field.
- **Gap** - a `status` with `state: gap` and the `decision_needed` to resolve it.
- **Blocked** - a `status` with `state: blocked` when the assigned stop condition
  is hit (completion, exhausted evidence, conflicting instructions, or need for
  wider scope).

Do not let a participant stop because it is bored or has hit diminishing returns
without reporting a `status` first.

## Worked examples

The examples below are synthetic. Each is a full envelope conforming to the schema.

### 1. Connection request

```json
{
  "connect_version": "agent-team-connect/v0.1",
  "type": "request",
  "message_id": "msg-0001",
  "correlation_id": "conn-42",
  "from": "vendor-intake-agent",
  "to": "orchestrator",
  "capabilities": ["evidence-trace"],
  "payload": {
    "objective": "Compare three supplied vendor briefs against fixed criteria.",
    "completion_test": "Every conclusion traces to a supplied statement or is labeled unsupported.",
    "constraints": ["Use only the supplied briefs", "No external sources"],
    "required_capabilities": ["evidence-trace", "bounded-scope"]
  }
}
```

### 2. Acceptance with negotiated capabilities

```json
{
  "connect_version": "agent-team-connect/v0.1",
  "type": "response",
  "message_id": "msg-0002",
  "correlation_id": "conn-42",
  "from": "orchestrator",
  "to": "vendor-intake-agent",
  "payload": {
    "accepted": true,
    "negotiated_capabilities": ["evidence-trace", "bounded-scope", "route", "audit"]
  }
}
```

### 3. Refusal with a reason

```json
{
  "connect_version": "agent-team-connect/v0.1",
  "type": "response",
  "message_id": "msg-0002",
  "correlation_id": "conn-42",
  "from": "orchestrator",
  "to": "vendor-intake-agent",
  "payload": {
    "accepted": false,
    "refusal_reason": "required capability 'external-write' is not supported",
    "next_step": "Remove the external-write requirement or supply an authorized writer."
  }
}
```

### 4. Handoff of a bounded role

```json
{
  "connect_version": "agent-team-connect/v0.1",
  "type": "handoff",
  "message_id": "msg-0003",
  "correlation_id": "conn-42",
  "from": "orchestrator",
  "to": "scout-1",
  "payload": {
    "role_brief": {
      "role": "Scout",
      "access_scope": "Supplied briefs only, read-only.",
      "task": "Extract claims and mark missing information without ranking vendors.",
      "evidence": "Exact statements from the supplied briefs.",
      "output_contract": "Source table with claim, source location, and uncertainty.",
      "stop_condition": "Stop after every criterion is covered or explicitly marked missing."
    },
    "evidence": ["brief-a.txt", "brief-b.txt", "brief-c.txt"]
  }
}
```

### 5. Status with a gap

```json
{
  "connect_version": "agent-team-connect/v0.1",
  "type": "status",
  "message_id": "msg-0004",
  "correlation_id": "conn-42",
  "from": "scout-1",
  "to": "orchestrator",
  "payload": {
    "state": "gap",
    "evidence_inspected": ["brief-a.txt", "brief-b.txt"],
    "gaps": ["brief-c.txt has no statement about exit effort"],
    "decision_needed": "Proceed with exit effort marked missing for vendor C, or supply the missing brief."
  }
}
```

### 6. Final result

```json
{
  "connect_version": "agent-team-connect/v0.1",
  "type": "result",
  "message_id": "msg-0005",
  "correlation_id": "conn-42",
  "from": "orchestrator",
  "to": "vendor-intake-agent",
  "payload": {
    "summary": "Vendor A best fits the criteria; vendor C is missing exit-effort evidence.",
    "request_satisfied": true,
    "evidence_basis": ["scout-source-table", "analyst-comparison", "auditor-pass"],
    "assumptions": ["Criteria weights are equal unless stated otherwise."],
    "unresolved_risks": ["Vendor C exit effort is unverified."]
  }
}
```

## Relationship to the existing contracts

- The `handoff` payload reuses the six-field role brief, so internal and external
  delegation share one contract.
- A `result` payload mirrors the delivery summary in `SKILL.md` and the shape of
  the bounded evaluation result in [`evals/result.schema.json`](evals/result.schema.json).
- The security boundaries here restate, not replace, [`SECURITY.md`](SECURITY.md).

## Limitations

- This is a specification. It does not provide transport, authentication, storage,
  or enforcement; a conforming deployment must supply those.
- A capability list and a well-formed message are not proof of capability or
  correctness.
- Versioning is a policy in this document, not enforced by a registry.
- Consequential actions still require explicit authorization outside this contract.
