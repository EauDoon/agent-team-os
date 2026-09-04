# Release notes for 0.1.10

This release deepens the `connect.md` interoperability layer with a deterministic
negotiation algorithm and a machine-verified conformance suite. No change to the
coordination instructions or the role brief contract.

## Changes

### Capability negotiation algorithm
Added a `## Capability negotiation` section to `connect.md` with the exact,
deterministic accept/refuse rules a conforming Orchestrator applies to a
`request`:

- `missing = sorted(required - supported)` and
  `negotiated = sorted((offered ∪ required)  supported)`;
- accept if and only if `missing` is empty;
- an offered capability that is not required never causes a refusal; an offered
  capability the Orchestrator lacks is simply not negotiated;
- all sets are sorted so the negotiated capability set and the refusal reason are
  reproducible; and
- a refusal always names the missing capabilities and the bounded next step.

### Connect conformance suite
Added `conformance/connect/` (a `cases.json` and a README), a versioned suite in
the spirit of `evals/`. Each case is a full connect message with an expected
`valid` or `invalid` outcome; invalid cases also record the expected violation.

- Added `check_connect_conformance` to `scripts/validate.py`, which runs the suite
  in CI and asserts each case's actual conformance matches its expectation.
- Refactored the connect checks around a reusable `connect_violations` helper so
  the `connect.md` worked examples and the conformance suite share one code path.
- Added unit tests for `connect_violations` and for the conformance outcome check.

## Verification

- `python3 scripts/validate.py` passes all checks, including the per-case
  conformance checks against `conformance/connect/cases.json`.
- `python3 -m unittest discover -s tests` passes; the symlink-only test is
  skipped on platforms without symlink permission.
- `python3 scripts/package.py --output dist` produces
  `agent-team-0.1.10.zip` and `agent-team-0.1.10.zip.sha256`.
- `sha256sum -c` confirms the archive against the checksum.

Recheck the package checksum after any later byte or metadata change.
