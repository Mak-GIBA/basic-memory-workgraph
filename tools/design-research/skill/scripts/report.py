"""Readable reports are rendered by the parent from validated review structures."""
from __future__ import annotations

import collections
import json
import os
from pathlib import Path
import re

from runtime import atomic_bytes, atomic_json, now, regular_path
from layout import MARKER, compact, record_path


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def evidence_links(ids, state, verbose=True):
    lines = []
    for key in ids:
        record = state["evidence"][key]
        suffix = (f"（{record['kind']}、反復{record['iteration']}、SHA-256 {record['sha256']}）" if verbose else '')
        lines.append(f"- [{key}: {record['description']}]({record['path']}) {suffix}".rstrip())
        if record["kind"] in {"test", "experiment"}:
            receipt = json.loads((Path(state["workspace"]) / record["path"]).read_text("utf-8"))
            if verbose:
                for name, output in receipt["outputs"].items():
                    lines.append(f"  - [{name}]({output['path']})")
            for output in receipt.get("artifacts", []):
                lines.append(f"  - [生成結果]({output['path']})")
                if Path(output["path"]).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif"}:
                    lines += ["", f"![実行時に保存した結果]({output['path']})", ""]
    return lines


def write(root, name, lines):
    path = regular_path(Path(root) / name)
    atomic_bytes(path,("\n".join(lines) + "\n").encode('utf-8'))


