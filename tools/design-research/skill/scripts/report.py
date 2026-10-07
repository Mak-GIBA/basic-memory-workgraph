"""Readable reports are rendered by the parent from validated review structures."""
from __future__ import annotations

import collections
import json
import os
from pathlib import Path
import re

from runtime import atomic_json, now, regular_path


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def evidence_links(ids, state):
    lines = []
    for key in ids:
        record = state["evidence"][key]
        lines.append(f"- [{key}: {record['description']}]({record['path']}) "
                     f"（{record['kind']}、反復{record['iteration']}、"
                     f"SHA-256 {record['sha256']}）")
        if record["kind"] in {"test", "experiment"}:
            receipt = json.loads((Path(state["workspace"]) / record["path"]).read_text("utf-8"))
            for name, output in receipt["outputs"].items():
                lines.append(f"  - [{name}]({output['path']})")
            for output in receipt.get("artifacts", []):
                lines.append(f"  - [生成結果]({output['path']})")
                if Path(output["path"]).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif"}:
                    lines += ["", f"![実行時に保存した結果]({output['path']})", ""]
    return lines


def write(root, name, lines):
    path = regular_path(Path(root) / name)
    path.write_text("\n".join(lines) + "\n", "utf-8")


def publish(state, workspace, run_dir):
    summary = {"run_id": state["run_id"], "status": state["status"],
               "phase": state["phase"], "iteration": state["iteration"],
               "reason": state.get("reason", ""), "updated_at": now(),
               "domain": state.get("plan", {}).get("domain", "unknown"),
               "source_head": state["expected_source"]["head"],
               "state_path": (run_dir / "state.json").relative_to(workspace).as_posix()}
    atomic_json(workspace / "status.json", summary)
    if not state.get("review"):
        return
    state["workspace"] = str(workspace)
    review, plan = state["review"], state["plan"]
    unresolved = [r for r in review["issues"] if r["status"] != "resolved"]
    unresolved.sort(key=lambda r: (["Critical", "High", "Medium", "Low"].index(r["severity"]), r["id"]))
    stats = collections.Counter(r["severity"] for r in unresolved)
    lines = ["# Design Research Review", "", f"実行ID: {state['run_id']} / **{state['status']}**",
             f"対象: {plan['domain']} / 確認日時: {now()}",
             f"目的: {plan['goal']}", f"基準案: {plan['baseline']}",
             f"対象の版: {state['expected_source']['head'] or 'Git管理なし'}。"
             "未コミット内容を含むソース指紋は実行状態に保存。", "",
             f"最終レビュー: 反復{state.get('history', [{}])[-1].get('iteration', state['iteration'])}。"
             "中断した修正の結果は、再検証されるまで未確認です。", "",
             "## Executive Summary", "", state.get("reason", ""), "",
             "未解消: " + " / ".join(f"{key} {stats[key]}件" for key in
                                     ["Critical", "High", "Medium", "Low"]), "",
             "これはAIによる評価と記録した検証の結果です。人間のユーザーテスト、"
             "本番運用の確認、方式の普遍的な有効性は、この実行からは判断できません。", ""]
    lines += [f"- {r['id']}: {r['title']}（{r['severity']}）" for r in unresolved[:10]]
    lines += ["", "## Reviewed Checks", "", "| 対象 | 必須 | 結果 | 根拠・限界 |",
              "|---|---|---|---|"]
    checked = {row["check_id"]: row for row in review["checks"]}
    for row in plan["criteria"]:
        result = checked[row["id"]]
        lines.append(f"| {cell(row['id'] + ': ' + row['title'])} | "
                     f"{'Yes' if row['required'] else 'No'} | {result['result']} | "
                     f"{cell(result['reason'])} |")
    for row in review["checks"]:
        lines += ["", f"### {row['check_id']}", ""]
        lines += evidence_links(row["evidence_ids"], state)
    for label, levels in [("High Priority Issues", ["Critical", "High"]),
                          ("Medium Priority Issues", ["Medium"]), ("Low Priority / Polish", ["Low"])]:
        lines += ["", "## " + label, ""]
        selected = [r for r in unresolved if r["severity"] in levels]
        if not selected:
            lines.append("未解消の指摘なし。未確認事項は検証結果と停止理由を参照。")
        for row in selected:
            lines += ["", f"### {row['id']}: {row['title']}", "",
                      f"**Severity:** {row['severity']}", f"**Target:** {row['target']}",
                      f"**Status:** {row['status']}", "",
                      "**Action / Reproduction:**  \n" + row["action"], "",
                      "**Expected:**  \n" + row["expected"], "",
                      "**Actual / Problem:**  \n" + row["actual"], "",
                      "**Why this matters:**  \n" + row["why"], "",
                      "**Recommended improvement:**  \n" + row["improvement"], "",
                      "**Evidence:**", ""]
            lines += evidence_links(row["evidence_ids"], state)
    lines += ["", "## Complexity / Simplicity", "", review["complexity_reason"],
              f"評価: {'許容' if review['complexity_ok'] else '見直しが必要'}", "",
              "## Recommended Fix Order", "", "影響が大きい順。目的に必要な最小の変更を優先。", ""]
    lines += [f"{index}. {r['id']}: {r['title']} → {r['improvement']}"
              for index, r in enumerate(unresolved, 1)]
    lines += ["", "## Limits / Recovery", "", state.get("reason", ""),
              "中断した修正は差分を保持し、新しいaudit/runで再検証します。"
              "pending_reviewの再開は同じ証拠を確認して評価から続けます。", ""]
    write(workspace, "review.md", lines)
    fixes = ["# Fix and Verification Report", "", f"実行ID: {state['run_id']} / **{state['status']}**",
             "修正担当の申告と、別の評価実行による再確認を分けて記録します。", ""]
    for fix in state.get("fixes", []):
        fixes += [f"## 反復 {fix['iteration']}", "", fix["reason"], "",
                  "変更ファイル: " + ", ".join(fix["actual_changed_files"]), ""]
        for item in fix["complexity_changes"]:
            fixes += [f"- 変更: {item['change']}", f"  - より単純な案: {item['simpler_alternative']}",
                      f"  - 採用理由: {item['reason']}"]
    for row in review["issues"]:
        if row["status"] != "resolved":
            continue
        fixes += ["", f"## {row['id']}: {row['title']}", "", "変更前の証拠:", ""]
        old = next((issue for history in state.get("history", []) for issue in history["review"]["issues"]
                    if issue["id"] == row["id"] and issue["status"] != "resolved"), None)
        if old:
            fixes += evidence_links(old["evidence_ids"], state)
        fixes += ["", "変更後の独立レビュー:", ""]
        fixes += evidence_links(row["evidence_ids"], state)
    fixes += ["", "残る確認:", "", state.get("reason", ""), ""]
    write(workspace, "fix-report.md", fixes)
    references = ["# Reference Implementations", "", f"実行ID: {state['run_id']}",
                  "公開されている仕様・研究・実装から確認した範囲を記録します。", ""]
    for item in review["reference_implementations"]:
        references += [f"## {item['name']}", "", f"[参照先]({item['url']})", "",
                       "- 良い設計: " + item["strength"],
                       "- この対象への適用: " + item["application"],
                       "- 適用条件・未確認: " + item["limitations"], ""]
        for key in item["source_ids"]:
            record = state["sources"][key]
            references += [f"- {key}: {record['source']['locator']} / {record['status']}",
                           *evidence_links([record["evidence_id"]], state)]
    if not review["reference_implementations"]:
        references.append("今回の判断に必要な模範実装は記録されていません。調査漏れと不要な比較を区別してください。")
    write(workspace, "reference-implementations.md", references)
    if state.get("dossier"):
        dossier = state["dossier"]
        atomic_json(workspace / "evidence.json", dossier)
        report = ["# Design Research", "", dossier["question"], "",
                  "## Scope / Constraints", "", dossier["scope"], ""]
        report += [f"- {r['kind']}: {r['text']}" for r in dossier["constraints"]]
        report += ["", "## Candidate Comparison", "",
                   "| 方式 | 基準案 | 評価軸 | 結果 | 根拠の種類 |", "|---|---|---|---|---|"]
        candidates = {r["id"]: r for r in dossier["candidates"]}
        for row in dossier["comparison"]:
            candidate = candidates[row["candidate_id"]]
            report.append(f"| {cell(candidate['name'])} | {'Yes' if candidate['baseline'] else 'No'} | "
                          f"{cell(row['criterion'])} | {cell(row['finding'])} | {row['basis']} |")
        report += ["", "## Claims and Evidence", ""]
        sources = {r["id"]: r for r in dossier["sources"]}
        for claim in dossier["claims"]:
            report += [f"### {claim['id']} ({claim['status']})", "", claim["statement"],
                       "条件: " + claim["context"], "限界: " + "; ".join(claim["limitations"]), ""]
            for evidence in claim["evidence"]:
                source = sources[evidence["source_id"]]
                link = source.get("local_path") or source.get("url")
                report.append(f"- [{source['id']}: {source['title']}]({link}) / "
                              f"{evidence['relation']} / {evidence['locator']}")
        decision = dossier["decision"]
        report += ["", "## Conditional Recommendation", "", f"状態: **{decision['status']}**",
                   f"候補: {decision['candidate_id']}", decision["rationale"], "",
                   "未確認: " + "; ".join(decision["unresolved"]),
                   "見直す条件: " + "; ".join(decision["revisit_when"]), "",
                   "## Experiments", ""]
        for experiment in dossier["experiments"]:
            report += [f"### {experiment['id']} ({experiment['status']})", "",
                       experiment["hypothesis"], "統制条件: " + "; ".join(experiment["controls"]),
                       "評価指標: " + "; ".join(experiment["metrics"]),
                       "合格条件: " + experiment["acceptance"], ""]
            report += [f"- [実行証拠]({path})" for path in experiment["artifacts"]]
        report += ["", "[検証と指摘](review.md) · [修正と再検証](fix-report.md) · "
                   "[参考実装](reference-implementations.md)", ""]
        write(workspace, "design-research.md", report)
        write(workspace, "decision.md", ["# Proposed Decision", "", decision["rationale"], "",
              "状態: " + decision["status"], "採用候補: " + str(decision["candidate_id"]),
              "未確認: " + "; ".join(decision["unresolved"]),
              "再検討: " + "; ".join(decision["revisit_when"]),
              "", "ハーネスによる完了は、人間による採用承認を意味しません。"])
    atomic_json(workspace / "research-log.json", {
        "schema_version": 1, "run_id": state["run_id"], "discovery": state.get("discovery", []),
        "sources": state["sources"], "executions": state.get("executions", []),
        "status": state["status"], "stop_reason": state.get("reason", ""),
        "source_fingerprint": state["expected_source"],
        "limits": "AI independent executions, not human acceptance or a universal benchmark"})
    archive = regular_path(run_dir / "reports")
    archive.mkdir(exist_ok=True)
    for name in ("design-research.md", "review.md", "fix-report.md", "reference-implementations.md",
                 "evidence.json", "decision.md", "research-log.json", "status.json"):
        source = workspace / name
        if source.is_file() and not source.is_symlink():
            if source.suffix == ".md":
                def rebase(match):
                    target = match.group(1)
                    if target.startswith(("http:", "https:", "#")) or target in {
                            "review.md", "fix-report.md", "reference-implementations.md"}:
                        return match.group(0)
                    return "](" + os.path.relpath(workspace / target, archive) + ")"
                (archive / name).write_text(re.sub(r"\]\(([^)]+)\)", rebase,
                                                   source.read_text("utf-8")), "utf-8")
            else:
                (archive / name).write_bytes(source.read_bytes())
