# Execution checkpoint

## Limits agreed before dispatch

Record the work-unit definition, total work units, review reserve, maximum
assignments, maximum concurrent assignments and maximum correction rounds.
Choose units the execution environment can actually observe. Record any hard
deadline or token limit only when supplied or agreed, and say how it is measured.

## Current accounting

For every assignment, record pending, working, stopped or accepted, units used,
remaining contracted work and latest accepted revision. Count failed attempts,
delegated activity and integration work. Separate measured usage from estimates.

## Continue or stop

Record the remaining task-work budget after reserving review capacity. Continue
only when the next bounded step fits the remaining scope and budget. Name the
specific expected benefit before granting another correction round.

## Cancellation and recovery

Record which pending assignments were canceled, which workers were asked to
stop, and which stops were acknowledged. Record partial artifacts and uncertain
effects. Keep ownership with a running worker until its stop is confirmed.
List the exact decision required to resume and the last accepted checkpoint.
