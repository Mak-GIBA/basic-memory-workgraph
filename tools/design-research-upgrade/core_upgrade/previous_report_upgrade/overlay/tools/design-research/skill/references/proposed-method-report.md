# Required proposed-method chapter and explanatory figures

This is the report contract for `research --report-profile proposed-method` (the Skill explicitly selects this profile
for method-design/improvement requests; bare CLI calls retain the comparison default). `--target-methods 5` is the default and includes the baseline.
Comparison-only research can explicitly select `--report-profile comparison`; audit/run
and historical runs without a saved profile retain their existing reporting behavior.
The profile and target are persisted in the run configuration and reused on resume.

## Research and writing sequence

Do not stop after retrieving papers or ranking names. Diagnose the current method's failure,
separate symptoms from causal hypotheses, develop distinct candidate mechanisms, map borrowed
principles to target conditions, check closest prior art, formalize a minimal implementation,
challenge it with simpler explanations and revise it. Reason about five comparable methods
(baseline plus four alternatives) across different mechanism families. A documented smaller
shortlist is allowed by the existing ideation contract; do not change search/experiment limits.

The main report's **提案手法** chapter must read as a Methods section, not an internal agent
log. Begin with plain-language purpose and intuition, give a concrete input-to-output example,
then explain the architecture and each component. Define symbols before formulas, explain what
each equation does, and distinguish preparation/training from inference/runtime. State exact
interfaces, the baseline difference, cost, imported principles, prior-art difference, objections,
revisions, failure conditions and the experiment that would refute each important mechanism.

Explain enough to reconstruct the method. Do not force decorative mathematics for a rule-based
algorithm: a sufficiently specified pseudocode algorithm plus `formalism_note` is valid.
If mathematics is supplied, give symbol definitions, shapes/ranges and equation explanations.
Avoid calling expected improvements measured facts, or calling the design focus a proven winner.
A baseline can still be the final recommendation after unfavorable or inconclusive results.

## Data location: one connected dossier

Put the entire old `method_ideation.py` ledger in `dossier_json.method_ideas`.
The baseline now includes its actual dossier candidate `id`.
`method_ideas.candidates` contains the non-baseline methods with exactly the same IDs and names
as `dossier.candidates`. Source IDs, URLs/local paths and reading levels must match the dossier;
source access/experiment validation in the existing harness still applies independently.

Add `presentation` to the candidate named by `selection.leading_candidate_id`.
This is the method selected for detailed explanation, not automatically the empirically best
method. Explain any difference from `dossier.decision.candidate_id` in `selection_note`.
Other candidates retain their full old ideation records: mechanism, mathematical/algorithmic
specification, integration, nearest prior art, falsifying experiment, objections and revisions.

```json
{
  "presentation": {
    "overview": "Plain-language goal, motivating failure and central idea",
    "worked_example": "A concrete input-to-output walkthrough; label hypothetical examples",
    "training": "Training/preparation steps and what is fixed; explicitly say when no learning occurs",
    "inference": "Inference/runtime steps and output; no train/test leakage",
    "evidence_scope": "What was actually checked; use 未測定 for unrun experiments and disclose unavailable visual inspection",
    "selection_note": "Why this design is explained, and how it relates to the actual recommendation",
    "equation_explanation": "Interpret the mathematical specification in ordinary language",
    "formalism_note": "Required instead when no mathematical formulation applies",
    "symbols": [{"symbol":"x", "definition":"Input observation", "shape":"State the actual shape/type/domain"}],
    "components": [{
      "id":"M1", "name":"Concrete component name", "inputs":"Actual inputs and shapes",
      "outputs":"Actual outputs and shapes", "operation":"Step-by-step mechanism",
      "rationale":"Why this targets the diagnosed failure", "baseline_difference":"What changes and stays fixed",
      "cost":"Time/memory/parameter implications, labeled measured or analytical"
    }],
    "differences":[{"aspect":"Comparison axis", "baseline":"Current behavior", "proposal":"Proposed behavior", "tradeoff":"Cost, assumption or failure condition"}],
    "verification":[{
      "hypothesis":"A falsifiable mechanism claim", "component_ids":["M1"],
      "experiment_id":"E1", "alternative_explanation":"A simpler competing explanation",
      "rejection_condition":"What observation would refute or change this hypothesis"
    }],
    "figures": []
  }
}
```

