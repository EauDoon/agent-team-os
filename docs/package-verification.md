# Verify package contents before installation

Run verification from a source checkout whose revision you have reviewed:

```sh
python3 scripts/package.py --output dist
python3 scripts/verify_package.py dist/agent-team-0.2.0.zip
```

The verifier compares every archive entry with the current source manifest and
file bytes. It rejects extra, missing or duplicate entries, non-regular files,
encrypted entries, changed content and oversized archives. It reads the ZIP
without extracting or executing any member. Archives are limited to 32 MiB;
decompression is bounded to each expected source file's size.

If you obtained an expected digest through a trusted channel, pass it with
`--sha256` followed by the 64-character digest. The result includes the computed
SHA-256, source version and file count. Exit status 0 means verification passed;
1 means it failed. Installation remains a separate explicit action.

A checksum downloaded beside an archive detects accidental corruption but does
not independently authenticate its publisher. Comparing against an unreviewed
or attacker-modified source tree does not establish trust. Use the checker from
your reviewed source, not an unchecked downloaded script. It verifies a package
against that source revision, not against whichever release happens to be latest.
