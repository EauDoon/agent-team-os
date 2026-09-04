# Release notes for 0.1.8

This release adds an agent interoperability layer. It is a specification and
protocol, not a runtime, and it does not change the coordination instructions or
the role brief contract.

## Changes

- Added `connect.md`, a versioned agent-interoperability specification for how an
  external agent or system connects to an `agent-team-os` Orchestrator. It covers:
  - design principles (bounded and not trusted, evidence travels with the message,
    one owner per artifact, uncertainty preserved, least privilege, graceful
    degradation);
  - participants and the connection lifecycle;
  - the message envelope and a capability discovery/negotiation model;
  - the five message types and their typed payloads
    (`request`, `response`, `handoff`, `status`, `result`);
  - status and gap semantics, authorization and security boundaries, and versioning
    rules;
  - structured, actionable rejection behavior and copy-paste-ready worked examples.
- Added `schemas/connect.schema.json`, the machine-readable connect message
  contract. The `handoff` payload reuses the six-field role brief from
  `schemas/role-brief.schema.json`.
- Added `check_connect` to `scripts/validate.py`, which verifies the connect schema
  requires the message envelope, declares all message types, and reuses the
  six-field role brief in a handoff. Added a unit test.
- Packaged both new files and documented the spec in the README.

## What this is not

- No server, endpoint, transport, authentication, or enforcement. A conforming
  deployment supplies those. The contract only defines the message content and its
  rules.

## Verification

- `python3 scripts/validate.py` passes all checks, including the new connect
  checks and the link checks for the new `connect.md` references.
- `python3 -m unittest discover -s tests` passes; the symlink-only test is
  skipped on platforms without symlink permission.
- `python3 scripts/package.py --output dist` produces
  `agent-team-0.1.8.zip` and `agent-team-0.1.8.zip.sha256`.
- `sha256sum -c` confirms the archive against the checksum.

Recheck the package checksum after any later byte or metadata change.
