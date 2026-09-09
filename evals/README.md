# Bounded evaluation suite

This directory defines a small, versioned calibration suite. It is a protocol
fixture, not evidence that one arm outperforms another.

## Arms

- **Strong solo baseline:** one capable generalist receives the task, the
  supplied evidence, and the same acceptance criteria. It may not delegate.
- **Current Agent Team instructions:** the same task and evidence, with the
  skill available and the delegation gate enabled.

Run both arms on the same task order, record the prompt and evidence version,
and score only the acceptance checks in `tasks.json`. Keep any holdout tasks
and raw transcripts outside this repository. Add a result only after the run
is independently reviewed, and never infer a general performance claim from
this bounded suite.

`results.v0.1.json` is intentionally empty and has `calibration_fixture`
status. The result shape is defined by `result.schema.json`.

## Record and summarize a paired run

Use `run.schema.json` for a separate reviewed-run document. This does not change
or populate the public calibration fixture. Keep raw evidence, transcripts and
holdout material outside the public repository.

Record `run_version` as `agent-team-run/v0.1`, the suite version, status
(`synthetic` for tool checks or `reviewed` for an independently reviewed run),
and distinct runner and reviewer IDs. Each record names the task ID, arm (`solo`
or `current`), prompt revision, evidence revision, ordered acceptance `checks`,
total `tokens`, and `duration_seconds`. Also record `output_revision`,
`review_evidence` (the scoring record locator), and `configuration` (model,
tools, routing instructions and relevant run settings). Each check is `pass`, `fail`, or
`unverified`, in the same order as the task's acceptance list. Include failed
and interrupted runs; mark checks unverified rather than silently dropping them.
Measure whole-task usage consistently, including delegated work and integration.

```sh
python3 scripts/evaluate.py my-reviewed-run.json
```

The tool requires every suite task in both arms, matching prompt and evidence
revisions, exactly the expected number of checks, and nonnegative measurements.
It reports per-arm counts and usage and the difference in passed checks. It
never treats unverified checks as passes. The status is preserved in the output.
No result is written to the repository.

Preregister task order, scoring and resource limits before running. Preserve
blinded first-pass scoring where practical. Separate role IDs are bookkeeping,
not proof of independent review. The summary is descriptive for the supplied
run, with no statistical significance, causal attribution, general superiority
or optimality claim. Repeated runs and an independently held-out comparison
remain necessary for broader conclusions.

Measurements and per-arm totals must remain representable: durations must be
finite binary64 values, and token counts must be exact JSON integers from 0 to
9007199254740991. An overflowing aggregate fails the run instead of emitting
Infinity or rounded token counts. Successful CLI output is strict JSON.

## Inspect the task-level comparison

Successful summaries also include `tasks` in suite order. Each entry shows both
arms' recorded result for every named acceptance criterion, the shared prompt
and evidence revisions, each output revision and the difference in passed
checks. These task differences reconcile to the overall difference. Failures
and unverified checks remain visible even when total scores are equal.

Use the breakdown to inspect where the supplied run differs, not to infer why
it differs. Task-level counts remain descriptive and are not a significance
test, causal attribution or general performance claim.
