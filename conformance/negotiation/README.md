# Negotiation conformance suite

This directory holds a small, versioned conformance suite for the capability
negotiation rules in [`connect.md`](../../connect.md#capability-negotiation).
Where the [connect suite](../connect/README.md) checks message shape, this suite
checks the decision: given a request and the capabilities an Orchestrator
advertises, which response payload the rules require.

## Layout

- `cases.json` - a versioned list of cases. Each case has a unique `name`, a
  `description`, a full connect `request`, the `advertised` capability tokens,
  and the exact `expect`ed response payload.

## Protocol

`scripts/validate.py` runs the suite in CI. For every case it computes the
response payload with the reference negotiator in `scripts/workflows.py` and
asserts exact equality with `expect`, including the sorted order of
`negotiated_capabilities` and the refusal text. It also checks that the
`connect.md` capability vocabulary matches the reference baseline and that the
specification's acceptance and refusal examples are what the rules produce for
its request example.

An implementer can run any request through the same rules:

```sh
python3 scripts/inspect_records.py negotiate request.json --advertise evidence-trace --advertise bounded-scope
```

The command computes the decision only. It sends nothing and grants no
permission.

## Keeping it honest

- Add a case when the rules change or a real interop disagreement is found.
- Keep `expect` exact: the rules are byte-reproducible, so a reordered list or a
  reworded refusal is a different answer.
- Keep the fixtures synthetic. Do not put identifying or sensitive data here.
