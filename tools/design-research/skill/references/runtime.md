# Harness execution and recovery

Run the installed `scripts/gan-harness.sh` with Bash. It delegates to Python standard-library code; it is an executable workflow, not a prompt to simulate a workflow.

## Modes

| Mode | Outcome | Application source |
|---|---|---|
| `research` | Compare methods, algorithms, architectures or evaluation designs; run necessary small local PoCs | Preserved |
| `audit` | Inspect core logic and relevant backend behavior; execute checks and report problems/unknowns | Preserved |
| `run` | Improve requested core logic/backend behavior, then execute checks and an independent review | Only the scoped fixer may edit |
| `resume RUN_ID` | Continue an unfinished run after checking identity, source, evidence and test environment | Original mode applies |
| `doctor` | Check structured Codex exec capabilities and a read-only command sandbox smoke test | Preserved; no report workspace |

Choose research for method/evaluation comparisons and non-app research targets. Use audit/run when the request is to inspect/improve existing application logic, whether or not it has a server. An API, database or agent framework is not required.
Start from the main purpose, the core logic contributing to it and the intended outcome. Keep the current/minimal baseline and hard constraints visible; backend checks support the requested goal and relevant constraints.

## Commands and limits

All new research/audit/run executions need `--brief`; `--project` defaults to the current directory. `--slug` defaults to `review` and accepts 1–64 lowercase letters/digits/hyphens starting with a letter/digit.

- `--test-command COMMAND`: repeat for mandatory checks. The parent executes each command via `/bin/bash -c` in a disposable source copy; this is intentional command execution. Use existing checks that assert results, state and relevant failure/recovery behavior.
- `--test-env-file PATH`: explicit literal KEY=VALUE assignments for a test environment. No sourcing, interpolation or implicit loading of project `.env` files. Use isolated test resources; a URL's hostname alone does not prove that a database is disposable.
- `--start-command COMMAND --url http://127.0.0.1:PORT/health`: optionally start an owned local test service in that copy. The URL must be credential-free and loopback. An already responding URL is refused when a start command is supplied.
- `--review PATH`: optional existing report; unrelated to installation dependencies. Reproduce relevant findings rather than trusting screenshots as backend proof.
- `--reference-url URL`: repeat for public primary sources or public implementation examples. Retrieval status is recorded; access alone does not establish a claim.
- `--allow-network`: enable academic queries, public source receipts and live Codex web research. Otherwise these are disabled; `--offline` is an explicit equivalent.
- `--max-iterations N`: default 5, maximum 5, including initial evaluation. At most 3 root-cause groups enter a fix iteration. Two consecutive evaluations without a better severity/check/complexity metric stop the run.
- `--phase-timeout SECONDS`: default 1800 per role/check; output is capped at 4 MB per stdout/stderr stream. Timeout or truncation cannot establish a runtime pass.
- `--model MODEL`: optional exact installed Codex model selection. If omitted, existing Codex configuration applies.

The planner freezes criteria once. It can schedule at most 8 academic-provider requests with 1–10 results each; `all` counts as 3. Each research iteration permits at most 3 declared PoCs. These are execution limits, not a guarantee that every web/MCP action is metered. Offline mode controls this kit's scholarly/live web research; it is not a firewall for the host, model service or configured MCP.

## Independent roles and evidence

The planner, research producer, reviewer and scoped fixer use separate `codex exec` processes with structured output. Read-only roles do not edit source; the fixer uses workspace-write. The parent executes checks and owns receipts. A fixer's claim does not resolve a finding.
Method/accuracy comparisons follow the multi-source reading guidance in [protocol.md](protocol.md). Existing execution/source gates check recorded evidence, not the quality of reading multiple papers; source counts are not a new completion gate.

Every mandatory runtime criterion needs a successful current-iteration receipt tied to the exact source fingerprint. A failed check for that criterion cannot be hidden by another successful check. An issue stays in subsequent reviews and needs new evidence before resolution. Static observations use archived source lines, not imaginary runtime results. Review also explains added complexity and a simpler alternative.

Successful research means that the declared required checks and evidence gates passed. It does not mean that the method was verified for all workloads or that a human approved adoption. No automatic `accepted` decision is allowed.

## Isolation boundaries

Local checks and PoCs run under the existing Codex command sandbox in temporary workspaces. PoCs use returned code and bounded non-secret source inputs outside the application, with no network or package installation. Backend checks copy tracked and visible untracked source, preserving the real working tree; existing local `node_modules`/`.venv` may be reused through read-only links.

The child test environment uses a disposable HOME/cache, test mode and explicitly selected values. Ambient database credentials and project `.env` files are not inherited. Explicit test service/database access may enable network in the check sandbox; the command and test data still need to target isolated resources.

