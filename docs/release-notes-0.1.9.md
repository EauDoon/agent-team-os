# Release notes for 0.1.9

Patch release that makes the `connect.md` worked examples machine-verified. No
change to the coordination instructions, the role brief contract, or the connect
protocol.

## Changes

- Added `check_connect_examples` to `scripts/validate.py`. The worked examples in
  `connect.md` are now extracted from their fenced `json` blocks and verified as
  valid, conforming connect messages:
  - the message envelope is present;
  - `connect_version` matches the schema const;
  - `type` is a known message type;
  - each payload has its schema-required keys; and
  - a `handoff` payload's `role_brief` has all six role brief fields.
- The constraints are read from `schemas/connect.schema.json`, so the check stays
  in sync with the contract automatically. This turns the spec's examples from
  illustrative into machine-verified: if an example drifts out of conformance, CI
  fails.
- Added a unit test covering a conforming example and one with a missing payload
  field.

## Verification

- `python3 scripts/validate.py` passes all checks, including the new per-example
  conformance checks against every example in `connect.md`.
- `python3 -m unittest discover -s tests` passes; the symlink-only test is
  skipped on platforms without symlink permission.
- `python3 scripts/package.py --output dist` produces
  `agent-team-0.1.9.zip` and `agent-team-0.1.9.zip.sha256`.
- `sha256sum -c` confirms the archive against the checksum.

Recheck the package checksum after any later byte or metadata change.
