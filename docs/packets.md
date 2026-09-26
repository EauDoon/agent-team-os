# Check a bounded handoff packet

Receipt verification also reports `records_added`, `records_removed`, changed
field names per record in `record_changes`, `invalid_records`, and whether
record order changed. The existing strict byte and order comparison remains:
formatting drift still fails. Diagnostics never read paths from the receipt and
never print record contents. Invalid current records remain failures while the
affected record IDs help direct repair.

A packet is an explicit index of related local records. It does not copy them,
execute instructions or establish that their claims are true.

```sh
python3 scripts/packet.py templates/operator-packet.json
python3 -m scripts.packet templates/operator-packet.json
```

Use the [packet template](../templates/operator-packet.json) and
[schema](../schemas/packet.schema.json). Give each record a unique ID, kind and
relative path. Supported kinds are brief, connect, plan, evidence, audit and
evaluation. Each is checked with its existing contract; evaluation records also
need the complete paired suite. Wire versions retain their existing meanings.
The v0.1 packet retains conformance-only behavior. Use the opt-in v0.2 closure
contract below when a receipt must also require specific evidence and audit
bookkeeping for an output revision.

Packets permit at most 16 records and 4 MiB of total index and record bytes,
with the usual 1 MiB limit per file. Paths use canonical forward slashes and
must resolve to files inside the index's directory. Absolute paths, parent
traversal, drive/stream names, duplicate paths and symbolic-link references fail.
The tool never follows a recursive packet index or searches for extra files.

The report identifies checked byte snapshots by SHA-256, records per-file
conformance, and includes at most 20 diagnostics per record. Any invalid record
returns `ok: false` and exit status 1 while retaining unaffected record results.
A malformed index or exceeded packet limit returns a generic failure. Passing
all record checks does not verify relationships between natural-language claims,
complete the task, authorize actions or prove an independent audit occurred.

## Preserve and recheck the exact packet

```sh
python3 scripts/packet.py templates/operator-packet.json --receipt packet-receipt.json
python3 scripts/packet.py templates/operator-packet.json --verify-receipt packet-receipt.json
```

A [receipt](../schemas/packet-receipt.schema.json) records the task ID, index
digest, and each record's ID, kind, path, digest and byte length. Creation requires
every record and any declared closure to pass. It uses the same exclusively published new-file behavior as
[authoring](authoring.md), including the hard-link filesystem requirement.
Existing files are never overwritten. Receipt output and verification are
mutually exclusive.

Verification checks the current packet with the current bundled validators before
comparing its captured bytes with the receipt. Even whitespace-only edits cause
a mismatch. A failed check or mismatch returns `ok: false` and exit status 1.
Only paths from the explicitly supplied packet are read; a receipt never drives
file access. Receipts do not freeze validator implementations, authenticate their
author or record approval. Keep the reviewed package revision alongside them when
reproducibility across tool upgrades matters.

## Require evidence and audit closure for a revision

The [v0.2 packet schema](../schemas/packet-v0.2.schema.json) adds a required
`closure` object. For example, given records with IDs `audit` and `evidence`:

```json
{
  "audit_record": "audit",
  "evidence_record": "evidence",
  "target_revision": "fictional-tool-r2",
  "target_source": "output",
  "required_claims": ["empty-title"]
}
```

Set `packet_version` to `agent-team-packet/v0.2`. Keep the existing `task_id`
and `records` fields. Select the exact audit and evidence records by their packet
IDs, the output source by its ledger ID, and the claims required for closure by
their ledger IDs. The claim list must contain 1 to 64 unique entries. Derive this
list from the original acceptance criteria; the tool cannot decide whether the
selected criteria fully answer the request.

Closure requires all packet records to conform and:

- The selected records exist with kinds `audit` and `evidence`.
- The audit recommends `pass` and targets the declared nonblank revision.
- The ledger contains the target source at that same revision.
- Every required claim exists, has status `supported`, and cites the target source.

Other sources may have different revisions. Unselected claims are not closure
requirements; keep their unresolved risks visible in the final delivery.
An individually valid `revise` audit or unsupported required claim now blocks
this opt-in closure. `closure.ready` is false, top-level `ok` is false, exit
status is 1, and no receipt is created. The report retains record results and up
to 20 closure failures with a full `failure_count`. Missing or invalid selected
records fail without hiding the other records. Closure checks reuse the exact
parsed snapshots that were hashed; referenced source locators are never opened.

Supply the receiver's independently expected revision for both creation and
verification:

```sh
python3 scripts/packet.py packet.json --target-revision fictional-tool-r2 --receipt receipt.json
python3 scripts/packet.py packet.json --target-revision fictional-tool-r2 --verify-receipt receipt.json
```

`--target-revision` fails on a different declared target or a v0.1 packet, so
falling back to conformance-only records cannot satisfy this explicit check.
A coherent old packet and its unchanged receipt also fail when the receiver
expects a newer revision. Verification retains closure diagnostics even when
all individual records are valid and no bytes changed.

Without the option, v0.2 checks only its own declared target; it cannot recognize
a self-consistent old packet as stale. The option is not replay protection for
the same revision, task identity verification, or authentication. Keep the
expected revision and receipt in a trusted receiver context. A party able to
replace both packet and receipt can create a new consistent pair. Source dates,
artifact contents, natural-language claims, actual reviewer independence, and
handoff acceptance remain outside this gate. The existing evidence inspector
provides a separate explicit date review when needed.

The v0.1 receipt format is unchanged: its index digest already preserves every
closure field. Older packet tools reject the new v0.2 index rather than silently
skipping its closure requirements. See the
[synthetic walkthrough](closure-walkthrough.md) for complete, incomplete,
altered and replayed cases from source or an extracted package.
