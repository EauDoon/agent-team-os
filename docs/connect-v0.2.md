# Connect v0.2 authoring contract

Use `agent-team-connect/v0.2` only after both participants explicitly agree to
support it. The [v0.2 schema](../schemas/connect-v0.2.schema.json) checks all
six role-brief values as nonempty strings, allows the documented optional brief
fields, and rejects unknown brief properties. The envelope and lifecycle remain
those described in [Connect](../connect.md).

The [v0.1 schema](../schemas/connect.schema.json) is preserved unchanged. It
requires six brief keys but historically permits additional keys and does not
type their values. The `connect` CLI selects the schema from `connect_version`;
it never upgrades a message or reinterprets a v0.1 brief using v0.2 rules.
Unsupported versions fail validation.

To migrate, first negotiate v0.2, review the brief against the standalone
[role-brief contract](../schemas/role-brief.schema.json), and move undocumented
metadata into your own separately scoped records. Do not silently drop unknown
fields or assume that a shape-valid v0.1 brief is safe to execute.

```sh
python3 scripts/check.py connect my-message.json --json
```

This fictional handoff uses the stronger version explicitly:

```json
{
  "connect_version": "agent-team-connect/v0.2",
  "type": "handoff",
  "message_id": "m4",
  "correlation_id": "c1",
  "from": "orch",
  "to": "scout-1",
  "payload": {
    "role_brief": {
      "role": "Scout",
      "access_scope": "Supplied briefs only, read-only.",
      "task": "Extract claims and mark missing information.",
      "evidence": "Supplied statements from the briefs.",
      "output_contract": "Source table with claim, source, and uncertainty.",
      "stop_condition": "Stop when every criterion is covered or marked missing."
    },
    "evidence": [
      "brief-a.txt",
      "brief-b.txt"
    ]
  }
}
```

Both versions have independent conformance cases, run by the repository
validator. A passing contract check does not authenticate participants, grant
permissions or establish that the brief is useful or truthful.
