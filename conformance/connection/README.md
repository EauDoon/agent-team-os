# Connection conformance suite

This directory holds a small, versioned conformance suite for the connection
lifecycle in [`connect.md`](../../connect.md#connection-lifecycle). Where the
[connect suite](../connect/README.md) checks one message and the
[negotiation suite](../negotiation/README.md) checks one decision, this suite
checks a whole exchange: the order of the messages, who sends each one, and
whether the envelopes agree with each other.

## Layout

- `cases.json` - a versioned list of cases. Each case has a unique `name`, a
  `description`, the connect `messages` in delivery order, and an `expect` of
  `valid` or `invalid`. A case may add `advertised`, the capability tokens the
  Orchestrator advertised, which also holds the response to the negotiation
  rules, and `require_closed: true`, which requires the exchange to end in a
  refusal or a result. Invalid cases carry a `violation` that must appear in
  one of the failures the exchange produces.

## Protocol

`scripts/validate.py` runs the suite in CI with the reference connection
inspector in `scripts/workflows.py`. Every case must produce its declared
outcome, and every invalid case must fail for its declared violation. The
validator also requires two paths through the `connect.md` worked examples to
be conforming closed connections: the request, acceptance, handoff, gap status
and result, and the request with its refusal.

An implementer can run any recorded exchange through the same rules:

```sh
python3 scripts/inspect_records.py connection request.json response.json handoff.json status.json result.json --advertise bounded-scope --advertise evidence-trace --require-closed
```

The [rule list](../../docs/record-inspection.md#check-a-whole-connection) names
the source of every rule. The inspector reads files only. It sends nothing,
authenticates no sender and grants no permission.

## Keeping it honest

- Add a case when the lifecycle rules change or a real interop disagreement is
  found. Keep one invalid case per rule.
- Keep `violation` specific: a case that fails for a different rule than it
  names is a defect in the suite, not the contract.
- Keep the fixtures synthetic. Do not put identifying or sensitive data here.
