# Security

Agent Team is an instruction package. Its main safety risks arise when a role receives excessive access, crosses its assigned scope, or produces output that is trusted beyond its evidence.

## Safe use

- Grant each role the least access needed for its task.
- Define permitted evidence and prohibited actions before delegation.
- Give every role an explicit output contract and stop condition.
- Treat role labels as coordination aids, not access controls or isolation.
- Treat task-scoped agents as temporary workers, not persistent identities.
- Inspect material claims and consequential actions before relying on them.
- Stop and request authorization when completion requires wider access or a new external action.

## Reporting a concern

Use the security-reporting channel offered by the repository host. Include the affected version, a minimal reproduction, expected behavior, observed behavior, and impact. Remove identifying or sensitive data from the report.

If only a public reporting channel is available, share a minimal impact summary first and wait for maintainer guidance before providing reproduction details.

Maintainers should acknowledge the report, reproduce it with synthetic data, assess the affected instructions, and publish a correction when ready.
