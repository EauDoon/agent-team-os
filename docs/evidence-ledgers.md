# Carry evidence through integration

Use [the ledger](../templates/evidence-ledger.json) when several outputs depend
on the same evidence. It contains a fictional vendor comparison with a visible
contradiction, not verified vendor data.

```sh
python3 scripts/check.py evidence templates/evidence-ledger.json --json
```

Give every inspected source an ID, locator, revision, and inspection date. A
locator should identify the relevant section or record, not merely a homepage.
Record the revision actually inspected. Retain evidence privately where needed;
the ledger does not need copied confidential source text.

Give every decision-relevant claim an ID and status: `supported`, `assumption`,
`unsupported`, or `conflicting`. Link source IDs to the claim and explain the
reasoning. A supported claim needs a source. A conflicting claim needs both
sides and a next step. Unsupported claims need a next step and must not become
facts merely because another role repeats them. Assumptions stay labeled even
when they are useful for a conditional recommendation.

At integration, trace conclusions to claim IDs. Reopen affected claims when an
input revision changes. Record which conclusion changes if an assumption fails.
If a conflict cannot be resolved within scope, preserve it in the final answer
and name the decision needed. The checker verifies references and completeness;
the Auditor must inspect whether each source actually supports the claim.
