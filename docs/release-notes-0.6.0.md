# Agent Team 0.6.0

This release adds a reference implementation of connect capability
negotiation, a version flag on every tool, a release gate with build
provenance, and a reproducible package digest, and it fixes validator,
contract-checker and packet gaps found in review. No schema or wire version
changed: connect v0.1 and v0.2, packet v0.1 and v0.2, and every other contract
keep their acceptance behavior. Python 3.11 or later and the standard library
suffice.

## Added

- **Reference negotiator.** `negotiate()` in `scripts/workflows.py` implements
  the `connect.md` negotiation rules. `scripts/inspect_records.py negotiate
  REQUEST --advertise TOKEN` computes the exact accept or refuse payload for a
  conforming request, checks it against the declared version's response
  schema, and sends nothing. `conformance/negotiation/cases.json` pins seven
  decisions for other implementations, and `scripts/validate.py` runs them.
- **`--version` everywhere.** `check`, `author`, `inspect_records`,
  `evaluate`, `packet`, `validate`, `package` and `verify_package` print
  `agent-team 0.6.0`. `scripts/version.py` is now the single reader of
  `VERSION` for the tools, the Makefile and CI.
- **Manifest completeness.** `scripts/validate.py` fails when a file under a
  shipped tree, a root document, or the current release notes are missing from
  `package-manifest.json`. The package now ships every release-notes file and
  the showcase (90 files).
- **Release gate and provenance.** `scripts/validate.py --release-tag TAG`
  requires the tag to equal `v<VERSION>`, a dated changelog entry and shipped
  release notes. The release workflow runs it first, refuses a tag whose commit
  is not on `main`, and attests the archive with `actions/attest`. Verify a
  downloaded archive with
  `gh attestation verify agent-team-0.6.0.zip --repo EauDoon/agent-team-os`.
- **Checks on the skill itself.** Every path `SKILL.md` cites must exist and
  ship, and the skill metadata may not advertise coordination.
- **Maintenance.** Dependabot proposes weekly updates for the SHA-pinned
  actions, `make ci` runs every CI step in order, and the changelog follows
  Keep a Changelog with dated entries.

## Changed

Review these before upgrading:

- **Archive digest.** Package members are stored uncompressed instead of
  Deflate, so a build of the tagged commit reproduces the published SHA-256 on
  any supported Python, including CPython builds that ship zlib-ng. The archive
  is about 400 KB instead of about 115 KB. The verifier still accepts Deflate
  archives from 0.5.0 and earlier.
- **Identity comparison.** Audit author and auditor IDs, and paired-evaluation
  runner and reviewer IDs, are compared ignoring case, surrounding whitespace
  and Unicode compatibility forms. An audit whose author and auditor differ
  only in those ways, such as `Maker` and ` maker`, now fails. A blank runner or
  reviewer ID is rejected.
- **Connect examples.** `connect.md` example 2 now negotiates
  `["bounded-scope", "evidence-trace"]`, as the rules require, and example 3 is
  the rules' refusal of example 1 (`missing required capabilities:
  bounded-scope`) under its own `message_id`, `msg-0006`. The refusal separator
  is pinned to a comma and a space. If you copied the old example text, update
  it. No schema or existing conformance case changed.
- **Skill metadata.** `agents/openai.yaml` describes six-field role briefs and
  connect contracts instead of routing work across agents.
- **CI.** Contract checks run once per change (pushes to `main`, pull
  requests, manual dispatch), with a timeout and without persisted checkout
  credentials. Tag pushes run only the release workflow.

## Fixed

- `scripts/validate.py` passed silently when any ancestor directory was named
  `dist` or `.git`, which the documented `dist/expanded` extraction layout
  triggers. It now checks the tree it is given, skips in-checkout environments
  such as `.venv` and `node_modules`, and reports an empty Markdown link target
  instead of crashing.
- A nullable `type` list, a string count or bound, or a string `required` in a
  schema raised a `TypeError` past every handler or was silently misread. They
  now fail cleanly, and an unusable schema is reported as a failed check.
- A schema `pattern` `$` matched before a trailing newline. It now anchors only
  at the end of the string, as in ECMA-262.
- On Windows, a packet record path such as `plan.json.` opened `plan.json`, so
  one file counted as two records. Such paths are rejected, and a record that
  names a file already listed, including through a hard link, fails.
- Evaluation records inside a packet now use the caller's `schema_root`.
- Documentation no longer describes a delegation gate or coordination
  workflow, the README repository map is complete, and the 0.5.0 release notes
  no longer mention a 0.4.0 tag that was never pushed.

## Verify this release

```sh
python3 scripts/validate.py --release-tag v0.6.0
python3 scripts/package.py --output dist
python3 scripts/verify_package.py dist/agent-team-0.6.0.zip
```

## Limitations carried forward

- The skill is an instruction layer, not an execution engine, storage system,
  authorization mechanism, or isolation boundary.
- A passing check establishes shape and bookkeeping, not truthful evidence,
  real permission enforcement or an independent review.
- The negotiator computes a decision only; it does not authenticate the
  initiator or enforce the negotiated capabilities.
- Human judgment remains necessary before consequential use.

## Authorship

EauDoon directed, reviewed, and takes responsibility for the result. This
public package uses synthetic scenarios. See `PROVENANCE.md` for the complete
creation record.
