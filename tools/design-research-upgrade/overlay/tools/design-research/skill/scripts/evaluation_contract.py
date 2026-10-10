"""Frozen, task-specific effectiveness contracts and receipt-backed paired results.

Mechanical grading verifies declared properties, not whether a chosen metric is
scientifically adequate. The independent reviewer must assess that separately.
Legacy runs have no evaluation_contract_version and retain their original gates.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from runtime import Blocked, relative, sha256, regular_path, sensitive_path
from evidence import existing_artifact

PURPOSES = ("auto", "effectiveness", "design", "literature")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                   allow_nan=False).encode()).hexdigest()


def active(state):
    return state.get("evaluation_contract_version") == 1


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def freeze(state):
    if not active(state):
        return
    try:
        value = json.loads(state["plan"]["evaluation_json"])
        purpose = value["purpose"]
        requested = state["config"].get("evaluation_purpose", "auto")
        if purpose not in PURPOSES[1:] or (requested != "auto" and purpose != requested):
            raise ValueError("purpose differs from the requested evaluation")
        for key in ("dataset", "budget", "limitations"):
            if not isinstance(value[key], str) or not value[key].strip():
                raise ValueError("declare " + key)
        if not isinstance(value["controls"], list) or not value["controls"] or any(
                not isinstance(c, str) or not c.strip() for c in value["controls"]):
            raise ValueError("declare common inputs, model/runtime, permissions and resource conditions")
        candidates = value["candidate_ids"]
        if (not isinstance(candidates, list) or len(set(candidates)) != len(candidates)
                or len(candidates) < 2 or value["baseline_id"] not in candidates
                or any(not isinstance(c, str) or not c for c in candidates)):
            raise ValueError("declare a baseline and at least one compared candidate")
        criteria = {c["id"]: c for c in state["plan"]["criteria"]}
        metrics = value["metrics"]
        if not isinstance(metrics, list):
            raise ValueError("metrics must be a list")
        ids = set()
        for m in metrics:
            if m["id"] in ids or not isinstance(m["id"], str) or not m["id"]:
                raise ValueError("metric IDs must be unique")
            ids.add(m["id"])
            if (m["kind"] not in ("exact_match", "absolute_error", "scalar")
                    or m["direction"] not in ("higher", "lower") or m["aggregation"] != "mean"
                    or not isinstance(m["primary"], bool) or not number(m["acceptance_delta"])):
                raise ValueError("invalid grader, direction, aggregation or acceptance threshold")
            for key in ("unit", "grading", "outcome_scope"):
                if not isinstance(m[key], str) or not m[key].strip():
                    raise ValueError("metric needs " + key)
            if m["primary"] and m["outcome_scope"] != "final_outcome":
                raise ValueError("primary metrics must grade final task outcomes, not bookkeeping")
            c = criteria.get(m["criterion_id"])
            if not c:
                raise ValueError("metric references an unknown frozen criterion")
            if purpose == "effectiveness" and m["primary"] and (
                    c["kind"] != "runtime" or not c["required"]):
                raise ValueError("effectiveness primary metrics need required runtime criteria")
        if purpose == "effectiveness" and not any(m["primary"] for m in metrics):
            raise ValueError("effectiveness needs at least one primary final-outcome metric")
        if purpose == "effectiveness":
            frozen_tasks(value, state)
        signature = digest(value)
        if state.get("evaluation_contract_sha256") not in (None, signature):
            raise ValueError("frozen evaluation changed; start a new run")
        state["evaluation_contract"] = value
        state["evaluation_contract_sha256"] = signature
    except (ValueError, KeyError, TypeError) as exc:
        raise Blocked("Evaluation plan: " + str(exc)) from exc


def frozen_tasks(contract, state):
    tasks = contract.get("tasks")
    if tasks is None and contract.get("task_manifest"):
        name = relative(contract["task_manifest"]).as_posix()
        if sensitive_path(name) or name not in state["expected_source"]["files"]:
            raise ValueError("task_manifest must be a frozen non-secret project file")
        path = regular_path(Path(state["config"]["project"]) / name)
        if not path.is_file() or path.stat().st_size > 5 * 1024 * 1024:
            raise ValueError("task_manifest is missing or oversized")
        tasks = json.loads(path.read_text("utf-8"))
    if (not isinstance(tasks, list) or not tasks or len(tasks) > 10000
            or any(not isinstance(t, dict) or not isinstance(t.get("id"), str) or not t["id"]
                   or "input" not in t or "expected" not in t for t in tasks)):
        raise ValueError("freeze task IDs, common inputs and expected outcomes in tasks or task_manifest before experiments")
    mapped = {t["id"]: t for t in tasks}
    if len(mapped) != len(tasks):
        raise ValueError("frozen task IDs must be unique")
    return mapped


def assert_frozen(state):
    if active(state) and state.get("evaluation_contract"):
        try:
            if (digest(state["evaluation_contract"]) != state["evaluation_contract_sha256"]
                    or json.loads(state["plan"]["evaluation_json"]) != state["evaluation_contract"]):
                raise ValueError("contract differs from the frozen plan")
        except (KeyError, ValueError, TypeError) as exc:
            raise Blocked("Evaluation contract changed; start a new run") from exc


def measure(dossier, state, workspace):
    """Recompute paired grades from immutable current parent-exported JSON artifacts."""
    assert_frozen(state)
    contract = state["evaluation_contract"]
    declared = dossier.get("evaluation_result", {})
    paths = declared.get("artifact_paths", [])
    if (declared.get("contract_sha256") != state["evaluation_contract_sha256"]
            or not isinstance(paths, list) or not paths or len(set(paths)) != len(paths)):
        raise Blocked("Evaluation needs the frozen contract hash and actual paired-result artifacts")
    known = {r["path"]: r for r in state["evidence"].values()}
    # add_record's source signature uses JSON's default ensure_ascii; preserve that format.
    signature = hashlib.sha256(json.dumps(state["expected_source"], sort_keys=True).encode()).hexdigest()
    tasks, trials = {}, []
    for name in paths:
        relative(name)
        r = known.get(name, {})
        if (r.get("kind") != "artifact" or r.get("iteration") != state["iteration"]
                or r.get("source_fingerprint") != signature):
            raise Blocked("Evaluation artifact needs a current matching parent record: " + str(name))
        path = existing_artifact(workspace, name)
        if sha256(path) != r["sha256"] or path.stat().st_size > 5 * 1024 * 1024:
            raise Blocked("Evaluation artifact changed or exceeds its limit")
        receipts = [e for e in state["evidence"].values() if e.get("kind") == "experiment"
                    and e.get("experiment_id") == r.get("experiment_id")
                    and e.get("iteration") == state["iteration"]
                    and e.get("source_fingerprint") == signature
                    and e.get("exit_code") == 0 and not e.get("timed_out") and not e.get("truncated")]
        if not any(any(a["path"] == name and a["sha256"] == r["sha256"] for a in
                       json.loads(existing_artifact(workspace, e["path"]).read_text())["artifacts"])
                   for e in receipts):
            raise Blocked("Evaluation artifact has no successful current exporting receipt")
        try:
            data = json.loads(path.read_text("utf-8"))
            if data["contract_sha256"] != state["evaluation_contract_sha256"]:
                raise ValueError("result contract hash mismatch")
            for task in data["tasks"]:
                if not isinstance(task["id"], str) or not task["id"] or task["id"] in tasks:
                    raise ValueError("task IDs must be unique across result artifacts")
                if not all(k in task for k in ("input", "expected")):
                    raise ValueError("each task needs shared input and expected final outcome")
                tasks[task["id"]] = {**task, "artifact_path": name}
            for trial in data["trials"]:
                trial = {**trial, "artifact_path": name}
                trials.append(trial)
        except (KeyError, TypeError, ValueError) as exc:
            raise Blocked("Invalid paired result artifact: " + str(exc)) from exc
    if not tasks or not trials:
        raise Blocked("Paired results need real task inputs and outputs")
    try:
        frozen = frozen_tasks(contract, state)
        if tasks.keys() != frozen.keys() or any(
                digest(tasks[tid][key]) != digest(frozen[tid][key])
                for tid in tasks for key in ("input", "expected")):
            raise ValueError("result tasks/inputs/expected outcomes differ from the frozen evaluation")
    except (ValueError, KeyError, TypeError) as exc:
        raise Blocked("Paired inputs: " + str(exc)) from exc
    rows, groups = {}, {}
    candidates = set(contract["candidate_ids"])
    try:
        for trial in trials:
            tid, repeat, cid = trial["task_id"], trial["trial_id"], trial["candidate_id"]
            if tid not in tasks or cid not in candidates or not isinstance(repeat, str) or not repeat:
                raise ValueError("unknown task/candidate or missing trial ID")
            key = (tid, repeat, cid)
            if key in rows or "output" not in trial:
                raise ValueError("duplicate trial or missing actual final output")
            groups.setdefault((tid, repeat), set()).add(cid)
            grades = {}
            for metric in contract["metrics"]:
                kind = metric["kind"]
                if kind == "exact_match":
                    score = float(digest(trial["output"]) == digest(tasks[tid]["expected"]))
                elif kind == "absolute_error":
                    if not number(trial["output"]) or not number(tasks[tid]["expected"]):
                        raise ValueError("absolute_error needs finite numeric final outputs")
                    score = abs(trial["output"] - tasks[tid]["expected"])
                else:
                    score = trial["values"][metric["id"]]
                    if not number(score) or not trial.get("grading_evidence"):
                        raise ValueError("scalar grades need finite values and grading_evidence")
                grades[metric["id"]] = score
            rows[key] = {**trial, "grades": grades}
        if any(g != candidates for g in groups.values()) or set(tasks) != {k[0] for k in groups}:
            raise ValueError("every task/trial must compare all candidates on the same input")
    except (KeyError, ValueError, TypeError) as exc:
        raise Blocked("Paired outcome grading: " + str(exc)) from exc
    metrics = []
    for metric in contract["metrics"]:
        means = {cid: sum(r["grades"][metric["id"]] for k, r in rows.items() if k[2] == cid) /
                 len(groups) for cid in contract["candidate_ids"]}
        baseline = means[contract["baseline_id"]]
        comparisons = []
        for cid, value in means.items():
            if cid == contract["baseline_id"]:
                continue
            delta = (value - baseline) * (1 if metric["direction"] == "higher" else -1)
            comparisons.append({"candidate_id": cid, "baseline": baseline, "candidate": value,
                                "delta": delta, "meets_threshold": delta >= metric["acceptance_delta"] or
                                math.isclose(delta, metric["acceptance_delta"], rel_tol=1e-12, abs_tol=1e-12)})
        metrics.append({**metric, "comparisons": comparisons})
    return {"status": "measured", "distinct_tasks": len(tasks), "paired_trials": len(groups),
            "metrics": metrics, "tasks": tasks, "trials": list(rows.values()),
            "scope": "この入力集合と宣言した採点規則に限る結果です。統計的有意性や方式の普遍的な優位は示しません。"}


def checkpoint_results(state, workspace):
    """Keep verified measurements available even if the model review later stops."""
    if not active(state) or not state.get("evaluation_contract", {}).get("metrics"):
        return None
    paths = []
    for record in state.get("evidence", {}).values():
        if record.get("kind") != "artifact" or record.get("iteration") != state["iteration"]:
            continue
        path = existing_artifact(workspace, record["path"])
        if path.suffix != ".json" or path.stat().st_size > 5 * 1024 * 1024:
            continue
        if sha256(path) != record["sha256"]:
            raise Blocked("Evaluation artifact changed before grading")
        try:
            value = json.loads(path.read_text("utf-8"))
        except (ValueError, UnicodeError):
            continue
        if isinstance(value, dict) and "contract_sha256" in value:
            if value["contract_sha256"] != state["evaluation_contract_sha256"]:
                raise Blocked("Exported paired result differs from the frozen contract")
            paths.append(record["path"])
    if not paths:
        return None
    summary = measure({"evaluation_result": {
        "contract_sha256": state["evaluation_contract_sha256"], "artifact_paths": paths}}, state, workspace)
    summary["iteration"] = state["iteration"]
    summary["source_fingerprint"] = digest(state["expected_source"])
    state["evaluation_summary"] = summary
    state["evaluation_review_bound"] = False
    return summary


def evaluate(dossier, state, workspace):
    if not active(state):
        return None
    contract = state["evaluation_contract"]
    candidates = {c["id"]: c for c in dossier["candidates"]}
    if (set(contract["candidate_ids"]) - candidates.keys()
            or not candidates[contract["baseline_id"]]["baseline"]):
        raise Blocked("Dossier candidates/baseline differ from the frozen evaluation")
    if dossier.get("evaluation_result"):
        summary = measure(dossier, state, workspace)
        state["evaluation_review_bound"] = True
    else:
        current = state.get("evaluation_summary", {})
        if (contract["purpose"] == "effectiveness" and current.get("status") == "measured"
                and current.get("iteration") == state["iteration"]
                and current.get("source_fingerprint") == digest(state["expected_source"])):
            state["evaluation_review_bound"] = False
            raise Blocked("Primary effects measured, but independent review has not bound the result artifacts")
        summary = {"status": "unmeasured", "distinct_tasks": 0, "paired_trials": 0,
                   "metrics": [], "scope": "主要効果は未測定。資料・設計の比較として扱います。"}
    state["evaluation_summary"] = summary
    summary["iteration"] = state["iteration"]
    summary["source_fingerprint"] = digest(state["expected_source"])
    if contract["purpose"] == "effectiveness" and summary["status"] != "measured":
        raise Blocked("Primary effect unmeasured: effectiveness validation cannot complete")
    if summary["status"] == "unmeasured" and dossier["decision"]["status"] == "proposed":
        raise Blocked("Unmeasured effects need a provisional/deferred decision")
    selected = dossier["decision"].get("candidate_id")
    if (summary["status"] == "measured" and dossier["decision"]["status"] == "proposed"
            and selected != contract["baseline_id"]):
        primary = [m for m in summary["metrics"] if m["primary"]]
        if not primary or any(not any(c["candidate_id"] == selected and c["meets_threshold"]
                                      for c in m["comparisons"]) for m in primary):
            raise Blocked("Proposed candidate does not meet the frozen primary-effect thresholds")
    return summary


def sections(state):
    if not active(state):
        return []
    contract = state.get("evaluation_contract")
    if not contract:
        return ["## 効果の測定状況", "", "評価条件はまだ確定していません。", ""]
    summary = state.get("evaluation_summary", {})
    out = ["## 主要指標と具体的な差", "", "研究の目的: " + contract["purpose"], "",
           "対象入力: " + contract["dataset"], "統制条件: " + "; ".join(contract["controls"]),
           "予算・測定範囲: " + contract["budget"], "適用限界: " + contract["limitations"], ""]
    current = (summary.get("iteration") == state["iteration"]
               and summary.get("source_fingerprint") == digest(state["expected_source"]))
    if summary.get("status") != "measured" or not current:
        return out + ["**主要効果は未測定です。効果の改善・不改善の結論は出せません。**", ""]
    if state.get("evaluation_review_bound") is False:
        out += ["実出力の採点は済んでいます。独立レビューによる結果の確認は未完了です。", ""]
    out += [f"異なる課題 {summary['distinct_tasks']} 件 / 対になる試行 {summary['paired_trials']} 組。繰り返しを別課題として数えません。", "",
            "| 指標 | 候補 | 基準 | 候補の実測値 | 改善方向の差 | 事前の条件 | 判定 |",
            "|---|---|---|---|---|---|---|"]
    for m in summary["metrics"]:
        for c in m["comparisons"]:
            out.append(f"| {m['id']} ({m['unit']}) | {c['candidate_id']} | {c['baseline']:.6g} | {c['candidate']:.6g} | {c['delta']:.6g} | 差 ≥ {m['acceptance_delta']} | {'条件を満たす' if c['meets_threshold'] else '条件を満たさない'} |")
    # Preserve a failure example first, plus a success or ordinary example, without hiding totals.
    task_ids = list(summary["tasks"])
    task_ids.sort(key=lambda tid: all(r["output"] == summary["tasks"][tid]["expected"]
                                     for r in summary["trials"] if r["task_id"] == tid))
    for tid in task_ids[:2]:
        task = summary["tasks"][tid]
        out += ["", "### 実行した具体例: " + tid, "", "共通の入力:", "", "```json",
                json.dumps(task["input"], ensure_ascii=False, indent=2), "```", "", "期待する最終結果:", "", "```json",
                json.dumps(task["expected"], ensure_ascii=False, indent=2), "```", ""]
        matching = [r for r in summary["trials"] if r["task_id"] == tid]
        failed = next((r for r in matching if r["output"] != task["expected"]), None)
        repeat = (failed or matching[0])["trial_id"]
        for r in summary["trials"]:
            if r["task_id"] == tid and r["trial_id"] == repeat:
                out += [f"{r['candidate_id']} の実際の最終結果（試行 {repeat}）:", "", "```json",
                        json.dumps(r["output"], ensure_ascii=False, indent=2), "```", "",
                        "採点: " + json.dumps(r["grades"], ensure_ascii=False), "",
                        f"[実行して保存した結果]({r['artifact_path']})", ""]
    return out + [summary["scope"], ""]


def instructions(role, state):
    if not active(state):
        return ""
    return """\nEVALUATION CONTRACT v1: Read references/effectiveness-evaluation.md before planning.
The planner must return evaluation_json: freeze purpose, final-outcome primary metrics,
grading rules, baseline/candidate IDs, paired inputs, controls, resource scope and acceptance
thresholds appropriate to this task BEFORE execution. Explicit requested purpose is binding.
An effectiveness request cannot be downgraded to design/literature to avoid measurement.
Tool response size, echoed thought strings, status codes and retrieval count alone do NOT
measure reasoning accuracy, generated-code correctness or final user-task success.
Design/literature research may finish with primary effects explicitly unmeasured and a
provisional/deferred decision. Illustrative examples are not measured comparisons.
Effectiveness needs actual paired final outputs exported by parent experiments. Each pair
uses the same task input/expected output and all frozen candidates. Keep failures and
distinguish unique tasks from repeated trials; do not infer statistical significance.
Use dossier.evaluation_result with contract_sha256 and workspace-relative artifact_paths;
the parent recomputes grades. Negative/equal results are valid completed research, never
force an improvement. State a recommendation consistent with threshold results and limits.
For scalar metrics explain the grader and retain grading_evidence; reviewer must inspect
its validity. Claims beyond the tested task/model/budget remain unverified.
"""
