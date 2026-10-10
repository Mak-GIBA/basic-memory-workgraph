#!/usr/bin/env python3
"""Offline, non-generative proposal ledger: initialize, audit and render method ideas.

Generation and literature reading belong to the surrounding research agent. This program
checks structural readiness; it cannot determine whether a method is novel or correct.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
FAMILIES = {"repair", "replacement", "transfer", "composition", "simplification", "fundamental"}
NOVELTY = {"unverified", "plausibly_distinct", "overlaps_prior_art"}
READ_LEVEL = {"metadata", "abstract", "relevant_sections", "full_text"}
DEFAULT_COMPARISON_TOTAL = 5  # baseline + four proposed alternatives


def skeleton(question: str = "", target_methods: int = DEFAULT_COMPARISON_TOTAL) -> dict:
    if target_methods < 3:
        raise ValueError("target_methods must be at least 3 (baseline + two alternatives)")
    return {
        "schema_version": 1,
        "question": question,
        "task": "",
        "baseline": {"id": "BASE", "name": "", "method": "", "known_limitations": []},
        "comparison_plan": {"target_total": target_methods, "exception_reason": ""},
        "primary_metric": "",
        "hard_constraints": [],
        "failure_modes": [],
        "sources": [],
        "candidates": [],
        "selection": {"leading_candidate_id": "", "rationale": "", "rejected_candidate_ids": []},
        "notes": ["A draft proposal is not a validated experiment or verified novel contribution."],
    }


def is_text(v, size=1):
    return isinstance(v, str) and len(v.strip()) >= size


def is_texts(v, minimum=1):
    return isinstance(v, list) and len(v) >= minimum and all(is_text(x) for x in v)


def checked_id(entry, path, issues):
    i = entry.get("id") if isinstance(entry, dict) else None
    if not isinstance(i, str) or not ID.fullmatch(i):
        issues.append(f"{path}.id: expected safe nonempty identifier")
        return ""
    return i


def unique_entries(data, field, issues):
    entries = data.get(field)
    if not isinstance(entries, list):
        issues.append(f"{field}: expected array")
        return [], set()
    found = set()
    for i, entry in enumerate(entries):
        value = checked_id(entry, f"{field}[{i}]", issues)
        if value in found and value:
            issues.append(f"{field}: duplicate ID {value}")
        found.add(value)
    return entries, found


def quality_issues(data: dict, *, strict: bool = False, allow_single_proposal: bool = False) -> list[str]:
    issues = []
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return ["schema_version: expected integer 1"]
    for key in ("question", "task", "primary_metric"):
        if strict and not is_text(data.get(key), 8):
            issues.append(f"{key}: substantive description required")
    base = data.get("baseline")
    if not isinstance(base, dict):
        issues.append("baseline: expected object")
    elif strict and (not is_text(base.get("name")) or not is_text(base.get("method"), 20)):
        issues.append("baseline: name and a concrete method description required")
    comparison_plan = data.get("comparison_plan", {})
    if not isinstance(comparison_plan, dict):
        issues.append("comparison_plan: expected object")
        comparison_plan = {}
    target_total = comparison_plan.get("target_total", DEFAULT_COMPARISON_TOTAL)
    if type(target_total) is not int or not 3 <= target_total <= 20:
        issues.append("comparison_plan.target_total: integer from 3 to 20 required")
        target_total = DEFAULT_COMPARISON_TOTAL
    exception_reason = comparison_plan.get("exception_reason", "")
    if not isinstance(exception_reason, str):
        issues.append("comparison_plan.exception_reason: expected string")
        exception_reason = ""
    if not isinstance(data.get("hard_constraints"), list):
        issues.append("hard_constraints: expected array")
    elif strict and not is_texts(data["hard_constraints"]):
        issues.append("hard_constraints: at least one meaningful constraint required")

    failures, failure_ids = unique_entries(data, "failure_modes", issues)
    sources, source_ids = unique_entries(data, "sources", issues)
    candidates, cand_ids = unique_entries(data, "candidates", issues)
    for f in failures:
        if not isinstance(f, dict):
            continue
        status = f.get("status")
        if status not in {"observed", "reported", "hypothesis"}:
            issues.append(f"failure_modes[{f.get('id')}].status: observed / reported / hypothesis")
        if strict and (not is_text(f.get("symptom"), 10) or not is_text(f.get("suspected_cause"), 10)):
            issues.append(f"failure_modes[{f.get('id')}]: symptom and cause must be explained")
        if status in {"observed", "reported"} and not is_text(f.get("evidence_locator")):
            issues.append(f"failure_modes[{f.get('id')}]: measured/reported failure needs evidence_locator")
    if strict and not failures:
        issues.append("failure_modes: diagnose at least one actual or hypothesized failure")

    deep_sources = 0
    studies = set()
    for s in sources:
        if not isinstance(s, dict):
            continue
        sid = s.get("id")
        if not is_text(s.get("title")) or not is_text(s.get("locator")):
            if strict:
                issues.append(f"sources[{sid}]: title and exact section/page locator required")
        if s.get("read_level") not in READ_LEVEL:
            issues.append(f"sources[{sid}].read_level: invalid")
        if is_text(s.get("url")) and not s["url"].startswith(("https://", "http://")):
            issues.append(f"sources[{sid}].url: must be http(s), or leave blank and supply local file path")
        if strict and not (is_text(s.get("url")) or is_text(s.get("local_path"))):
            issues.append(f"sources[{sid}]: retrievable URL or local_path required")
        if strict and not is_text(s.get("mechanism"), 18):
            issues.append(f"sources[{sid}]: explain the mechanism actually described")
        if s.get("read_level") in {"relevant_sections", "full_text"} and is_text(s.get("locator")):
            deep_sources += 1
            studies.add(s.get("study_id") or sid)
    if strict and (deep_sources < 2 or len(studies) < 2):
        issues.append("sources: read decisive sections in at least two independent primary studies; otherwise keep draft")
    if strict and len(candidates) + 1 < target_total:
        minimum = 1 if allow_single_proposal else 2
        if len(candidates) < minimum or not is_text(exception_reason, 30):
            issues.append(
                f"candidates: target approximately {target_total} total methods (1 baseline + "
                f"{target_total - 1} proposals); fewer require an explicit substantive "
                f"comparison_plan.exception_reason and at least {minimum} distinct proposal(s)"
            )
    families = set()
    mechanism_fingerprints = {}
    for c in candidates:
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        name = c.get("name", "")
        hypothesis = c.get("core_hypothesis", "")
        explanation = c.get("mechanistic_explanation", "")
        if isinstance(hypothesis, str) and isinstance(explanation, str) and hypothesis.strip() and explanation.strip():
            fingerprint = re.sub(r"\W+", "", (hypothesis + explanation).casefold())
            if fingerprint in mechanism_fingerprints:
                issues.append(f"candidates[{cid}]: same proposal mechanism as {mechanism_fingerprints[fingerprint]} (rename is not diversity)")
            mechanism_fingerprints[fingerprint] = cid
        fam = c.get("family")
        if fam not in FAMILIES:
            issues.append(f"candidates[{cid}].family: invalid proposal family")
        else:
            families.add(fam)
        for fid in c.get("failure_mode_ids", []):
            if fid not in failure_ids:
                issues.append(f"candidates[{cid}]: unknown failure_mode_id {fid}")
        for sid in c.get("source_ids", []):
            if sid not in source_ids:
                issues.append(f"candidates[{cid}]: unknown source_id {sid}")
        if c.get("novelty_status") not in NOVELTY:
            issues.append(f"candidates[{cid}].novelty_status: invalid; novelty cannot be auto-certified")
        if strict:
            required = {
                "name": 4, "core_hypothesis": 24, "mechanistic_explanation": 60,
                "transfer_mapping": 20, "integration_plan": 30,
                "resource_tradeoff": 20, "expected_failure_regime": 25,
                "prior_art_difference": 30,
            }
            if not (is_text(c.get("mathematical_specification"), 30) or is_text(c.get("pseudocode"), 40)):
                issues.append(f"candidates[{cid}]: mathematical_specification or pseudocode is required")
            for k, minlen in required.items():
                if not is_text(c.get(k), minlen):
                    issues.append(f"candidates[{cid}].{k}: detailed specification required")
            for k in ("assumptions", "testable_predictions", "critical_objections", "revision_actions"):
                if not is_texts(c.get(k)):
                    issues.append(f"candidates[{cid}].{k}: at least one concrete item required")
            if not isinstance(c.get("prior_art_queries"), list) or len(c["prior_art_queries"]) < 2:
                issues.append(f"candidates[{cid}].prior_art_queries: search both method-level and mechanism-level novelty")
            if not isinstance(c.get("failure_mode_ids"), list) or not c["failure_mode_ids"]:
                issues.append(f"candidates[{cid}].failure_mode_ids: connect to a diagnosed failure")
            if fam in {"transfer", "composition"} and not c.get("source_ids"):
                issues.append(f"candidates[{cid}].source_ids: transfer needs grounded source mapping")
            exp = c.get("discriminating_experiment")
            if not isinstance(exp, dict):
                issues.append(f"candidates[{cid}].discriminating_experiment: object required")
            else:
                for k in ("comparison", "primary_metric", "controls", "acceptance_rule", "negative_result_interpretation", "budget"):
                    if not is_text(exp.get(k), 10):
                        issues.append(f"candidates[{cid}].discriminating_experiment.{k}: specify before running")
            near = c.get("closest_prior_art_source_ids", [])
            if not isinstance(near, list) or not near:
                issues.append(f"candidates[{cid}].closest_prior_art_source_ids: name the most relevant retrieved prior work")
            else:
                for sid in near:
                    if sid not in source_ids:
                        issues.append(f"candidates[{cid}]: unknown closest prior art {sid}")
            if not c.get("prior_art_queries"):
                issues.append(f"candidates[{cid}]: prior-art search incomplete; novelty unverified")
    family_minimum = 1 if allow_single_proposal and len(candidates) == 1 else (3 if len(candidates) >= 4 else 2)
    if strict and len(families) < family_minimum:
        issues.append("candidates: vary the underlying mechanism (three families for four+ proposals; otherwise at least two)")
    sel = data.get("selection")
    if not isinstance(sel, dict):
        issues.append("selection: expected object")
    elif strict:
        lead = sel.get("leading_candidate_id")
        if lead not in cand_ids:
            issues.append("selection.leading_candidate_id: choose a known candidate")
        if not is_text(sel.get("rationale"), 40):
            issues.append("selection.rationale: defend choice against simplest competing method")
        for other in sel.get("rejected_candidate_ids", []):
            if other not in cand_ids:
                issues.append(f"selection.rejected_candidate_ids: unknown {other}")
    return issues


def line(v):
    return " ".join(str(v or "（未記入）").split())


def bullets(items):
    return "\n".join("- " + line(x) for x in (items or [])) or "- （未記入）"


def render(data: dict, issues: list[str]) -> str:
    sources = {s.get("id"): s for s in data.get("sources", []) if isinstance(s, dict)}
    ready = not issues
    out = ["# 提案手法の設計・比較レポート", "",
           f"> **品質ゲート:** {'仕様項目は充足（有効性・新規性は未証明）' if ready else '暫定案（未充足項目あり）'}。"
           " アイデア・文献上の報告・実測結果を混同しない。", "",
           "## 1. 研究課題と現行法", "",
           f"**問い:** {line(data.get('question'))}", "",
           f"**対象:** {line(data.get('task'))}", "",
           f"**主指標:** {line(data.get('primary_metric'))}", "",
           f"**現行方式:** {line(data.get('baseline', {}).get('method'))}", "",
           f"**比較の目安:** 全{data.get('comparison_plan', {}).get('target_total', DEFAULT_COMPARISON_TOTAL)}方式"
           f"（現行ベースライン1＋提案候補{data.get('comparison_plan', {}).get('target_total', DEFAULT_COMPARISON_TOTAL) - 1}）。"
           f"現在は全{len(data.get('candidates') or []) + 1}方式を記載。", "",
           "**厳守条件:**", bullets(data.get("hard_constraints")), "",
           "## 2. 観測された問題と原因仮説", ""]
    fs = data.get("failure_modes") or []
    if not fs: out.extend(["未記入（測定結果ではありません）。", ""])
    for f in fs:
        out.extend([f"### {line(f.get('id'))} — {line(f.get('symptom'))}", "",
                    f"- 区分: `{line(f.get('status'))}` / 根拠: {line(f.get('evidence_locator'))}",
                    f"- 原因仮説: {line(f.get('suspected_cause'))}", ""])
    out.extend(["## 3. 比較方式の要約（現行法を含む）", "",
                "| 案 | 方式 | 中核仮説 | 既存研究との区別 | 状態 |",
                "|---|---|---|---|---|"])
    out.append(f"| Baseline: {line(data.get('baseline', {}).get('name'))} | 現行法 | 比較基準 | 適用対象の現行実装 | 基準方式 |")
    for c in data.get("candidates") or []:
        cell = lambda val: line(val).replace("|", "\\|")[:210]
        out.append(f"| {cell(c.get('id'))}: {cell(c.get('name'))} | {cell(c.get('family'))} | {cell(c.get('core_hypothesis'))} | {cell(c.get('prior_art_difference'))} | {cell(c.get('novelty_status'))} |")
    out.append("")
    exception_reason = (data.get("comparison_plan") or {}).get("exception_reason")
    if exception_reason:
        out.extend([f"**比較方式数を絞った理由:** {line(exception_reason)}", ""])
    for c in data.get("candidates") or []:
        cid = c.get("id")
        out.extend([f"## 4. {line(cid)} — {line(c.get('name'))}", "",
                    "### 核心仮説と原理", line(c.get("core_hypothesis")), "",
                    line(c.get("mechanistic_explanation")), "",
                    "### 外部手法からの転用・変更", line(c.get("transfer_mapping")), "",
                    "### 数式・目的関数・処理の定義", "```text", str(c.get("mathematical_specification") or "未記入"), "```", "",
                    "### 擬似コード", "```text", str(c.get("pseudocode") or "未記入"), "```", "",
                    "### 組み込みと計算負担", line(c.get("integration_plan")), "",
                    line(c.get("resource_tradeoff")), "",
                    "### 成立条件・反証可能な予測", bullets(c.get("assumptions")), "",
                    bullets(c.get("testable_predictions")), "",
                    "**効かないと予想される領域:** " + line(c.get("expected_failure_regime")), "",
                    "### 先行研究と新規性の暫定判断", "",
                    f"**判定:** `{line(c.get('novelty_status'))}`。新規性は自動認定されません。", "",
                    line(c.get("prior_art_difference")), "",
                    "**検索語:**", bullets(c.get("prior_art_queries")), "",
                    "**最も近い既存研究:**", bullets([f"[{sid}] {sources.get(sid, {}).get('title', '不明')}" for sid in c.get("closest_prior_art_source_ids", [])]), "",
                    "**転用元の一次資料:**"])
        ss = c.get("source_ids") or []
        out.extend([bullets([f"[{sid}] {sources.get(sid,{}).get('title','不明')} — {sources.get(sid,{}).get('locator','未記入')}" for sid in ss]), "",
                    "### 反対意見と改訂内容", "",
                    "**主要な反論:**", bullets(c.get("critical_objections")), "",
                    "**反論を受けての改訂・再検証:**", bullets(c.get("revision_actions")), "",
                    "### この案を区別する最小実験", ""])
        exp = c.get("discriminating_experiment") or {}
        for k, label in (("comparison","比較方法"),("controls","統制・負の対照"),("primary_metric","指標"),("acceptance_rule","事前の判断条件"),("negative_result_interpretation","悪い結果の解釈"),("budget","計算予算")):
            out.append(f"- **{label}:** {line(exp.get(k))}")
        out.append("")
    sel = data.get("selection") or {}
    out.extend(["## 5. 研究上の判断と次の実験", "",
                f"**第一候補:** {line(sel.get('leading_candidate_id'))}（暫定選定であり、実証済みの勝者ではない）", "",
                f"**選定理由:** {line(sel.get('rationale'))}", "",
                f"**除外・保留:** {', '.join(sel.get('rejected_candidate_ids') or []) or '未決定'}", "",
                "## 6. 先行文献・根拠の確認範囲", ""])
    for sid, s in sources.items():
        dest = s.get('url') or s.get('local_path') or '所在未記入'
        out.append(f"- [{sid}] {line(s.get('title'))} — {dest}; 読取範囲 `{line(s.get('read_level'))}` / {line(s.get('locator'))}")
    out.extend(["", "## 7. 未充足の確認項目", ""])
    if issues:
        out.extend("- " + x for x in issues)
    else:
        out.append("- 仕様項目に構造的な欠落はありません。原典の正確性、実装の妥当性、研究的新規性、性能優位は別途検証が必要です。")
    return "\n".join(out).rstrip() + "\n"


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init", help="Create a blank auditable proposed-method ledger")
    init.add_argument("--out", type=Path, required=True)
    init.add_argument("--question", default="")
    init.add_argument("--target-methods", type=int, default=DEFAULT_COMPARISON_TOTAL,
                      help="Target total methods including baseline (default: 5)")
    val = sub.add_parser("validate", help="Check structural completeness; never asserts scientific correctness")
    val.add_argument("file", type=Path)
    val.add_argument("--strict", action="store_true")
    ren = sub.add_parser("render", help="Render a readable provisional or structurally complete method report")
    ren.add_argument("file", type=Path)
    ren.add_argument("--out", type=Path, required=True)
    ren.add_argument("--strict", action="store_true", help="Refuse rendering until strict gates pass")
    args = parser.parse_args(argv)
    if args.action == "init":
        if not 3 <= args.target_methods <= 20:
            parser.error("--target-methods must be between 3 and 20")
        if args.out.exists():
            parser.error(f"Refusing to overwrite existing file: {args.out}")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(skeleton(args.question, args.target_methods), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print(f"Initialized {args.out}; no evidence or candidates invented")
        return 0
    try:
        data = json.loads(args.file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    issues = quality_issues(data, strict=args.strict)
    if args.action == "validate":
        if issues:
            for x in issues: print("INVALID:", x, file=sys.stderr)
            return 1
        print("PASS: structural checks only; no scientific or novelty certification")
        return 0
    if args.strict and issues:
        for x in issues: print("INVALID:", x, file=sys.stderr)
        return 1
    if args.out.resolve() == args.file.resolve():
        parser.error("Refusing to overwrite source evidence JSON")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(data, quality_issues(data, strict=True)), encoding="utf-8")
    print(f"Rendered {args.out}; unresolved strict gates: {len(quality_issues(data, strict=True))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
