# Check authored contracts

Use the optional standard-library CLI before sending a JSON role brief or
connection message. The installed skill itself needs no Python runtime.

```sh
python3 scripts/check.py brief my-brief.json
python3 scripts/check.py connect my-message.json --json
python3 -m scripts.check connect my-message.json --json
```

Exit status is 0 for a conforming document and 1 for an invalid or unreadable
document. Argument errors return 2. JSON output contains `ok`, `kind`, and
`failures`. Inputs must be UTF-8, at most 1 MiB, and have unique object keys and
finite numbers. The CLI reads the named file and local bundled schemas only.
It sends no messages and executes no content from the document.

The checker implements the schema keywords used in this repository, including
nested types, required keys, unknown-field rejection, local references and
conditional payloads. It is not a general JSON Schema implementation. It rejects
unsupported assertion keywords rather than pretending to validate them.

Passing checks establishes shape, not truthful evidence, useful scope, actual
permission enforcement, authenticated identity or successful execution. Review
all six brief fields for meaningful content before delegation.