The object above is a schema illustration, not a completed design. `figures` must be populated
with actual design definitions, and `experiment_id` must reference `dossier.experiments`.
Only the selected design needs the complete presentation object; every comparison candidate
still needs a substantive design record. The validator checks presence/types/links, not the
truth or sufficiency of scientific reasoning. The reviewer must inspect the actual content.

## Figures: actual inline SVG plus explanatory prose

Provide 3–6 figures covering all three kinds:
`architecture`, `module_detail`, `baseline_comparison`.

Architecture shows the input-to-output flow. Module detail expands the proposed operation
rather than repeating the same boxes. Baseline comparison places both methods side by side
and explicitly marks unchanged, added and modified steps. A caption identifies what is shown;
`explanation` says how to read it and why the depicted difference matters. Use consistent IDs,
names, symbols and shapes between text, formulas, pseudocode and diagrams.

```json
{
  "id":"F1", "kind":"architecture", "title":"Architecture of the proposed method",
  "caption":"What is shown and which conditions apply",
  "alt_text":"An accessible textual account of the flow",
  "explanation":"How to read the arrows, identify the proposed part, and connect it to the mechanism",
  "component_ids":["M1"],
  "nodes":[
    {"id":"N1", "label":"Input", "detail":"Actual input data", "component_id":"", "lane":"shared", "change":"unchanged"},
    {"id":"N2", "label":"New transformation", "detail":"Actual operation, not just a slogan", "component_id":"M1", "lane":"proposal", "change":"added"}
  ],
  "edges":[{"from":"N1", "to":"N2", "label":"Transferred data and shape", "kind":"flow"}]
}
```

Use 2–16 nodes and 1–28 edges per figure, at most four boxes on one parallel rank. The solid
`flow` edges form a directed acyclic graph; deliberate feedback is explicitly `feedback` and
rendered dashed. All arrows have meaningful labels; no orphan boxes or dangling IDs.
Node `lane` is `baseline`, `proposal` or `shared`; `change` is `unchanged`, `added` or `modified`.
Node `component_id` links the described component; only boundaries/baseline-only boxes may use
an empty string. The figure's `component_ids` must equal the component IDs appearing in nodes.
Baseline-comparison figures require both baseline and proposal lanes. Detail figures must expose
an added/modified operation. Keep node labels at most 80 characters and details at most 160;
put the fuller explanation in prose rather than shrinking the text.

Do not provide raw SVG, embedded script, shell commands, image URLs or preclaimed rendered
artifacts. The parent generates SVG from these graph records using the standard library,
escapes XML, writes editable JSON next to each figure, and embeds the actual SVGs inline in the
report. No paid image service, network call, new package or model is needed for diagram rendering.
The graph format supports explanatory process diagrams, not every possible scientific plot.
Embedding-space plots, experimental curves and specialized mathematical figures remain separate
artifact-producing experiments and must use real data/receipts where applicable.

## Review, persistence and failure states

The parent generates an immutable, content-addressed preview after the producer response and
before the reviewer. The reviewer receives `method_report_preview`. Inspect it when the host
supports images; check readability, clipping, arrow meaning and text/figure agreement. If that
inspection is unavailable, say so. Valid XML and file existence are not a visual quality test.

Final figures are stored below the current run's `method-figures/<design-hash>/` directory.
An existing artifact with different bytes, a symlink or an unsafe path is refused. New revisions
get new content hashes, so old figure files are not silently replaced. The existing report
archiver rebases the figure and source-definition links in the run snapshot.

The harness rejects a structurally incomplete Methods chapter rather than declaring
`research_complete`. Early/stopped runs still contain **提案手法**, explicitly marked 未完成.
This does not require a positive experimental result. Planned tests stay planned; conceptual
figures never count as successful test receipts. Review/gate rules for empirical claims are
unchanged. No install-time network, remote mutation, auto-migration, model-setting change,
extra search budget or recursive child harness is introduced.

## Offline inspection commands

```bash
python3 <skill-dir>/scripts/proposal_report.py validate evidence.json --target-methods 5
python3 <skill-dir>/scripts/proposal_report.py render evidence.json --out new-report.md --strict
```

These commands are for inspection, not a replacement for the requested harness run. The render
command refuses to overwrite an existing report. It reads a dossier of at most 5 MB and cannot
generate ideas, verify actual literature access or establish scientific merit on its own.
