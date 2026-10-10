from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PKG = Path(__file__).resolve().parents[1]
CLI = next(path for parent in Path(__file__).resolve().parents
           for path in (parent / "overlay/tools/design-research/skill/scripts/method_ideation.py",
                        parent / "tools/design-research/skill/scripts/method_ideation.py") if path.is_file())
SPEC = importlib.util.spec_from_file_location("method_ideation", CLI)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def complete():
    d = mod.skeleton("Improve quality and robustness of structured retrieval")
    d["task"] = "Find near-duplicate wafer patterns using an image embedding"
    d["baseline"] = {"name": "Euclidean embedding", "method": "Train the standard Euclidean contrastive embedding using fixed supervised splits and common retrieval evaluation.", "known_limitations": ["Minority categories have lower recall"]}
    d["primary_metric"] = "Exact-match Recall at top ten with paired dataset evaluation"
    d["hard_constraints"] = ["Keep the backbone and avoid exceeding 10% extra inference cost"]
    d["failure_modes"] = [dict(id="F1", status="hypothesis", symptom="Hard tree-structured subgroups appear closer than appropriate negatives", suspected_cause="Embedding distance does not preserve subgroup-specific geometry", evidence_locator="")]
    d["sources"] = [
        dict(id="S1", title="Synthetic paper one", url="https://example.org/p1", read_level="relevant_sections", locator="Section 3 and 4; Fig 2", mechanism="Uses a hypothetical hierarchical embedding objective.", study_id="study1"),
        dict(id="S2", title="Synthetic paper two", url="https://example.org/p2", read_level="full_text", locator="Sections 2–6 and Appendix B", mechanism="Uses a different hypothetical metric projection strategy.", study_id="study2"),
    ]
    for idx, family in enumerate(["repair", "replacement", "transfer", "composition"], 1):
        d["candidates"].append(dict(
            id=f"P{idx}", name=f"Candidate {idx}: {family}", family=family,
            failure_mode_ids=["F1"], source_ids=["S1"] if family == "transfer" else ["S2"],
            core_hypothesis=f"Introduce a {family}-specific intervention controlling the subgroup-aware neighborhood structure.",
            mechanistic_explanation=f"First identify the bottleneck in the present similarity metric, then use a {family}-specific mechanism in the representation or its loss. Its intervention changes the relationship between distances and subgroup membership. This remains a hypothesis.",
            transfer_mapping="Original principle maps distances to neighborhoods; target changes only the retrieval head.",
            mathematical_specification="Let z=f(x), h=g(z). Minimize L=L_metric+lambda*L_structure, with dimension and domain checked for h.",
            pseudocode="1. Compute embedding z=f(x)\n2. Transform h=g(z)\n3. Calculate supervised retrieval loss\n4. Optimize and evaluate unchanged splits.",
            integration_plan="Integrate a standalone adapter after the frozen feature backbone, keeping original checkpoints and evaluation logic.",
            resource_tradeoff="Extra adapter adds operations to the query path; measure latency and memory before recommending it.",
            expected_failure_regime="Without a meaningful subgroup tree the structural prior can add noise and lower retrieval accuracy.",
            prior_art_difference="Closest methods learn a static metric; this hypothetical candidate changes the subgroup-aware weighting mechanism.",
            novelty_status="plausibly_distinct", closest_prior_art_source_ids=["S1"], prior_art_queries=["hierarchical metric embeddings recent retrieval", "subgroup-aware weighting metric head"],
            assumptions=["Tree structure is present independently of training labels"],
            testable_predictions=["On low-tree-structure subsets the gain should shrink"],
            critical_objections=["The extra head might only add capacity, not new geometry"],
            revision_actions=["Add a parameter-matched Euclidean head as negative control"],
            discriminating_experiment=dict(
                comparison="Baseline vs parameter-matched head vs candidate on locked splits",
                controls="Match parameter count, embedding dimension, training budget and use fixed data partitions",
                primary_metric="Paired difference in Recall@10 across independent data units",
                acceptance_rule="Decide based on prespecified practically meaningful gain and uncertainty",
                negative_result_interpretation="Reject proposed geometry explanation if capacity-matched head performs equally well",
                budget="Pilot on small split, then predeclared training run count and compute quota")))
    d["selection"] = {"leading_candidate_id": "P3", "rationale": "Prefer cross-domain mechanism only conditionally: it targets the diagnosed failure and can be contrasted with a simple matched replacement.", "rejected_candidate_ids": ["P1", "P2", "P4"]}
    return d


