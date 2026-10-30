# Author records without replacing existing work

Provide all six role-brief fields explicitly:

```sh
python3 scripts/author.py brief --role Maker --scope "Supplied files only." --task "Build the fictional tool." --evidence "Supplied requirements." --deliver "Tool and acceptance checks." --stop "Acceptance or scope gap." --output brief.json
python3 scripts/check.py brief brief.json --json
```

The composer checks the complete brief before writing. It rejects blank fields,
requires a new output filename and never invents scope or authorization.
Repeat `--prohibit TEXT` to write `prohibited_actions` in the order given; blank
values are refused, and without the flag the key is omitted, so existing
invocations write the same bytes as before. Review
the written fields before using the brief. Existing files and symlinks are not
replaced. Parent directories must already exist.

The writer stages complete UTF-8 content, then publishes it with an exclusive
same-directory hard link. If the filesystem cannot support that operation, it
fails without silently falling back to overwrite behavior. Records are limited
to 1 MiB. Success returns JSON with `ok: true`; invalid input or an unavailable
output returns generic JSON with `ok: false` and exit status 1. When a documented
authoring rule failed, the output adds `reason`, such as `each brief field needs
meaningful text`, and a non-conforming record adds masked schema `failures`, as
described in [failure reasons](record-inspection.md#read-a-failure-reason). An
existing output file or another I/O failure keeps the generic error alone. No
role is started and no message is sent. Module invocation via
`python3 -m scripts.author` is also supported.

## Compose connect messages

When a checked routing plan already contains the brief, avoid manual retyping:

```sh
python3 scripts/author.py plan-brief templates/routing-plan.json --assignment build --output brief.json
```

The entire plan must conform before extraction. The assignment ID must match
exactly, and all brief fields including optional prohibitions are copied without
alteration. Existing output files remain protected. Extraction does not establish
dependency acceptance or permission to start the assignment.

Every message command composes only `agent-team-connect/v0.2`, after both
participants agree to it, and requires `--version agent-team-connect/v0.2`, the
wire version, not the package version. Each one checks the complete message
against the v0.2 schema before the exclusive write, so a refused message writes
no file. Repeated flags keep their order. Files are draft messages only:
producing one neither negotiates a connection nor sends it.

### `request`

```sh
python3 scripts/author.py request --version agent-team-connect/v0.2 --from initiator --to orchestrator --message-id m1 --correlation-id task1 --objective "Compare the supplied briefs." --completion-test "Every conclusion cites a brief." --require bounded-scope --offer evidence-trace --output request.json
```

`--require` fills `payload.required_capabilities` and `--offer` fills the
envelope `capabilities`. Capability tokens must be lowercase,
hyphen-separated and unique per flag. Repeat `--constraint TEXT` for hard
limits. Blank text is refused.

### `response`

```sh
python3 scripts/author.py response --version agent-team-connect/v0.2 --request request.json --advertise bounded-scope --advertise evidence-trace --message-id m2 --output response.json
```

The request must be a conforming v0.2 request; a v0.1 request or another
message type is refused. The payload is exactly what the
[negotiation rules](../connect.md#capability-negotiation) owe that request for
the advertised set: an acceptance with the sorted negotiated set, or the
refusal naming the missing capabilities. Sender and recipient are reversed from
the request and the correlation ID is copied.

### `handoff` and `refusal`

```sh
python3 scripts/author.py handoff --version agent-team-connect/v0.2 --from owner --to maker --message-id m1 --correlation-id task1 --brief brief.json --evidence brief-a.txt --output handoff.json
python3 scripts/author.py refusal --version agent-team-connect/v0.2 --from owner --to initiator --message-id m2 --correlation-id task1 --reason "Requested action is outside scope." --next-step "Request a bounded scope decision." --output refusal.json
```

The composer copies the brief without widening access or rewriting its fields.
A missing or malformed brief produces no output file. Repeat `--evidence ID` to
write `payload.evidence`, the inputs the role may inspect; values must be
nonblank and unique, and without the flag the key is omitted. Use `refusal` for
a refusal that is not about capabilities, such as a scope conflict or an
authorization gap; `response` writes capability refusals.

### `status`

```sh
python3 scripts/author.py status --version agent-team-connect/v0.2 --from maker --to owner --message-id m3 --correlation-id task1 --state gap --gap "Brief C is missing." --decision-needed "Proceed without brief C, or supply it." --output status.json
```

`--state` is one of `working`, `gap`, `blocked` or `done`. A `gap` status needs
a nonblank `--decision-needed`, as [connect.md](../connect.md#rejections-and-errors-consumer-ux)
requires. Repeat `--evidence-inspected ID` and `--gap TEXT` as needed.

### `result`

```sh
python3 scripts/author.py result --version agent-team-connect/v0.2 --from orchestrator --to initiator --message-id m5 --correlation-id task1 --summary "The comparison is complete." --satisfied yes --response response.json --output result.json
```

A result must record the negotiated capability set in its envelope
`capabilities`, so it takes exactly one source. `--response FILE` names the
accepted v0.2 response of the same connection: its correlation ID must match,
and its sender and recipient must equal the result's `--from` and `--to`. Its
`negotiated_capabilities` are copied, or `[]` when the set is empty. Without a
response file, repeat `--capability CAP` instead; the tokens are written sorted.
Repeat `--evidence-basis ID`, `--assumption TEXT` and `--risk TEXT` as needed.

### An authored exchange

These commands write a complete connection that the
[connection inspector](record-inspection.md#check-a-whole-connection) accepts:

```sh
python3 scripts/author.py request --version agent-team-connect/v0.2 --from initiator --to orchestrator --message-id m1 --correlation-id c1 --objective "Compare the supplied briefs." --completion-test "Every conclusion cites a brief." --require bounded-scope --offer evidence-trace --output request.json
python3 scripts/author.py response --version agent-team-connect/v0.2 --request request.json --advertise bounded-scope --advertise evidence-trace --message-id m2 --output response.json
python3 scripts/author.py plan-brief templates/routing-plan.json --assignment requirements --output brief.json
python3 scripts/author.py handoff --version agent-team-connect/v0.2 --from orchestrator --to analyst-1 --message-id m3 --correlation-id c1 --brief brief.json --evidence brief-a.txt --output handoff.json
python3 scripts/author.py status --version agent-team-connect/v0.2 --from analyst-1 --to orchestrator --message-id m4 --correlation-id c1 --state done --evidence-inspected brief-a.txt --output status.json
python3 scripts/author.py result --version agent-team-connect/v0.2 --from orchestrator --to initiator --message-id m5 --correlation-id c1 --summary "Acceptance checks are ready." --satisfied yes --response response.json --output result.json
python3 scripts/inspect_records.py connection request.json response.json handoff.json status.json result.json --advertise bounded-scope --advertise evidence-trace --require-closed
```

The existing v0.1 validation contract remains unchanged.
