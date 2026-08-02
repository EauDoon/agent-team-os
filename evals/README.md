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
