# Purpose, primary outcomes and paired examples (2.4+ new runs)

Read this before planning an evaluation. This is a general contract for retrieval,
algorithms, agents, technology selection and design research; it is not MCP-specific.
Keep the user's question, requested scope and available budget decisive.

## Choose and freeze the purpose

`--evaluation-purpose auto` lets the planner classify the actual request. Explicit
`effectiveness`, `design` or `literature` is binding. An effectiveness/accuracy/speed
question needs final-outcome measurements; never downgrade it to avoid experiments.
Design/literature work can complete with effects explicitly unmeasured, a conditional
decision, actual sources and labeled illustrative examples. Do not claim a negative
effect just because evidence could not be collected.

The planner returns `evaluation_json` as a JSON string with these fields:

```json
{
  "purpose": "effectiveness",
  "baseline_id": "A",
  "candidate_ids": ["A", "B"],
  "tasks": [{"id": "boundary", "input": 1701, "expected": false}],
  "dataset": "Two boundary inputs for this narrow decision; not representative population data",
  "controls": ["Same task input, expected output, runtime/model, permissions and budgets"],
  "budget": "One local run; metric scope excludes authoring/model time unless measured",
  "limitations": "Small deterministic sample, no statistical or universal inference",
  "metrics": [{
    "id": "accuracy", "criterion_id": "R1", "primary": true,
    "kind": "exact_match", "unit": "fraction", "direction": "higher",
    "aggregation": "mean", "acceptance_delta": 0.1,
    "grading": "Compare the actual final output with the independently specified expected output",
    "outcome_scope": "final_outcome"
  }]
}
```

This is an illustrative contract, not measured evidence. Set the dataset, metric,
grading and threshold for the specific task; **0.1 is not a default policy**.
Effectiveness requires at least one primary metric mapped to a required runtime
criterion. Negative/equal measured results may complete research. A metric threshold
determines the recommendation, not whether the experiment exists.

Freeze `tasks` with IDs, common inputs and expected final outcomes before execution.
For larger datasets use `task_manifest`, a non-secret project-relative JSON file
containing the same task array (maximum 5 MB / 10,000 tasks), protected by the source
fingerprint. The parent rejects changed inputs/labels, omitted tasks and extra tasks.

Supported graders: `exact_match` (whole JSON final outcome), `absolute_error`
(finite numeric final outputs), `scalar` (domain-specific measured score in `values`).
All aggregate paired trials by mean. Use higher/lower to declare improvement direction;
`acceptance_delta` is the required signed improvement. For scalar grades preserve
`grading_evidence` explaining the computation and inspect the actual grading code.
The harness checks arithmetic/provenance; the reviewer checks metric relevance,
dataset adequacy, matching conditions, failure handling and interpretation.

Examples: retrieval should grade relevant answers/results against labels; a code tool
should grade final code with functional checks; a reasoning aid should compare actual
task answers with/without it under the same model/budget. Echoed thoughts, a valid tool
response, bytes returned or a document being found do not measure these outcomes.
Declare latency's scope (tool call vs end-to-end, setup, retries and model time).
If unavailable, list the gap; token estimates do not establish billed cost savings.

## Split production and execute

The parent saves a validated `producer-design` result before `producer-assets` builds
code. No checks are executed by either child. The parent archives declared files,
executes at most three local experiments and owns immutable receipts/results.

Export paired results as a declared JSON `artifact_paths` file:

```json
{
  "contract_sha256": "copy the actual supplied frozen evaluation_contract_sha256",
  "tasks": [{"id": "boundary", "input": 1701, "expected": false}],
  "trials": [
    {"task_id": "boundary", "trial_id": "1", "candidate_id": "A", "output": true},
    {"task_id": "boundary", "trial_id": "1", "candidate_id": "B", "output": false}
  ]
}
```

This is a format example. Return outputs actually produced by running the methods,
not constants selected to obtain desired grades. For scalar metrics each trial also
has `values: {"metric-id": actual_number}` and nonempty `grading_evidence`. Keep shared
inputs and expected outcomes identical across candidates. Use distinct task IDs for
different tasks, trial IDs for repeats. Retain failed final outcomes as output values;
an experiment should exit zero after recording a negative finding, but execution
errors/timeouts cannot become successful measurements. Preserve sample counts and
all failures. Inputs/tasks must be unique across exported result files.

Reviewer dossier adds `evaluation_result: {"contract_sha256": "actual hash",
"artifact_paths": ["actual workspace-relative parent-exported results.json path"]}`.
These paths point to result artifacts, while dossier `experiments[].artifacts` still
point to successful parent experiment **receipts** under the existing ledger contract.
The parent verifies hash, current iteration/source, exporting receipt, pair coverage,
and recalculates grades. It generates the result table and concrete input/expected/
baseline/candidate examples directly from those artifacts, retaining a failure example
when available. The reviewer explains why the difference matters to the user's goal.
An unmeasured primary effect blocks effectiveness completion; design/literature may
complete with provisional/deferred conclusions and an explicit measurement gap.

## Recovery and limits

The parent grades and saves valid paired results immediately after experiments,
before asking for independent review. If review stops, measured values and actual
examples remain visible with review marked incomplete; that alone cannot establish
research completion or adoption. Effectiveness review must bind the result artifacts.

The role/check timeout remains 1800 seconds unless explicitly changed. Role receipts
record elapsed time, exit code, timeout/truncation and output hashes, so a stopped model
role can be distinguished from an experiment failure. A single format/locator/history
repair is allowed within the remaining original role budget, never a timeout retry or
weakened evidence gate. Source citations must exist and span at most 200 line intervals.
Only the same run's previous issue ledger permits `resolved`; old run findings are
historical inputs, not locally resolved issues.

Resume requires unchanged source, evidence, frozen purpose/metrics and checkpoints.
Saved comparison/code stages are reused. A partial check uses a new iteration to keep
old receipts immutable, reuses saved production stages and runs checks afresh. New
review issues can trigger new production in a later iteration. Interrupted source
fixing remains refused. Legacy runs without this extension keep the old contract.

Preflight checks executables and dependency layout before model work for explicit
checks and again after planning. Dependency directory symlinks used by backend copies
are unsupported; use a real local directory or system runtime. The preflight does not
execute checks, install dependencies or bypass the sandbox. `comparison` is the
general interface default; select `proposed-method` when a proposed Methods chapter
and its additional diagrams fit the requested outcome. Prepare freezes both profile
and purpose in its dispatch hash; changing them invalidates the lease.
