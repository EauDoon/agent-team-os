# Synthetic closure walkthrough

This example uses the small internal tool scenario: a fictional work-item
tracker must reject an empty title. All roles, evidence and audit results are
fixtures. No tracker, worker, independent reviewer, connection or external action
runs. Passing proves the record-handling checks behaved as expected.

With Python 3.11 or later, from either the source checkout or the extracted
deterministic package directory, run:

```sh
python3 examples/closure-walkthrough.py --output ../synthetic-closure-run
```

Choose a new output directory. The script writes only there and runs the bundled
CLIs using the same interpreter. It authors and checks a six-field brief and
v0.2 handoff, writes clearly synthetic evidence and audit fixtures, inspects
them, then creates and verifies a v0.2 closure packet receipt for
`fictional-tool-r2`. This does not accept the handoff or release dependent work.

The script makes separate copies for each negative case:

| Case | Expected result |
| --- | --- |
| Complete records for r2 | Receipt created; exact-byte verification passes. |
| Required claim is unsupported | Closure fails; no new receipt. |
| Passing audit belongs to r1 | Closure fails despite valid individual records. |
| Target evidence source belongs to r1 | Closure fails despite valid individual records. |
| Evidence file is missing | Record check and closure fail. |
| Required claim cites only another source | Closure fails. |
| Evidence gains only a newline | Closure still passes; exact-byte receipt verification fails. |
| Coherent r1 packet with its own valid receipt is replayed for r2 | Verification fails against the receiver's explicit expected revision. |

Inspect `complete/packet.json`, `complete/receipt.json`, `summary.json` and
`transcript.json` inside the output directory. The transcript includes all
18 CLI invocations, exit codes and JSON reports. The script exits successfully
only when both positive and negative outcomes match these expectations. Negative
case directories retain a copy of the original receipt for inspection; failed
closure never creates the requested `new-receipt.json`.

Before extracting a built archive, use
`python3 scripts/verify_package.py path/to/agent-team-0.4.0.zip` against reviewed
source as described in [package verification](package-verification.md). The
walkthrough, schema and all tools are in the package manifest. Repository tests
run this same journey from both source and a fresh external extraction.

Review the [closure limits](packets.md#require-evidence-and-audit-closure-for-a-revision)
before using real records. A digest cannot establish claim truth, genuine review,
permission, current artifact contents, or freshness when the expected revision
comes from the packet itself.
