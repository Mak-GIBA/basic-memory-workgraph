"""Small explicit integration hooks for the existing research harness."""
from __future__ import annotations

from proposal_report import method_required, validation_issues


def role_instructions(role, state):
    if not method_required(state):
        return ""
    count = state.get("config", {}).get("target_methods", 5)
    common = f"""
PROPOSED-METHOD REPORT CONTRACT:
This run compares approximately {count} methods overall, including the current/minimal baseline.
Do not count ablations, aliases or hyperparameter variants as new method families.
Keep existing search, experiment, sandbox and budget limits. A smaller shortlist needs a
substantive comparison_plan.exception_reason; never fabricate sources or a superior result.
Read skill_directory/references/proposed-method-report.md and method-ideation.md.
The complete dossier_json must carry method_ideas: the five-method design ledger, including
presentation on its leading candidate. The parent renders the chapter and real SVG diagrams;
children must not edit report.md or write diagram files directly. Design figures are not
experimental evidence. Dossier IDs, source identities and experiment IDs must agree.
Explain the method in this order: goal and intuition, worked input-to-output example,
overall architecture, modules, symbols/equations or pseudocode, preparation/training versus
inference, baseline differences, imported principles and prior-art differences, integration,
complexity, objections/revisions and hypothesis-to-experiment mapping. Do not substitute
bullet labels, TODOs, literature summaries or unexplained formulas for an actual explanation.
The report needs architecture, module_detail and baseline_comparison figures as bounded
node/edge definitions, each with caption, alternative text, component IDs and explanatory
prose. Inspect the actual preview when supported; a valid SVG is not proof of readability.
Keep the final recommendation separate from the method being explained. It may be provisional
or rejected; do not claim a winner merely because a candidate was chosen for detailed design.
"""
    if role == "planner":
        return common + "\nFreeze an acceptance criterion covering the proposed-method chapter and fair comparisons.\n"
    if role == "producer":
        return common + "\nDevelop distinct mechanisms, review their closest prior art and revise against objections before selecting a design focus. Describe every candidate, not just five names. Return the complete method_ideas in dossier_json.\n"
    if role == "reviewer":
        return common + "\nRead method_report_preview when available. Check diagram/text agreement, complete interfaces, symbol meanings, training/inference paths and whether the baseline diff isolates the mechanism. Fix dossier_json, preserving experiment statuses and authentic evidence. If visual inspection cannot be performed, explicitly record that limitation in evidence_scope.\n"
    return ""


def additional_gate_reasons(state):
    if not method_required(state):
        return []
    return ["Proposed-method report: " + item for item in validation_issues(
        state.get("dossier"), target_methods=state["config"].get("target_methods", 5),
        allow_single_proposal=state.get("execution_contract_version") == 2)]