def publish(state, workspace, run_dir):
    if not compact(workspace):
        return publish_legacy(state, workspace, run_dir)
    from runtime import Blocked
    target = regular_path(workspace/'report.md')
    state['workspace'] = str(workspace)
    summary = {"run_id":state['run_id'], "status":state['status'], "phase":state['phase'],
               "iteration":state['iteration'], "reason":state.get('reason',''), "updated_at":now(),
               "domain":state.get('plan',{}).get('domain','unknown'),
               "source_head":state['expected_source']['head'],
               "state_path":(run_dir/'state.json').relative_to(workspace).as_posix()}
    atomic_json(record_path(workspace,'status.json'), summary)
    if target.exists() and not target.read_text('utf-8').startswith(MARKER):
        raise Blocked('report.md is not an owned generated report; preserve it before rerunning')
    review = state.get('review')
    plan = state.get('plan',{})
    dossier = state.get('dossier')
    unresolved = sorted([r for r in (review or {}).get('issues',[]) if r['status']!='resolved'],
                        key=lambda r: (['Critical','High','Medium','Low'].index(r['severity']),r['id']))
    stats = collections.Counter(r['severity'] for r in unresolved)
    lines = [MARKER, '# 調査・検証報告', '',
             f"実行ID: {state['run_id']} / **{state['status']}** / 段階: {state['phase']} / 反復: {state['iteration']}",
             f"更新: {summary['updated_at']}", '', '## 結論と確認してほしいこと', '',
             state.get('reason') or '実行中です。結論はまだ確定していません。', '',
             '課題: '+state['config']['brief'],
             '対象版: '+(state['expected_source']['head'] or 'Git管理なし'), '']
    if dossier:
        decision = dossier['decision']
        candidate = next((r['name'] for r in dossier['candidates'] if r['id']==decision['candidate_id']), '未選定')
        lines += [f"提案: **{candidate}**（{decision['status']}）", decision['rationale'], '',
                  '判断待ち・未確認: '+('; '.join(decision['unresolved']) or '台帳に記載なし'),
                  '見直す条件: '+('; '.join(decision['revisit_when']) or '台帳に記載なし'), '',
                  '研究の完了は方式の採用承認を意味しません。', '']
    if review:
        lines += ['未解消: '+' / '.join(f'{k} {stats[k]}件' for k in ['Critical','High','Medium','Low']), '']
        lines += [f"- {r['id']}: {r['title']}（{r['severity']}） → {r['improvement']}" for r in unresolved]
    else:
        lines += ['今回の実行はレビュー未成立です。前回の評価を今回の結果として扱わないでください。', '']
    lines += ['## 調査・比較・検証', '', '対象: '+plan.get('domain','未分類'),
              '目的: '+plan.get('goal',state['config']['brief']), '基準案: '+plan.get('baseline','未確認'), '']
    if dossier:
        lines += ['### 比較条件', '', dossier['scope'], '']
        lines += [f"- {r['kind']}: {r['text']}" for r in dossier['constraints']]
        lines += ['', '### 候補の比較', '', '| 方式 | 評価軸 | 結果 | 根拠の種類 |', '|---|---|---|---|']
        candidates = {r['id']:r for r in dossier['candidates']}
        for row in dossier['comparison']:
            name = candidates[row['candidate_id']]['name']
            lines.append(f"| {cell(name)} | {cell(row['criterion'])} | {cell(row['finding'])} | {row['basis']} |")
        sources = {r['id']:r for r in dossier['sources']}
        lines += ['', '### 主張と根拠', '']
        for claim in dossier['claims']:
            lines += [f"#### {claim['id']}（{claim['status']}）", '', claim['statement'],
                      '条件: '+claim['context'], '限界: '+'; '.join(claim['limitations']), '']
            for ev in claim['evidence']:
                source = sources[ev['source_id']]
                link = source.get('local_path') or source.get('url')
                lines.append(f"- [{source['id']}: {source['title']}]({link}) / {ev['relation']} / {ev['locator']}")
        if dossier['experiments']:
            lines += ['', '### 実験', '']
            for ex in dossier['experiments']:
                lines += [f"#### {ex['id']}（{ex['status']}）", '', ex['hypothesis'],
                          '統制条件: '+'; '.join(ex['controls']), '指標: '+'; '.join(ex['metrics']),
                          '合格条件: '+ex['acceptance'], '']
                lines += [f'- [実行証拠]({p})' for p in ex['artifacts']]
    if review:
        lines += ['', '### 確認結果', '', '| 確認対象 | 必須 | 結果 | 根拠・限界 |', '|---|---|---|---|']
        checked = {r['check_id']:r for r in review['checks']}
        for criterion in plan['criteria']:
            row = checked[criterion['id']]
            links = ', '.join(f"[{key}]({state['evidence'][key]['path']})" for key in row['evidence_ids'])
            lines.append(f"| {cell(criterion['id']+': '+criterion['title'])} | {'Yes' if criterion['required'] else 'No'} | {row['result']} | {cell(row['reason'])} {links} |")
        for issue in unresolved:
            lines += ['', f"### {issue['id']}: {issue['title']}", '',
                      f"重要度: {issue['severity']} / 対象: {issue['target']} / 状態: {issue['status']}",
                      '操作・再現: '+issue['action'], '期待結果: '+issue['expected'],
                      '実際の結果: '+issue['actual'], '影響: '+issue['why'],
                      '改善案: '+issue['improvement'], '']
            lines += evidence_links(issue['evidence_ids'],state,False)
        lines += ['', '### 複雑さの評価', '', review['complexity_reason'],
                  '評価: '+('許容' if review['complexity_ok'] else '見直しが必要'), '']
        if review['reference_implementations']:
            lines += ['### 参考となる設計・実装', '']
            for ref in review['reference_implementations']:
                lines += [f"- [{ref['name']}]({ref['url']}): {ref['strength']}",
                          '  - 適用: '+ref['application'], '  - 条件・限界: '+ref['limitations']]
                for key in ref['source_ids']:
                    source = state['sources'][key]
                    lines += [f"  - {key}: {source['source']['locator']} / {source['status']}"]
                    lines += evidence_links([source['evidence_id']],state,False)
    if state.get('fixes'):
        lines += ['', '## 変更と再検証', '', '修正担当の申告と独立した再確認を分けます。', '']
        for fix in state['fixes']:
            lines += [f"### 反復 {fix['iteration']}", '', fix['reason'],
                      '変更ファイル: '+', '.join(fix['actual_changed_files']), '']
            for change in fix['complexity_changes']:
                lines += ['- 変更: '+change['change'], '  - より単純な案: '+change['simpler_alternative'],
                          '  - 採用理由: '+change['reason']]
        for issue in (review or {}).get('issues',[]):
            if issue['status']!='resolved':
                continue
            old = next((r for h in state.get('history',[]) for r in h['review']['issues']
                        if r['id']==issue['id'] and r['status']!='resolved'),None)
            lines += ['', f"### {issue['id']}: {issue['title']}", '', '変更前の証拠:', '']
            if old:
                lines += evidence_links(old['evidence_ids'],state,False)
            lines += ['', '変更後の独立レビュー:', '']+evidence_links(issue['evidence_ids'],state,False)
    lines += ['', '## 残る確認と実行記録', '', state.get('reason',''),
              '実測・AIによる評価の範囲を示しています。人間の利用確認、本番運用、方式の普遍的な有効性は未確認です。',
              '中断した修正の差分は保持し、新しいaudit/runで再検証します。', '',
              f"[実行状態]({summary['state_path']}) · [機械用の状態](.internal/status.json)"]
    if dossier:
        atomic_json(record_path(workspace,'evidence.json'),dossier)
        lines += ['[出典・主張・実験の台帳](.internal/evidence.json)']
    atomic_json(record_path(workspace,'research-log.json'), {
        'schema_version':1, 'run_id':state['run_id'], 'discovery':state.get('discovery',[]),
        'sources':state['sources'], 'executions':state.get('executions',[]), 'status':state['status'],
        'stop_reason':state.get('reason',''), 'source_fingerprint':state['expected_source']})
    write(workspace,'report.md',lines)
    archive = regular_path(run_dir/'reports')
    archive.mkdir(exist_ok=True)
    def rebase(match):
        target = match[1]
        if target in {'.internal/status.json','.internal/evidence.json','.internal/research-log.json'}:
            return ']('+Path(target).name+')'
        if target.startswith(('http:','https:','#')):
            return match[0]
        return ']('+os.path.relpath(workspace/target,archive)+')'
    write(archive,'report.md',re.sub(r'\]\(([^)]+)\)',rebase,'\n'.join(lines)).splitlines())
    for name in ('status.json','research-log.json')+ (('evidence.json',) if dossier else ()):
        atomic_bytes(archive/name,record_path(workspace,name).read_bytes())


def publish_legacy(state, workspace, run_dir):
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
