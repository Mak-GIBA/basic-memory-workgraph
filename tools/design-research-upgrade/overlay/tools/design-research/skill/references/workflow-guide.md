# Design Research — one user-facing entry, explicit workflow boundaries

This is the default operating contract of `$design-research`, NOT another user-facing Skill.
The user may write only `$design-research 検索精度を改善して` or directly ask to research a method.
Do not require them to name phases, 5 candidates, diagrams, flags, paths or run IDs.
This contract does not authorize modifying application code, production, settings or approvals.

## What is automatic

- Resolve the selected project, requirements, prior workstream plan, completed runs, tests and constraints from existing local data. Never guess between equally plausible projects/prior results. Ask one focused question only when it changes scope or authorization.
- Choose the right workflow based on the user's *outcome*, not on having them pick a command. Show the chosen scope and next step succinctly.
- For method comparison, use baseline + about four genuinely different methods when useful; explain a smaller focused comparison. Read relevant primary work, keep falsification/ablation and appropriate controlled experiments. Default to the general `comparison` profile; choose `proposed-method` when a detailed Methods chapter is part of the requested outcome.
- Before research, read [effectiveness-evaluation.md](effectiveness-evaluation.md). Freeze purpose, primary final-outcome metrics, grading, controls, acceptance thresholds and measurement scope. Effectiveness/accuracy/performance requests require paired actual outputs and current receipts; missing primary measurements cannot be called completed validation. Design/literature work can complete with effects explicitly unmeasured and conditional conclusions. Negative/equal measured results are valid research.
- For full feature work, work from the requirements / user story and decompose uncertain core logic into questions. Execute or schedule in the current session only the work the user actually requested. A plan-only request stops at the plan.
- If completed prior findings and changed requirements/new evidence are present, use reassess rather than pretending to resume the old run. Previous results are historical evidence, not current measurements.

## Routing matrix (user asks for the goal, the Skill picks the workflow)

| User intent | Entry state / routing | Produce | Stop boundary |
| --- | --- | --- | --- |
| A new feature or system from story to architecture | `$upstream-new` / `$upstream-change` owns overall delivery; invoke design-research as a mandatory substep before choosing uncertain technical approaches | Clarified stories / requirements → core-logic research → architecture/design.md → verification plan | No unapproved implementation or deployment |
| Improve or investigate ONE named algorithm (e.g. ranker quality) | design-research: `research` (or `workstream` if a frozen workstream already exists) | Method comparison + PoC + illustrated report | Does not rewrite overall design.md by itself |
| Improve a requirement involving MULTIPLE core algorithms | `plan` then each `workstream` when research is requested → handoff to upstream integration | requirements-to-workstreams map, dependency-aware stages, several reports, integration conditions | Plan only if user explicitly asked only for a plan |
| Reconsider a completed study / update constraints | `reassess`, never `resume` | new independent report, comparison against previous, unrelated mechanism candidate | Preserve past report and note every changed assumption |
| Continue an interrupted run with identical conditions | `resume` | restored run and state | Reject changing frozen inputs |
| Show current results / what remains | `runs` / `status`, read-only | result, gaps, next recommended work | No experiment |
| Basic documentation typo or simple deterministic defect | no full design-research required unless the user requests it | simple edit/verification through the responsible workflow | Avoid pointless paper surveys |

## Core workflow states

```mermaid
flowchart TD
 S[Story / request] --> U[Upstream: clarify use cases and requirements]
 U --> D{Does a technical choice materially change the outcome?}
 D -->|No| A[Upstream: standard architecture design]
 D -->|Yes| P[Design Research: isolate core-logic questions]
 P --> R[Per-question method research and controlled PoC]
 R --> I[Upstream: integrate trade-offs and interfaces]
 I --> V[Upstream: architecture, framework selection, design.md, verification]
 A --> V
 V --> C{Later changed requirements or new evidence?}
 C -->|Yes| E[Design Research: reassess selected question(s)]
 E --> I
 C -->|No| F[Explicit review / approval, then separate implementation]
```

Figure interpretation: arrows are decision and hand-off boundaries, **not** proof of actual automatic execution or parallelism. `upstream` owns requirements and whole-system design. `design-research` owns method selection, isolated PoCs, research evidence, and the hand-off. The application source is not modified by research mode.

## What the user sees (not an internal action menu)

If the user writes `$design-research 検索精度を改善して`, use available context to decide whether this is a single known ranking algorithm or requires candidate generation + ranking + latency workstreams. Prefer a single scoped study if the user specifies just one algorithm. In unclear cases, inspect the project, then propose an evidence-based small scope without interrogating the user about CLI modes. Say what will be researched, then proceed through permitted local work.

- Don't ask the user to compose a long prompt prescribing five methods, diagrams, experiments, research profile, URLs or JSON file paths.
- Do not invoke separate `$design-research-plan` or `$design-research-reassess` Skill entries: those are legacy names. Read the internal reference and dispatch via `scripts/codex_interface.py`.
- If the user requests an *entire workflow*, continue from planning into executable workstreams and final handoff within the available session and authorization. Existing locks mean same-project jobs are serialized. Do **not** claim parallel execution merely because the dependency plan has parallel waves. Report any unexecuted steps.
- If the user explicitly requests **only** decomposition/planning, stop after generating and validating the plan, without executing studies.
- When the parent upstream workflow invokes design-research, return a compact handoff per workstream: requirement IDs, selected approach, input/output contract, measured and missing evidence, computing/runtime costs, findings vs assumptions, method report link, and suggested design.md integration. The parent performs system-level trade-off review.

## How to dispatch (internal implementation notes)

Find `<scripts>` relative to this reference (`../scripts`). Run the installed CLI; never rely on a pasted example as evidence.

1. `python3 <scripts>/workflow_overview.py --project <project>` to inspect the recorded workflow stage and available workstreams, then inspect runs/requirements as needed. The overview is read-only and does not certify content or execute jobs.
2. Standalone new research: `prepare research` then `run research --expect-dispatch <hash>`. Completed-study revision: `prepare reassess` then `run reassess --expect-dispatch <hash>`. Interrupted same-input run: `prepare resume` then `run resume --expect-dispatch <hash>`. Status-only: `runs` and read actual report.
3. Multi-topic requirement: use `scripts/research_workstreams.py` to create and validate a plan and use `codex_interface.py workstreams` for dependency waves. For a requested study, `prepare workstream` then `run workstream` with the exact dispatch hash. Respect prior-run identity, per-question prerequisites and the existing project lock.
4. Before every run, inspect the `prepare` output, user authorization and frozen inputs including `--report-profile` and `--evaluation-purpose`; reconcile any `needs_selection` state. Do not auto-pick the latest unrelated run. After running, read the actual produced report and status, primary metric table, paired input/expected/actual examples, gaps and limits. A structural contract does not certify semantic correctness.
5. No new daemon, service, settings modification, global hook, external mutation or automatic approval. A `ready` prepare does not mean a completed study.

## Acceptance and evaluation

A complete user-facing result should demonstrate that natural short prompts trigger the intended route, no obsolete shortcut is necessary, the workflow starts/stops at the requested boundary, all outputs declare their verification state, and the parent can integrate method findings into readable architecture diagrams. Codex selecting a Skill implicitly is model behavior and is not guaranteed; test explicit invocation, implicit short prompts and negative examples in an actual Codex environment as a separate validation step.
