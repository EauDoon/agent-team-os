# Agent Team

[![build](https://img.shields.io/github/actions/workflow/status/EauDoon/agent-team-os/ci.yml?branch=main)](https://github.com/EauDoon/agent-team-os/actions)
[![license](https://img.shields.io/github/license/EauDoon/agent-team-os)](https://github.com/EauDoon/agent-team-os/blob/main/LICENSE)
[![last commit](https://img.shields.io/github/last-commit/EauDoon/agent-team-os)](https://github.com/EauDoon/agent-team-os)

A wire-format and tool pack for bounded, evidence-backed multi-role work.

Agent Team is an installable skill that ships a versioned contract for delegating to specialist agents, an interop specification for exchanging work between agent systems, and dependency-light Python tooling that checks authored JSON against the shipped schemas and packages the skill as a deterministic ZIP plus SHA-256 checksum.

The coordination protocol itself is part of the host runtime that consumes this skill, not part of the skill. This package standardizes the contract layer without prescribing the orchestration rules. Hosts can document their protocol choices elsewhere and use this skill as the wire format and the validator.

## What the skill ships

- **Role brief schema:** `schemas/role-brief.schema.json` defines the six-field contract that every delegated role must receive. The `role` field is a free-form string, so any host taxonomy is acceptable; the schema enforces presence, length, and structure, not vocabulary.
- **Connect specification:** `connect.md` plus `schemas/connect.schema.json` define a versioned envelope for capability discovery, handoffs (which reuse the role-brief contract), status, result, and structured refusal. The optional v0.2 authoring contract adds stronger handoff validation under its own envelope.
- **Dependency-light validators:** `scripts/check.py` and `scripts/validate.py` enforce the shipped schemas, the connect and negotiation conformance suites, link integrity, manifest completeness, and version pinning; `evals/runner.py` runs the rubric case suite. They use only the Python standard library.
- **Calibrated evaluation harness:** `evals/tasks.json`, `evals/result.schema.json`, `evals/results.v0.1.json`, and `evals/runner.py` provide a bounded synthetic rubric and a calibration fixture that records no performance claims.
- **Deterministic packaging:** `scripts/package.py` and `scripts/verify_package.py` build a ZIP plus SHA-256 and compare archive members against reviewed source bytes before extraction.
- **Templates and examples:** `templates/role-brief.md` and `templates/audit-report.md` are reusable authoring templates; `examples/routing-scenarios.md` walks three fully synthetic end-to-end scenarios.

## Quick start

The installed Agent Team skill is instruction-only and requires no runtime
dependencies, package manager, or external assets. Optional authoring and
verification tools use Python 3.11 or later with the standard library. CI
targets Python 3.11 and 3.14 on Linux and Windows. Record and report exports
require a local filesystem with hard-link support; read-only checks do not.

1. Copy the included `skill/agent-team-os` directory into the target workspace
   at `.agents/skills/agent-team-os/`.
2. Confirm the installed structure:

   ```text
   <workspace>/
   `-- .agents/
       `-- skills/
           `-- agent-team-os/
               |-- SKILL.md
               `-- agents/
                   `-- openai.yaml
   ```

3. Invoke the skill explicitly in Codex:

   ```text
   Use $agent-team-os to draft the six-field role brief and validate it
   against the shipped schema before handing the brief off.
   ```

The included metadata permits implicit invocation when a request would
clearly benefit from the contract layer. This is an activation request to the
host, not evidence of native routing. Explicit invocation is the clearest way
to request the skill. Native positive or negative routing and paired model
evaluation remain unverified; see the
[evaluation procedure](evals/README.md#native-routing-and-fresh-context-evaluation).

### Package and install

The package builder is deterministic and writes a ZIP plus SHA-256 checksum.
It uses only the Python standard library:

```powershell
$ErrorActionPreference = 'Stop'
python .\scripts\validate.py
if ($LASTEXITCODE -ne 0) { throw 'Validation failed.' }
python .\scripts\package.py --output .\dist
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
$digest = (Get-Content -LiteralPath .\dist\agent-team-0.5.0.zip.sha256 -Raw).Split()[0]
python .\scripts\verify_package.py .\dist\agent-team-0.5.0.zip --sha256 $digest
if ($LASTEXITCODE -ne 0) { throw 'Package verification failed.' }
if (Test-Path -LiteralPath .\dist\expanded) { throw 'Extraction directory already exists. Choose a fresh directory.' }
New-Item -ItemType Directory -Path .\dist\expanded -ErrorAction Stop | Out-Null
Expand-Archive -LiteralPath .\dist\agent-team-0.5.0.zip -DestinationPath .\dist\expanded
$project = (Get-Item -LiteralPath (Read-Host 'Existing target project directory')).FullName
if (-not (Test-Path -LiteralPath $project -PathType Container)) { throw 'Choose an existing directory.' }
$destination = Join-Path $project '.agents\skills\agent-team-os'
New-Item -ItemType Directory -Path (Split-Path $destination) -Force | Out-Null
if (Test-Path -LiteralPath $destination) { throw 'Skill already exists. Review an explicit upgrade separately.' }
New-Item -ItemType Directory -Path $destination -ErrorAction Stop | Out-Null
Get-ChildItem -LiteralPath .\dist\expanded\agent-team-0.5.0\skill\agent-team-os -Force | Copy-Item -Destination $destination -Recurse
```

On Bash:

```bash
python3 scripts/validate.py || exit 1
python3 scripts/package.py --output dist || exit 1
read -r digest archive_name < dist/agent-team-0.5.0.zip.sha256 || exit 1
python3 scripts/verify_package.py dist/agent-team-0.5.0.zip --sha256 "$digest" || exit 1
mkdir -- dist/expanded || { echo 'Choose a fresh extraction directory.' >&2; exit 1; }
unzip -q dist/agent-team-0.5.0.zip -d dist/expanded || exit 1
read -r -p 'Existing target project directory: ' project || exit 1
project=$(cd -- "$project" && pwd -P) || exit 1
destination="$project/.agents/skills/agent-team-os"
mkdir -p -- "$project/.agents/skills" || exit 1
mkdir -- "$destination" || { echo 'Skill already exists. Review an explicit upgrade separately.' >&2; exit 1; }
cp -R -- dist/expanded/agent-team-0.5.0/skill/agent-team-os/. "$destination/" || exit 1
```

Verify the checksum before copying. From the reviewed source checkout, run
`python3 scripts/verify_package.py dist/agent-team-0.5.0.zip` to compare
archive members with source bytes before extraction. The package contains the
skill, templates, schemas, examples, validator, and release documentation. It
does not publish or change remote metadata.

The builder replaces an existing archive and checksum pair with rollback on
ordinary write failures. If rollback itself fails, the command reports
failure and retains the recovery directory it names. Preserve those copies
and inspect both output files before recovery; a failed rollback does not mean
the old pair was restored.

Run the commands from the reviewed source checkout. Select an existing target
project explicitly; these recipes do not use `CODEX_HOME` or modify a global
installation. An existing skill directory is never merged or overwritten. For
an upgrade, compare the reviewed new files with the installed files, preserve
a backup, and authorize the replacement separately. A failed copy can leave
only the newly created directory partially populated; inspect it before retrying.

## Operator tools

Start with the [operator quickstart](docs/operator-quickstart.md) for a checked
routing plan, evidence ledger, handoff acceptance, and audit closure workflow.
Use only the records that help the task.

| Tool | Local outcome |
| --- | --- |
| `scripts/author.py` | Compose complete briefs, explicit v0.2 handoffs, and actionable refusals. |
| `scripts/inspect_records.py` | Inspect readiness, plan changes, evidence impact, and audit remediation. |
| `scripts/inspect_records.py negotiate` | Compute the exact accept or refuse payload the connect negotiation rules require. |
| `scripts/check.py brief` or `connect` | Validate authored JSON before handing off work. |
| `scripts/check.py plan` | Catch dependency cycles, duplicate output ownership, and inconsistent budgets. |
| `scripts/check.py evidence` | Catch missing claim sources and unresolved evidence gaps. |
| `scripts/check.py audit` | Require current-revision rechecks before significant findings close. |
| `scripts/evaluate.py` | Check complete paired runs, inspect each task, and export escaped reports. |
| `scripts/packet.py` | Check related records and create or verify exact-byte receipts. |
| `scripts/verify_package.py` | Compare a ZIP with reviewed source bytes before extraction. |

Checks and inspections are read-only. Authoring, report exports, and packet
receipts write only explicitly requested new files; the package builder
writes its archive and checksum. They do not send messages, execute role
instructions, authenticate agents, or enforce permissions. Each tool accepts
`--version` and prints `agent-team X.Y.Z`. See
[contract checking](docs/contract-checking.md) for input limits and exit codes.

## Good use cases for the contract layer

The shipped schemas and validators are useful whenever a host wants to:

- Hand a bounded task to a specialist agent and verify the brief before dispatch.
- Receive a handoff that names a role, an access scope, and an output contract
  the host can check against its own rules.
- Exchange work with another agent system through a versioned envelope the
  other system can also validate.
- Run the same authored brief through multiple model providers and compare
  the results without re-authoring.
- Calibrate a host's routing policy against synthetic tasks before exposing
  it to real work.

Detailed role briefs are available in
[`examples/routing-scenarios.md`](examples/routing-scenarios.md). Reusable
briefs and audit reports are in [`templates/`](templates/).

## Connecting other agents

If another agent or system needs to hand work to, or receive work from, an
agent host that uses this skill, use the connection specification in
[`connect.md`](connect.md). It is a versioned, machine-readable contract
(`schemas/connect.schema.json`) covering capability discovery, message types,
handoffs that reuse the six-field role brief, status and gap semantics, and
the security boundaries that keep a connection bounded. It is a
specification, not a runtime; the transport and real permission enforcement
remain the deployment's job.

## The role brief contract

Every delegated role must receive:

- **Role:** the task-scoped assignment (any non-empty string; the host runtime
  decides which role names are valid for a given task).
- **Access scope:** exact sources, tools, actions, and read or write limits.
- **Task:** the distinct question, artifact, or risk the role owns.
- **Evidence:** the inputs to inspect and the traceability required for claims.
- **Output contract:** the expected format, contents, quality bar, and recipient.
- **Stop condition:** the event that ends work, including completion, a
  blocking gap, or a scope conflict.

A role should not begin with missing fields, duplicate another role, or
receive broader access than its task requires. The machine-readable contract
is [`schemas/role-brief.schema.json`](schemas/role-brief.schema.json), and the
dependency-light checker is [`scripts/check.py`](scripts/check.py).

## Safety boundaries

Agent Team improves coordination, but coordination is not access control.

- Treat role separation as an operating pattern, not a security boundary.
- Enforce real permissions through the execution environment.
- Grant only the access required for the assigned task.
- Do not allow a role to widen its scope, redefine the request, or invent
  authorization.
- Preserve uncertainty when evidence is missing, weak, or contradictory.
- Require explicit authorization before any consequential external action
  that was not already approved.
- Keep human review in the loop for consequential decisions and actions.

Confidence, silence, and role labels are not substitutes for evidence. An
independent check is not a guarantee.

## Repository map

```text
agent-team-os/
|-- README.md                       # Overview and tool inventory
|-- LICENSE                         # MIT License
|-- SECURITY.md                     # Safe-use and reporting guidance
|-- CONTRIBUTING.md                 # Design rules and contribution process
|-- PROVENANCE.md                   # Creation, review, and evaluation record
|-- CHANGELOG.md                    # Version history
|-- VERSION                         # Current package version
|-- connect.md                      # Agent interoperability connection spec
|-- templates/
|   |-- role-brief.md               # Six-field role brief template
|   |-- audit-report.md             # Independent audit report template
|   |-- audit-closure.json          # Audit closure record
|   |-- evidence-ledger.json        # Evidence ledger record
|   |-- routing-plan.json           # Routing plan record
|   |-- operator-packet.json        # Packet index over the records above
|   |-- execution-checkpoint.md     # Execution checkpoint note
|   `-- handoff-receipt.md          # Handoff acceptance receipt
|-- schemas/
|   |-- VERSIONS.md                 # Pinned version of every schema
|   |-- role-brief.schema.json      # Six-field role brief contract
|   |-- connect.schema.json         # Connect message contract, v0.1
|   |-- connect-v0.2.schema.json    # Connect authoring contract, v0.2
|   |-- routing-plan.schema.json    # Routing plan record
|   |-- evidence-ledger.schema.json # Evidence ledger record
|   |-- audit-closure.schema.json   # Audit closure record
|   |-- packet.schema.json          # Record packet index, v0.1
|   |-- packet-v0.2.schema.json     # Record packet with closure policy, v0.2
|   `-- packet-receipt.schema.json  # Exact-byte packet receipt
|-- evals/
|   |-- tasks.json                  # Versioned synthetic evaluation fixtures
|   |-- cases/                      # Rubric cases for the six tasks
|   |-- runner.py                   # Rubric case runner
|   |-- run.schema.json             # Paired-run record shape
|   |-- result.schema.json          # Versioned result shape
|   |-- results.v0.1.json           # Calibration fixture, no performance claims
|   `-- README.md                   # Evaluation protocol and baseline
|-- conformance/
|   |-- connect/                    # Connect message conformance suite
|   |-- connect-v0.2/               # Optional v0.2 authoring contract suite
|   `-- negotiation/                # Capability negotiation decisions
|-- scripts/
|   |-- validate.py                 # Dependency-light contract and link checker
|   |-- package.py                  # Deterministic ZIP and checksum builder
|   |-- verify_package.py           # Archive verification against source bytes
|   |-- check.py                    # Brief, connect, plan, evidence, audit checks
|   |-- contracts.py                # Bundled JSON Schema subset checker
|   |-- author.py                   # Brief and handoff authoring
|   |-- inspect_records.py          # Readiness, impact and negotiation inspection
|   |-- evaluate.py                 # Paired-run evaluation
|   |-- packet.py                   # Record packet receipts
|   |-- version.py                  # The one reader of VERSION
|   `-- workflows.py                # Semantic checks and the reference negotiator
|-- docs/
|   |-- release-notes-0.5.0.md      # Versioned release notes (one per release)
|   `-- ...                         # Operator guides (authoring, handoffs, etc.)
|-- .github/workflows/ci.yml        # Pull request and push checks
|-- .github/workflows/release.yml   # Tag-triggered release build
|-- examples/
|   `-- routing-scenarios.md        # Three synthetic end-to-end scenarios
`-- skill/
    `-- agent-team-os/
        |-- SKILL.md                # Slim contract description
        `-- agents/
            `-- openai.yaml         # Display metadata and invocation policy
```

## Limitations

- The skill is an instruction layer, not an execution engine, storage system,
  authorization mechanism, or isolation boundary.
- Output quality remains limited by the supplied evidence, available tools,
  model behavior, and enforced permissions.
- Delegation adds overhead when roles overlap or the task is too small.
- Task-scoped roles do not provide durable identity, memory, authority, or
  trust across requests.
- Human judgment remains necessary before consequential use.
- The shipped schemas accept any non-empty role name. Hosts must define and
  enforce their own role vocabulary.

## Authorship and provenance

EauDoon directed, reviewed, and takes responsibility for the result. This
public package uses synthetic scenarios. See [`PROVENANCE.md`](PROVENANCE.md)
for the complete creation record.

Agent Team is an independent community project.

## License

Released under the MIT License. See [`LICENSE`](LICENSE).