class IdeationContractTests(unittest.TestCase):
    def test_draft_writes_without_claiming_novelty(self):
        with tempfile.TemporaryDirectory() as temp:
            data, report = Path(temp)/"ledger.json", Path(temp)/"report.md"
            x = subprocess.run([sys.executable, str(CLI), "init", "--out", str(data), "--question", "Check candidate method"], capture_output=True, text=True)
            self.assertEqual(x.returncode, 0, x.stderr)
            self.assertEqual(subprocess.run([sys.executable, str(CLI), "validate", str(data), "--strict"], capture_output=True).returncode, 1)
            self.assertEqual(subprocess.run([sys.executable, str(CLI), "render", str(data), "--out", str(report)], capture_output=True).returncode, 0)
            body = report.read_text()
            self.assertIn("暫定案", body)
            self.assertIn("未充足", body)
            self.assertNotIn("性能向上を確認", body)

    def test_full_design_passes_structural_validation(self):
        d=complete()
        self.assertEqual(mod.quality_issues(d, strict=True), [])
        rep=mod.render(d, mod.quality_issues(d, strict=True))
        self.assertIn("P3", rep)
        self.assertIn("未証明", rep)
        self.assertIn("parameter-matched", rep)
        self.assertIn("数式", rep)
        self.assertIn("全5方式", rep)
        self.assertIn("Baseline: Euclidean embedding", rep)

    def test_default_is_baseline_plus_four_alternatives(self):
        d = mod.skeleton("Check hypothesis selection and experimental comparison")
        self.assertEqual(d["comparison_plan"]["target_total"], 5)
        self.assertEqual(len(complete()["candidates"]), 4)

    def test_three_proposals_need_documented_exception(self):
        d = complete()
        d["candidates"].pop()
        d["selection"]["rejected_candidate_ids"] = ["P1", "P2"]
        self.assertTrue(any("target approximately 5" in issue for issue in mod.quality_issues(d, strict=True)))
        d["comparison_plan"]["exception_reason"] = (
            "Fixed compute budget and narrow method scope permit only three credible "
            "alternatives; adding more would be cosmetic."
        )
        self.assertEqual(mod.quality_issues(d, strict=True), [])

    def test_two_proposals_are_allowed_only_with_reason(self):
        d = complete()
        d["candidates"] = d["candidates"][:2]
        d["selection"] = {"leading_candidate_id": "P1", "rationale": "The repair candidate may isolate the suspected failure while the replacement provides a distinct alternative.", "rejected_candidate_ids": ["P2"]}
        d["comparison_plan"]["exception_reason"] = (
            "Very narrow existing module and fixed runtime permit two distinct proposals only."
        )
        self.assertEqual(mod.quality_issues(d, strict=True), [])

    def test_single_proposal_not_enough_even_with_exception(self):
        d = complete()
        d["candidates"] = d["candidates"][:1]
        d["comparison_plan"]["exception_reason"] = (
            "Limited project scope; cannot credibly evaluate a larger set of proposals."
        )
        self.assertTrue(any("at least two" in issue for issue in mod.quality_issues(d, strict=True)))

    def test_cli_init_sets_target_methods(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/"ledger.json"
            cmd = [sys.executable, str(CLI), "init", "--out", str(target), "--question", "Compare", "--target-methods", "5"]
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(target.read_text())["comparison_plan"]["target_total"], 5)

    def test_dangling_prior_art_source_is_rejected(self):
        d=complete(); d["candidates"][0]["source_ids"].append("MADE_UP")
        self.assertTrue(any("unknown source_id MADE_UP" in issue for issue in mod.quality_issues(d, strict=True)))

    def test_duplicate_ids_are_rejected(self):
        d=complete(); d["sources"][1]["id"]="S1"
        self.assertTrue(any("duplicate ID S1" in issue for issue in mod.quality_issues(d, strict=True)))

    def test_abstract_only_primary_sources_block_strict_quality(self):
        d=complete(); d["sources"][0]["read_level"]="abstract"
        self.assertTrue(any("independent primary" in issue for issue in mod.quality_issues(d, strict=True)))

    def test_novelty_claim_cannot_use_proven_novel(self):
        d=complete(); d["candidates"][0]["novelty_status"]="proven_novel"
        self.assertTrue(any("novelty_status" in issue for issue in mod.quality_issues(d, strict=True)))

    def test_rephrased_same_mechanism_does_not_count_as_diversity(self):
        d=complete(); d["candidates"][1]["core_hypothesis"]=d["candidates"][0]["core_hypothesis"]
        d["candidates"][1]["mechanistic_explanation"]=d["candidates"][0]["mechanistic_explanation"]
        self.assertTrue(any("rename is not diversity" in x for x in mod.quality_issues(d, strict=True)))

    def test_claimed_novelty_without_nearest_prior_art_blocks(self):
        d=complete(); d["candidates"][1]["closest_prior_art_source_ids"]=[]
        self.assertTrue(any("closest_prior_art" in x for x in mod.quality_issues(d, strict=True)))

    def test_missing_falsifier_or_critical_review_blocks_strict(self):
        d=complete(); d["candidates"][0]["discriminating_experiment"]["negative_result_interpretation"]=""
        d["candidates"][1]["critical_objections"]=[]
        errs=mod.quality_issues(d, strict=True)
        self.assertTrue(any("negative_result_interpretation" in x for x in errs))
        self.assertTrue(any("critical_objections" in x for x in errs))

    def test_cli_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            data, report=Path(temp)/"ledger.json",Path(temp)/"report.md"
            data.write_text(json.dumps(complete(),ensure_ascii=False),encoding="utf-8")
            self.assertEqual(subprocess.run([sys.executable,str(CLI),"validate",str(data),"--strict"],capture_output=True).returncode,0)
            self.assertEqual(subprocess.run([sys.executable,str(CLI),"render",str(data),"--out",str(report),"--strict"],capture_output=True).returncode,0)
            self.assertGreater(report.stat().st_size,1500)
            self.assertTrue(data.exists())


if __name__ == "__main__": unittest.main()
