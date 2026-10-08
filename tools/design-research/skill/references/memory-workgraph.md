# Detailed verification and experiment records in Workgraph

Use the existing Basic Memory Workgraph installed by this repository's `install_basic_memory_workgraph.sh`. This is optional retention by the outer Design Research skill after reading actual run artifacts; the Bash harness and `DR_GAN_CHILD=1` roles do not write Memory.

## Select useful records

A per-run save request is not required for useful verification/experiment records when existing settings and write permissions allow saving. A record can be useful within the same project: it changes a later comparison/decision, prevents repeating a failed approach, preserves non-obvious reproduction conditions or supports resuming an investigation. Identify that concrete use before saving. Explicit save requests determine the requested content/scope.

Retain successful and failed executions with useful evidence. Routine passing checks, completion summaries, unsupported impressions and every run by default are not sufficient. Do not turn a planned/unexecuted experiment into an executed result. Detailed project records use Artifact notes; promotion to Rule/Workflow/Validation separately requires Workgraph's existing admission criteria. This permission is scoped to Design Research verification/experiment records, not a change to Workgraph's general policy.

## Save through the configured project

1. Confirm the active mode, current write permissions, installed Workgraph policy and settings. Respect Plan/read-only, explicit no-save instructions and `auto=off` for automatic saving. Resolve an existing Basic Memory project from the user's specified mapping, the host's configured project context or the installed `basic-memory.json` `primaryProject`; do not assume a fixed home, project or server. Discover available Memory tools rather than inventing tool names. Do not install Workgraph, create a project or change hooks/settings to enable saving.
2. Read `.internal/status.json` (legacy: root `status.json`), its `state_path`, the actual execution receipt and relevant raw results. Match run ID, evidence ID, iteration and source fingerprint. Use that run's preserved `reports/` and registered evidence paths. Source-access receipts alone do not establish that a paper was understood or a test passed.
3. Use `artifacts/design-research/<slug>/<run-id>/<evidence-id>.md` within the selected Memory project, one note per selected verification/experiment execution. Search for the same run/evidence before writing and read promising matches. If the same evidence and interpretation already exist, skip the write. Add only material new interpretation/conditions to an existing note; keep distinct executions and conflicting results separate. If lookup fails, skip automatic saving rather than risk duplicates.
4. Write the detailed record below using the available Basic Memory tool and existing Artifact schema (`type: artifact`, `kind: report`). Sanitize secrets, personal/test data and unnecessary confidential details before writing; preserve enough neutral context to interpret the result. Default to `sharing_scope: private`, `training_use: excluded`, `privacy_review: pending`. Keep long raw logs, data, generated code and paper texts in their existing artifacts; link them rather than importing them into Memory.
5. Read back the saved note once and verify content, actual evidence references and metadata. Do not create companion Case/Rule/Workflow notes or relations solely to build a graph. Apply separate admission rules to any independently useful generalized knowledge.
6. In the final artifact navigation table show the actual Memory project, note path/returned reference, usefulness and save state. Distinguish saved, unchanged duplicate, not selected, unavailable and failed; never present a proposed path as a saved note. Memory failure does not change the harness outcome or discard local reports. Saving is a skill action, not guaranteed by a bare terminal harness invocation.

## Required detail per selected execution

| Content | What to record |
|---|---|
| Purpose and reuse | Project/context in safe terms, question/hypothesis, contribution to the main goal, the future decision/reproduction/resume this record helps |
| Identity | Slug, run ID, evidence ID, iteration, execution time, target/source fingerprint and applicable code/model/data versions |
| Conditions | Inputs/evaluation data and their safe identifiers, baseline/candidates, controlled variables, environment, resource limits and relevant dependencies |
| Evaluation | Metrics, expected results/acceptance thresholds and their basis; mark unknown values explicitly |
| Reproduction | Actual command, needed safe setup, input/artifact paths and receipt hash where available |
| Results | Actual values and exit status, pass/fail/unknown, timeout/truncation, important output/error excerpts, baseline differences under common conditions |
| Interpretation | What the execution establishes, what remains inferred/unknown, failure/root-cause evidence, limitations and conditions requiring recheck |
| Evidence | Actual receipt, stdout/stderr, saved output and run-specific report links; do not label a test pass as human adoption |

Copy verified values from artifacts and distinguish them from explanations. If a field is unavailable, say so; do not invent detail to fill the table. Existing Memory is a lead to revalidate against the current question, source/data/model version and conditions, not proof that an old result still applies.
