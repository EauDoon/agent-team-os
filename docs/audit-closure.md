# Close findings against the delivered revision

Give the Auditor the original request, acceptance criteria, scoped evidence and
exact output revision. Preserve a distinct first assessment before sharing the
Maker's preferred conclusion when independent judgment matters. A separate role
name cannot establish independence, and shared model errors remain possible.

Use the [Markdown report](../templates/audit-report.md) for a narrative review,
or [the JSON report](../templates/audit-closure.json) for a checked closure record.

```sh
python3 scripts/check.py audit templates/audit-closure.json --json
```

Assign a stable ID, severity, owner and evidence to each finding. Preserve the
finding while its owner fixes it. Mark it resolved only after recording a recheck
of the delivered target revision, including the observed result. An old passing
check does not close a new revision. Reopen affected findings if later edits
invalidate their evidence.

Choose `pass` only when no blocking or material finding remains unresolved.
Choose `revise` for a bounded correction and `blocked` when evidence, permission
or a required decision prevents completion. An accepted minor risk needs a
stated disposition; labeling a material issue accepted risk does not bypass the
completion gate. The Orchestrator owns the final recommendation and must not
silently remove inconvenient findings.

The JSON checker verifies closure bookkeeping and separate author/auditor IDs.
It does not authenticate reviewers, execute tests or prove review quality.
