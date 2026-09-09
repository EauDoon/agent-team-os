# Check a bounded handoff packet

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
every record to pass. It uses the same exclusively published new-file behavior as
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
