# Author records without replacing existing work

Provide all six role-brief fields explicitly:

```sh
python3 scripts/author.py brief --role Maker --scope "Supplied files only." --task "Build the fictional tool." --evidence "Supplied requirements." --deliver "Tool and acceptance checks." --stop "Acceptance or scope gap." --output brief.json
python3 scripts/check.py brief brief.json --json
```

The composer checks the complete brief before writing. It rejects blank fields,
requires a new output filename and never invents scope or authorization. Review
the written fields before using the brief. Existing files and symlinks are not
replaced. Parent directories must already exist.

The writer stages complete UTF-8 content, then publishes it with an exclusive
same-directory hard link. If the filesystem cannot support that operation, it
fails without silently falling back to overwrite behavior. Records are limited
to 1 MiB. Success returns JSON with `ok: true`; invalid input or an unavailable
output returns generic JSON with `ok: false` and exit status 1. No role is started
and no message is sent. Module invocation via `python3 -m scripts.author` is also
supported.

## Compose a handoff or an actionable refusal

After both participants agree to v0.2, wrap an inspected brief or write a refusal:

```sh
python3 scripts/author.py handoff --version agent-team-connect/v0.2 --from owner --to maker --message-id m1 --correlation-id task1 --brief brief.json --output handoff.json
python3 scripts/author.py refusal --version agent-team-connect/v0.2 --from owner --to initiator --message-id m2 --correlation-id task1 --reason "Requested action is outside scope." --next-step "Request a bounded scope decision." --output refusal.json
```

The composer copies the brief without widening access or rewriting its fields.
It validates the complete message before publication. A missing or malformed
brief produces no output file. Newly composed messages require the explicit
version flag; the existing v0.1 validation contract remains unchanged. Files are
draft messages only, and producing one neither negotiates a connection nor sends it.
