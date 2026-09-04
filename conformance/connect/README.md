# Connect conformance suite

This directory holds a small, versioned conformance suite for the connect message
contract in [`schemas/connect.schema.json`](../../schemas/connect.schema.json).
It is a set of fixtures with expected outcomes, in the spirit of
[`evals/`](../../evals/README.md).

## Layout

- `cases.json` - a versioned list of cases. Each case has a unique `name`, a full
  `message`, and an `expect` of `valid` or `invalid`. Invalid cases also carry a
  `violation` describing the constraint that is expected to fail.

## Protocol

`scripts/validate.py` runs the suite in CI. For every case it checks the message
against the contract (required envelope, `connect_version` const, the `type` enum,
each type's required payload keys, and the handoff role brief fields) and asserts
that the result matches the case's `expect`. A valid case must conform; an invalid
case must not. If a case's outcome stops matching its expectation, CI fails.

## Keeping it honest

- Add a case when the contract changes or a real interop failure is found.
- Keep `expect` accurate: a case that no longer fails for the stated reason is a
  defect in the suite, not the contract.
- Keep the fixtures synthetic. Do not put identifying or sensitive data here.
