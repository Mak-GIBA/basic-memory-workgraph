## Proposed-method research and reporting

For proposed-method engineering, use `research --report-profile proposed-method` (required for method-design/improvement requests) with `--target-methods 5`. Compare approximately five methods including the baseline, normally across at least three mechanism families. Keep the existing experiment/search budgets. A substantive documented exception is allowed; aliases and ablations do not count as new methods.

Read `references/method-ideation.md` and `references/proposed-method-report.md`. Diagnose a failure, develop distinct mechanisms, inspect closest prior work, formalize interfaces/equations/algorithms, challenge and revise the candidates, and plan discriminating experiments. A list of five names is insufficient.

The producer and reviewer return the complete `method_ideas` object inside `dossier_json`, not a separate unconnected document. The leading candidate has a `presentation` with explanation and structured figures. The parent generates a mandatory `## 提案手法` chapter, real embedded SVGs and editable graph definitions in the canonical report. Do not append to a published report by hand. Review the generated preview where supported; explicitly state when visual inspection was unavailable.

The chapter must explain intuition, a worked example, interfaces, component mechanisms, symbols, equations or pseudocode, training/preparation versus inference, baseline differences, imported principles, complexity, objections/revisions and falsification experiments. Missing explanations, figures or inconsistent IDs cannot pass the structural gate. Structural readiness never establishes novelty, efficacy or human approval. A hypothesis-only proposal must state 未測定.

Use `--report-profile comparison` only for comparison-only research that does not develop a proposal. Audit/run and resumes of older runs without a profile preserve the existing contract.

The canonical Skill invocation above explicitly selects this profile. A bare CLI `research` command defaults to comparison for backward compatibility. Do not omit the profile when the user requests a proposed-method report.
