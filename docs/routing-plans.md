# Check ownership before dispatch

Record a routing decision with [the JSON template](../templates/routing-plan.json).
The supplied small-internal-tool example names three assignments with disjoint
outputs. Read-only review has no write resources. Replace the fictional values
with a bounded task, then run:

```sh
python3 scripts/check.py plan templates/routing-plan.json --json
```

Choose `solo` with one assignment when there is no distinct specialist benefit.
For `team`, state the benefit in `delegation_reason`. Each assignment needs a
complete six-field brief, one output identifier, dependencies and write resource
names. A dependency means its accepted output must exist before the dependent
assignment starts. Independent ready assignments may run concurrently.

The checker rejects unknown dependencies, cycles, duplicate outputs and write
ownership overlaps, including a parent resource and its child. Resource names
are logical identifiers compared without case and with normalized separators,
not file permissions or filesystem discovery. Use one owner for a shared file;
other roles can return proposed changes for that owner. A sequential ownership
transfer needs a revised plan after the first owner stops.

The checker cannot establish that the delegation benefit is real or that the
execution environment enforces the brief. Review both before dispatch.

Plans are bounded to 64 assignments, 63 dependencies per assignment, 256 write
resources per assignment and 1024 write resources in total. Oversized arrays
fail before item validation or ownership analysis. Resource overlap checks use
a path-prefix index, and semantic routing diagnostics stop after 32 findings
plus an omission notice. These limits bound authoring checks; they do not grant
permission to run that many assignments or access those resources.