Model roles reuse existing Codex authentication/configuration and may send task context to the configured model. This kit neither installs nor changes that configuration. Source copies exclude secret-looking paths; recorded text is redacted for known credential values and common credential forms. These controls do not prove the absence of every possible secret in arbitrary binary artifacts.

The harness kills only its own process groups, archives sanitized stdout/stderr, and cleans scratch directories. It neither attaches to nor terminates an unrelated running service. It never bypasses a failing sandbox. Prompts prohibit commits, resets, deployment, production mutation, paid experiments and recursive harness calls; these scope rules do not replace repository rules or host permissions.

## Files and evidence links

`PROJECT/docs/design-research/SLUG/` contains readable deliverables:

- `review.md`: severity, target, reproduction, expected/actual results, impact, recommended improvement and linked evidence.
- `fix-report.md`: declared changes and independent before/after evidence.
- `reference-implementations.md`: useful primary-source designs, applicability and limits.
- `design-research.md`, `evidence.json`, `decision.md`: produced when a research dossier is available.
- `research-log.json` and `status.json`: actual source/check scope, status and stopping reason.

`runs/RUN_ID/` preserves state, role invocations/prompts/outputs, access receipts, generated PoC code, execution receipts, stdout/stderr and report snapshots. Prior deliverables and an optional input review are archived under `inputs/` before publication.

Guide the user by the question they want to check, using actual links under the resolved project root and slug:

| What to check | Artifact relative to `PROJECT/docs/design-research/SLUG/` |
|---|---|
| Completion, run ID and stopping reason | `status.json`; follow its `state_path` to `runs/RUN_ID/state.json` for execution state and scope |
| Candidate comparison and conditional recommendation | `design-research.md` and `decision.md`, when a research dossier exists |
| Findings, reproduction and expected/actual behavior | `review.md` and its Evidence links |
| Sources, measured results and reproducible evidence | `evidence.json`, when available, plus report Evidence links and `research-log.json`; follow receipts to stdout/stderr and saved artifacts |
| Reports from a particular execution | `runs/RUN_ID/reports/` and its actual files |
| Requested fixes and independently checked before/after results | `fix-report.md` and its evidence for changes actually made in `run` mode |
| Retained detailed verification/experiment records | Actual note references under `artifacts/design-research/SLUG/RUN_ID/` in the configured Memory project; see [memory-workgraph.md](memory-workgraph.md) |

Check `status.json` first. Top-level reports can change on a later run with the same slug, and a run stopped before review can leave prior reports in place. Match report run IDs and use this run's snapshots for historical references. A missing dossier/report is an unproduced artifact; link existing status/state instead. The presence of `fix-report.md` during research/audit does not establish that application fixes were made. Include only relevant, existing files in the final navigation table and state unexecuted or blocked work explicitly.
Memory paths belong to the selected Basic Memory project, not the target repository's report directory. The outer skill chooses useful records and saves them when permitted; report the actual saved references/status. The harness itself does not install Workgraph or perform Memory writes.

Evidence records have stable EV IDs, workspace-relative paths, SHA-256, iteration and source fingerprint. Before each role/resume the parent rechecks registered artifacts and execution outputs. Declare `artifact_paths` in planned checks/experiments for generated JSON, plots or images; results must exist and are archived. Readable issue evidence links point to actual receipts and raw results. PNG/JPEG/GIF results also render inline. Screenshots are only produced if an actual applicable check captures them; this backend kit does not install a browser or infer a visual review.

The standalone ledger CLI preserves its schema-v1 structural mode. Use `validate --check-artifacts` to require real files/hashes. Parent-owned experiment receipts add execution provenance; file existence by itself does not prove a command was run or a conclusion was correct.

## Outcomes and recovery

| Status | Meaning | Exit |
|---|---|---:|
| `research_complete` | Required research/evidence gates passed; conditional proposal | 0 |
| `passed` | Required checks, no open Critical/High, and complexity review passed | 0 |
| `reviewed` | Audit report completed; findings or failed checks may remain | 0 |
| `blocked` / `cancelled` | Missing prerequisites, inconsistent evidence, failure or interruption | 2 |
| `plateau` / `limit_reached` | Improvement stopped or iteration budget exhausted | 2 |

A doctor exit of 0 means capability/sandbox checks succeeded, not model authentication or end-to-end workflow success.

Use `resume RUN_ID --project PROJECT` only for unfinished work with unchanged source, evidence and explicit environment file. Pending review resumes from existing check results. An interrupted check/experiment uses a new iteration and scratch workspace, preserving prior receipts; commands can execute again and must safely initialize/reset test state. Interrupted source fixing is refused: inspect the preserved diff and start a fresh audit/run. Completed, plateaued or budget-exhausted runs need a new execution. Never reset user changes to make resume pass.

If sandbox diagnostics fail, fix the host setup and retry doctor. Do not switch to unrestricted execution. Installation and the scholarly CLI can still work without a runnable model harness.
