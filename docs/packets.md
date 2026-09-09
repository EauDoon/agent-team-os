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
