# Agent Team 0.2.0

This release adds optional local operator tooling while preserving the
instruction-only skill and the six-field role brief.

- Check authored briefs and connection messages against complete bundled schema
  constraints, including nested types and unknown fields.
- Check routing dependencies, exclusive artifact ownership and execution budgets.
- Carry evidence references and unresolved claims through integration.
- Record revision-aware handoff acceptance, resumption and audit closure.
- Summarize paired evaluations with shared inputs and no dropped task arms.
- Verify ZIP contents against a reviewed source checkout without extraction.

Existing v0.1 connection acceptance is preserved against its unchanged schema.
The new opt-in `agent-team-connect/v0.2` wire version enforces the complete
role-brief contract. The CLI checks the declared version without upgrading it.
Wrong envelope or payload types still fail the applicable published schema.

The operator checker uses Python 3.11 or later and only the standard library.
Direct script and module execution are supported. No runtime scheduler,
transport, access-control layer, automatic installation or remote action is
added. The public evaluation result remains an empty calibration fixture.
Synthetic tests establish tool behavior, not empirical agent superiority.
