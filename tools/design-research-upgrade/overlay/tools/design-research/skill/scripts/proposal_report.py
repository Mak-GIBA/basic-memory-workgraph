#!/usr/bin/env python3
"""Validate and render an explanatory proposed-method chapter (stdlib; no model calls).

Diagrams are generated from a bounded graph, never accepted as executable/raw SVG.
Readiness is structural: it does not establish novelty, scientific validity or results.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import unicodedata

from method_ideation import quality_issues, DEFAULT_COMPARISON_TOTAL

ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
KINDS = {"architecture", "module_detail", "baseline_comparison"}
READ_DEPTH = {"metadata": 0, "abstract": 1, "relevant_sections": 2, "full_text": 3}
PLACEHOLDER = re.compile(r"^(?:todo|tbd|n/?a|未記入|未定|後で|\.\.\.|…|\{\{.*\}\})[.。！!\s]*$", re.I)
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
RENDERER_VERSION = 1


def text_ok(value):
    return isinstance(value, str) and bool(value.strip()) and not PLACEHOLDER.fullmatch(value.strip())


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def design_digest(ideas):
    return hashlib.sha256(canonical({"renderer_version": RENDERER_VERSION, "method_ideas": ideas})).hexdigest()


def method_required(state):
    # Persist the profile for new runs. Old runs without it retain their old contract.
    return state.get("config", {}).get("mode") == "research" and state.get("config", {}).get("report_profile") == "proposed-method"


def _rows(value):
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _index(value):
    return {v.get("id"): v for v in _rows(value) if isinstance(v.get("id"), str)}


def _references(value, allowed, path, errors, required=True):
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        errors.append(f"{path}: expected identifier array")
        return []
    if (required and not value) or len(value) != len(set(value)):
        errors.append(f"{path}: nonempty, unique references required")
    for ref in value:
        if ref not in allowed:
            errors.append(f"{path}: unknown reference {ref}")
    return value


def _texts(row, fields, path, errors):
    for name in fields:
        if not text_ok(row.get(name)):
            errors.append(f"{path}.{name}: explain this item; placeholders do not count")
        elif len(row[name]) > 12000:
            errors.append(f"{path}.{name}: exceeds the bounded narrative size")


def _objects(value, path, errors, lo=1, hi=40, ids=False):
    if not isinstance(value, list) or not lo <= len(value) <= hi or not all(isinstance(x, dict) for x in value):
        errors.append(f"{path}: expected {lo}..{hi} objects")
        return []
    seen = set()
    if ids:
        for row in value:
            key = row.get("id")
            if not isinstance(key, str) or not ID.fullmatch(key) or key in seen:
                errors.append(f"{path}: unsafe or duplicate ID")
            else:
                seen.add(key)
    return value


def _layers(fig):
    """Topological ranks for solid flow arrows; feedback is explicitly dashed."""
    nodes = {n["id"]: n for n in fig["nodes"]}
    indegree = dict.fromkeys(nodes, 0)
    children = {n: [] for n in nodes}
    ranks = dict.fromkeys(nodes, 0)
    for edge in fig["edges"]:
        if edge["kind"] == "flow":
            children[edge["from"]].append(edge["to"])
            indegree[edge["to"]] += 1
    queue = [n for n in nodes if indegree[n] == 0]
    order = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for child in children[node]:
            ranks[child] = max(ranks[child], ranks[node] + 1)
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(order) != len(nodes):
        raise ValueError("Flow arrows contain a cycle; mark an intentional feedback edge as feedback")
    result = []
    for level in range(max(ranks.values(), default=-1) + 1):
        result.append([nodes[n] for n in order if ranks[n] == level])
    return result


def graph_issues(fig, components):
    errors = []
    path = "figures[" + str(fig.get("id", "?")) + "]"
    _texts(fig, ("title", "caption", "alt_text", "explanation"), path, errors)
    if isinstance(fig.get("title"), str) and len(fig["title"]) > 160:
        errors.append(path + ".title: shorten the figure title; explain details in the caption")
    if fig.get("kind") not in KINDS:
        errors.append(path + ".kind: architecture / module_detail / baseline_comparison required")
    covered = _references(fig.get("component_ids"), components, path + ".component_ids", errors)
    nodes = _objects(fig.get("nodes"), path + ".nodes", errors, 2, 16, True)
    edges = _objects(fig.get("edges"), path + ".edges", errors, 1, 28)
    node_ids = _index(nodes)
    linked_components = set()
    for node in nodes:
        _texts(node, ("label", "detail"), path + ".nodes", errors)
        if len(str(node.get("label", ""))) > 80 or len(str(node.get("detail", ""))) > 160:
            errors.append(path + ": shorten node labels/details; put full explanations in prose")
        if node.get("lane") not in {"baseline", "proposal", "shared"}:
            errors.append(path + ": node lane must be baseline, proposal or shared")
        if node.get("change") not in {"unchanged", "added", "modified"}:
            errors.append(path + ": node change must be unchanged, added or modified")
        ref = node.get("component_id")
        if ref:
            if not isinstance(ref, str) or ref not in components:
                errors.append(path + ": node refers to unknown component")
            else:
                linked_components.add(ref)
        elif ref != "":
            errors.append(path + ": use an empty component_id only for boundary/baseline nodes")
    used, edge_keys = set(), set()
    for edge in edges:
        _texts(edge, ("label",), path + ".edges", errors)
        if len(str(edge.get("label", ""))) > 80:
            errors.append(path + ": edge label too long")
        start, end = edge.get("from"), edge.get("to")
        if not isinstance(start, str) or not isinstance(end, str) or start not in node_ids or end not in node_ids or start == end:
            errors.append(path + ": edges need two distinct known nodes")
        else:
            used.update((start, end))
            key = (start, end, edge.get("kind") if isinstance(edge.get("kind"), str) else "?")
            if key in edge_keys:
                errors.append(path + ": duplicate arrow")
            edge_keys.add(key)
        if edge.get("kind") not in {"flow", "feedback"}:
            errors.append(path + ": edge kind must be flow or feedback")
    if set(covered) != linked_components:
        errors.append(path + ": component_ids must match component references in its nodes")
    if set(node_ids) - used:
        errors.append(path + ": disconnected boxes are not an explanatory flow diagram")
    if fig.get("kind") == "baseline_comparison":
        lanes = {n.get("lane") for n in nodes if isinstance(n.get("lane"), str)}
        if not {"baseline", "proposal"} <= lanes:
            errors.append(path + ": baseline_comparison must show both baseline and proposal lanes")
    if fig.get("kind") == "module_detail" and not any(n.get("change") in {"added", "modified"} for n in nodes):
        errors.append(path + ": module_detail must expose a proposed or modified operation")
    if not errors:
        try:
            if any(len(layer) > 4 for layer in _layers(fig)):
                errors.append(path + ": more than four parallel boxes; split the figure for readability")
        except ValueError as exc:
            errors.append(path + ": " + str(exc))
    return errors


def _validation_issues(dossier, *, target_methods=DEFAULT_COMPARISON_TOTAL, allow_single_proposal=False):
    """Validate the design contract, cross-links and graph; not research truth."""
    if not isinstance(dossier, dict):
        return ["dossier: expected object"]
    ideas = dossier.get("method_ideas")
    if not isinstance(ideas, dict):
        return ["method_ideas: required for a proposed-method report"]
    try:
        errors = ["method_ideas." + x for x in quality_issues(ideas, strict=True, allow_single_proposal=allow_single_proposal)]
    except (TypeError, KeyError, AttributeError, ValueError):
        return ["method_ideas: malformed nested design record"]
    comparison = ideas.get("comparison_plan")
    if not isinstance(comparison, dict) or comparison.get("target_total") != target_methods:
        errors.append("method_ideas.comparison_plan.target_total: must equal the run's frozen target")
    candidates = _index(ideas.get("candidates"))
    selection = ideas.get("selection", {})
    selected_id = selection.get("leading_candidate_id") if isinstance(selection, dict) else None
    candidate = candidates.get(selected_id) if isinstance(selected_id, str) else None
    if not candidate:
        return errors + ["method_ideas.selection: a known method to explain is required; label it provisional, not a proven winner"]
    baseline = ideas.get("baseline", {})
    bid = baseline.get("id") if isinstance(baseline, dict) else None
    dcandidates = _index(dossier.get("candidates"))
    if not isinstance(bid, str) or bid not in dcandidates or not dcandidates[bid].get("baseline"):
        errors.append("method_ideas.baseline.id: link the actual baseline in dossier.candidates")
    if set(dcandidates) != set(candidates) | ({bid} if isinstance(bid, str) else set()):
        errors.append("method_ideas: comparison candidate IDs must match the dossier, including the baseline")
    for cid, item in candidates.items():
        if cid in dcandidates and item.get("name") != dcandidates[cid].get("name"):
            errors.append(f"method_ideas.candidates[{cid}]: name differs from dossier comparison")
    dsources = _index(dossier.get("sources"))
    for source in _rows(ideas.get("sources")):
        sid = source.get("id")
        other = dsources.get(sid) if isinstance(sid, str) else None
        if not other:
            errors.append("method_ideas.sources: unregistered dossier source " + str(sid))
        elif (source.get("url") or source.get("local_path")) != (other.get("url") or other.get("local_path")):
            errors.append("method_ideas.sources: source identity differs from dossier " + str(sid))
        elif READ_DEPTH.get(source.get("read_level"), -1) > READ_DEPTH.get(other.get("read_level"), -1):
            errors.append("method_ideas.sources: read depth exceeds dossier " + str(sid))
    p = candidate.get("presentation")
    if not isinstance(p, dict):
        return errors + ["selected presentation: required; a candidate list is not a Methods chapter"]
    _texts(p, ("overview", "worked_example", "training", "inference", "evidence_scope", "selection_note"), "presentation", errors)
    comps = _objects(p.get("components"), "presentation.components", errors, 1, 16, True)
    component_ids = _index(comps)
    for component in comps:
        _texts(component, ("name", "inputs", "outputs", "operation", "rationale", "baseline_difference", "cost"), "components[" + str(component.get("id")) + "]", errors)
    symbols = _objects(p.get("symbols"), "presentation.symbols", errors, 0, 50)
    if text_ok(candidate.get("mathematical_specification")) and not symbols:
        errors.append("presentation.symbols: define the symbols and shapes used in the formulation")
    for symbol in symbols:
        _texts(symbol, ("symbol", "definition", "shape"), "presentation.symbols", errors)
    if text_ok(candidate.get("mathematical_specification")):
        _texts(p, ("equation_explanation",), "presentation", errors)
    else:
        _texts(p, ("formalism_note",), "presentation", errors)
    differences = _objects(p.get("differences"), "presentation.differences", errors)
    for row in differences:
        _texts(row, ("aspect", "baseline", "proposal", "tradeoff"), "presentation.differences", errors)
    predictions = _objects(p.get("verification"), "presentation.verification", errors)
    experiments = _index(dossier.get("experiments"))
    for row in predictions:
        _texts(row, ("hypothesis", "alternative_explanation", "rejection_condition"), "presentation.verification", errors)
        eid = row.get("experiment_id")
        if not isinstance(eid, str) or eid not in experiments:
            errors.append("presentation.verification: experiment_id must link a dossier experiment")
        _references(row.get("component_ids"), component_ids, "presentation.verification.component_ids", errors)
    figures = _objects(p.get("figures"), "presentation.figures", errors, 3, 6, True)
    kinds = {f.get("kind") for f in figures if isinstance(f.get("kind"), str)}
    if not KINDS <= kinds:
        errors.append("presentation.figures: architecture, module_detail and baseline_comparison are required")
    architectures = set()
    fingerprints = set()
    for figure in figures:
        errors.extend(graph_issues(figure, component_ids))
        fingerprint = hashlib.sha256(canonical({k:figure.get(k) for k in ("nodes","edges")})).hexdigest()
        if fingerprint in fingerprints:
            errors.append("presentation.figures: identical graphs do not replace architecture, detail and baseline views")
        fingerprints.add(fingerprint)
        if figure.get("kind") == "architecture" and isinstance(figure.get("component_ids"),list):
            architectures.update(x for x in figure["component_ids"] if isinstance(x,str))
    if set(component_ids) - architectures:
        errors.append("presentation.figures: architecture view must cover every described component")
    return errors



def validation_issues(dossier, *, target_methods=DEFAULT_COMPARISON_TOTAL, allow_single_proposal=False):
    try:
        if not isinstance(dossier, dict):
            return ["dossier: expected object"]
        ideas = dossier.get("method_ideas")
        if isinstance(ideas, dict) and type(ideas.get("schema_version")) is not int:
            return ["method_ideas.schema_version: integer required"]
        return _validation_issues(dossier, target_methods=target_methods, allow_single_proposal=allow_single_proposal)
    except (TypeError, KeyError, AttributeError, ValueError, RecursionError):
        return ["method_ideas: malformed nested report/graph record; use the documented types"]


def safe_path(path):
    path = Path(os.path.abspath(Path(path).expanduser()))
    for part in [*reversed(path.parents), path]:
        if part.is_symlink():
            raise ValueError("Refusing symlink: " + str(part))
        if part.exists() and part != path and not part.is_dir():
            raise ValueError("Parent is not a directory: " + str(part))
    return path


def immutable_write(path, content):
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not path.is_file() or path.read_bytes() != content:
            raise ValueError("Existing design artifact was modified; refusing overwrite: " + str(path))
        return
    with path.open("xb") as stream:
        stream.write(content)


def wrap(text, columns):
    lines, current, width = [], "", 0
    for char in str(text):
        amount = 2 if unicodedata.east_asian_width(char) in "WF" else 1
        if char == "\n" or (current and width + amount > columns):
            lines.append(current)
            current, width = "", 0
        if char != "\n":
            current += char
            width += amount
    if current:
        lines.append(current)
    return lines or [""]


def svg(fig):
    """Deterministic SVG with real text, explicit legend and non-overlapping DAG boxes."""
    layers = _layers(fig)
    box_w, gap, margin = 310, 70, 85
    width = max(850, 2 * margin + max(len(row) for row in layers) * (box_w + gap) - gap)
    title_lines = wrap(fig["title"], 70)
    coords, labels, ypos = {}, {}, 75 + 24 * len(title_lines)
    lane_order = {"baseline": 0, "shared": 1, "proposal": 2}
    for layer in layers:
        layer = sorted(layer, key=lambda n: (lane_order[n["lane"]], n["id"]))
        heights = []
        for node in layer:
            title, detail = wrap(node["label"], 30), wrap(node["detail"], 40)
            height = 52 + 24 * len(title) + 19 * len(detail)
            labels[node["id"]] = (title, detail)
            heights.append(height)
        row_width = len(layer) * (box_w + gap) - gap
        start = (width - row_width) / 2
        for index, node in enumerate(layer):
            coords[node["id"]] = (start + index * (box_w + gap), ypos, box_w, heights[index])
        ypos += max(heights) + 126
    height = ypos + 20
    title = html.escape(fig["title"])
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
           f'<title id="title">{title}</title>', f'<desc id="desc">{html.escape(fig["alt_text"])}</desc>',
           '<defs><marker id="arrow" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto"><path d="M0,0 L9,3.5 L0,7" fill="#333"/></marker></defs>',
           f'<rect width="{width}" height="{height}" fill="white"/>',
           '<g font-family="Noto Sans CJK JP, Meiryo, sans-serif" fill="#161616">',
           *[f'<text x="{width / 2}" y="{35+24*i}" text-anchor="middle" font-size="20" font-weight="bold">{html.escape(t)}</text>' for i,t in enumerate(title_lines)],
           f'<text x="{width / 2}" y="{51+24*len(title_lines)}" text-anchor="middle" font-size="13">概念図：実線は処理の流れ、破線はフィードバック。性能の実測図ではありません。</text>']
    # Arrows first, so a box never loses text to an overdrawn arrow.
    for edge in fig["edges"]:
        x1, y1, w1, h1 = coords[edge["from"]]
        x2, y2, w2, h2 = coords[edge["to"]]
        feedback = edge["kind"] == "feedback"
        if feedback:
            side = width - 30
            path = f'M{x1+w1},{y1+h1/2} H{side} V{y2+h2/2} H{x2+w2}'
            lx, ly = side - 12, (y1+h1/2+y2+h2/2)/2
        else:
            mid = (y1 + h1 + y2) / 2
            path = f'M{x1+w1/2},{y1+h1} V{mid} H{x2+w2/2} V{y2-4}'
            lx, ly = (x1+w1/2+x2+w2/2)/2, mid - 17
        dash = ' stroke-dasharray="6 5"' if feedback else ''
        out.append(f'<path d="{path}" fill="none" stroke="#333" stroke-width="1.6"{dash} marker-end="url(#arrow)"/>')
        label_lines = wrap(edge["label"], 28)
        # A background rect, instead of paint-order text strokes, also works in CairoSVG.
        label_width = max(sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in line) for line in label_lines) * 6.5 + 10
        label_x = lx - label_width + 5 if feedback else lx - label_width / 2
        out.append(f'<rect x="{label_x}" y="{ly-13}" width="{label_width}" height="{16*len(label_lines)+4}" fill="white"/>')
        for j, label in enumerate(label_lines):
            anchor = 'end' if feedback else 'middle'
            out.append(f'<text x="{lx}" y="{ly+16*j}" font-size="12" text-anchor="{anchor}">{html.escape(label)}</text>')
    for layer in layers:
        for node in layer:
            x, y, w, h = coords[node["id"]]
            title_lines, detail_lines = labels[node["id"]]
            change = {"unchanged": "維持", "added": "追加", "modified": "変更"}[node["change"]]
            lane = {"baseline": "既存法", "proposal": "提案法", "shared": "共通"}[node["lane"]]
            out += [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="#f6f6f6" stroke="#333" stroke-width="{2.4 if node["change"] != "unchanged" else 1.1}"/>',
                    f'<text x="{x+14}" y="{y+22}" font-size="12">{lane}・{change}　{html.escape(node["component_id"] or node["id"])}</text>']
            yy = y + 47
            for line in title_lines:
                out.append(f'<text x="{x+14}" y="{yy}" font-size="17" font-weight="bold">{html.escape(line)}</text>')
                yy += 24
            for line in detail_lines:
                out.append(f'<text x="{x+14}" y="{yy}" font-size="13">{html.escape(line)}</text>')
                yy += 19
    out += ['</g>', '</svg>']
    return "\n".join(out).encode("utf-8")


def md(value):
    """Narrative fields are plain prose. Raw HTML and Markdown control are not accepted."""
    value = html.escape(str(value), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+!|])", r"\\\1", value)


def cell(value):
    return md(value).replace("\n", "<br>")


def code_block(value, language="text"):
    longest = max((len(x) for x in re.findall(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return [fence + language, value, fence, ""]


def render_chapter(dossier, workspace, figure_root, *, required=True, target_methods=5, allow_single_proposal=False):
    if not required and not (isinstance(dossier, dict) and "method_ideas" in dossier):
        return []
    errors = validation_issues(dossier, target_methods=target_methods, allow_single_proposal=allow_single_proposal)
    out = ["", "## 提案手法", ""]
    if errors:
        out += ["**未完成：提案手法章の必須項目に不足があります。** 架空の手法・文献・図・結果では補いません。", ""]
        out += ["- " + md(x) for x in errors[:18]]
        if len(errors) > 18:
            out.append(f"- ほか{len(errors)-18}項目。完全な結果は構造検証で確認してください。")
        return out + [""]
    ideas = dossier["method_ideas"]
    c = _index(ideas["candidates"])[ideas["selection"]["leading_candidate_id"]]
    p = c["presentation"]
    key = design_digest(ideas)
    workspace, figure_root = safe_path(workspace), safe_path(figure_root)
    if figure_root != workspace and workspace not in figure_root.parents:
        raise ValueError("Figure root must be inside this report workspace")
    dest = figure_root / key
    immutable_write(dest / "method-ideas.json", canonical(ideas))
    paths = {}
    for figure in p["figures"]:
        image, source = dest / (figure["id"] + ".svg"), dest / (figure["id"] + ".json")
        immutable_write(image, svg(figure))
        immutable_write(source, canonical(figure))
        paths[figure["id"]] = (image.relative_to(workspace).as_posix(), source.relative_to(workspace).as_posix())
    out += [f"**説明対象：{md(c['id'])} — {md(c['name'])}**", "",
            "設計記述と図の構造チェック済み。新規性・有効性・比較上の優越を認定するものではありません。", "",
            md(p["evidence_scope"]), "", "### ねらいと直感", "", md(p["overview"]), "",
            md(c["core_hypothesis"]), "", md(c["mechanistic_explanation"]), "",
            "### 全体像と具体例", "", md(p["worked_example"]), ""]
    ordered = sorted(p["figures"], key=lambda f: ({"architecture": 0, "module_detail": 1, "baseline_comparison": 2}[f["kind"]], f["id"]))
    def figures(kind):
        rows = []
        for number, figure in enumerate(ordered, 1):
            if figure["kind"] != kind:
                continue
            path, source = paths[figure["id"]]
            rows += [f"![{md(figure['alt_text'])}]({path})", "",
                     f"**図{number}．{md(figure['title'])}**　{md(figure['caption'])}", "",
                     md(figure["explanation"]), "", f"[図{number}の編集用定義]({source})", ""]
        return rows
    out += figures("architecture")
    out += ["### 構成要素の詳細", ""]
    for component in p["components"]:
        out += [f"#### {md(component['id'])}：{md(component['name'])}", "",
                f"**入力：** {md(component['inputs'])}  \n**出力：** {md(component['outputs'])}", "",
                md(component["operation"]), "", "**なぜ必要か：** " + md(component["rationale"]), "",
                "**既存法との差分：** " + md(component["baseline_difference"]), "",
                "**追加コスト：** " + md(component["cost"]), ""]
    out += figures("module_detail")
    out += ["### 記号・定式化とアルゴリズム", ""]
    if p["symbols"]:
        out += ["| 記号 | 意味 | 型・次元・範囲 |", "|---|---|---|"]
        out += [f"| {cell(s['symbol'])} | {cell(s['definition'])} | {cell(s['shape'])} |" for s in p["symbols"]]
        out.append("")
    if text_ok(c.get("mathematical_specification")):
        # Preserve equations verbatim in a bounded code block, portable to every MD reader.
        out += code_block(c["mathematical_specification"], "math")
        out += [md(p["equation_explanation"]), ""]
    else:
        out += [md(p["formalism_note"]), ""]
    if text_ok(c.get("pseudocode")):
        out += ["**擬似コード**", ""] + code_block(c["pseudocode"])
    out += ["### 学習・準備時と推論・実行時", "", "**学習・準備時：** " + md(p["training"]), "",
            "**推論・実行時：** " + md(p["inference"]), "",
            "### 既存法との差分とトレードオフ", "",
            "| 観点 | 既存法 | 提案法 | 代償・成立条件 |", "|---|---|---|---|"]
    out += [f"| {cell(r['aspect'])} | {cell(r['baseline'])} | {cell(r['proposal'])} | {cell(r['tradeoff'])} |" for r in p["differences"]]
    out += [""] + figures("baseline_comparison")
    out += ["### 先行研究からの導入と独自部分", "", md(c["transfer_mapping"]), "", md(c["prior_art_difference"]), "",
            "**新規性の記録：** " + md(c["novelty_status"]) + "（自動認定ではありません）", ""]
    sources = _index(ideas["sources"])
    for sid in dict.fromkeys(c.get("source_ids", []) + c.get("closest_prior_art_source_ids", [])):
        s = sources[sid]
        out += [f"- {md(sid)}：{md(s['title'])}。確認箇所：{md(s['locator'])}。出典の詳細は主張・根拠の台帳を参照。"]
    out += ["", "### 実装への組込みと計算負担", "", md(c["integration_plan"]), "", md(c["resource_tradeoff"]), "",
            "### なぜこの案を詳しく検討するか", "", md(ideas["selection"]["rationale"]), "", md(p["selection_note"]), "",
            f"比較の目安は全{target_methods}手法。現在の比較はベースライン1＋提案候補{len(ideas['candidates'])}。アブレーションを数合わせに使いません。", ""]
    if ideas["comparison_plan"].get("exception_reason"):
        out += ["**比較数の例外理由：** " + md(ideas["comparison_plan"]["exception_reason"]), ""]
    out += ["### 成立条件・反論と設計の改訂", ""]
    for title, key in (("成立条件", "assumptions"), ("主要な反論", "critical_objections"), ("反論を受けた改訂", "revision_actions")):
        out += ["**" + title + "**", ""] + ["- " + md(item) for item in c[key]] + [""]
    out += ["**失敗すると予想される条件：** " + md(c["expected_failure_regime"]), "",
            "### 仮説と検証実験の対応", "",
            "| 仮説 | 対象 | 実験 | 競合する説明 | 棄却・修正する条件 |", "|---|---|---|---|---|"]
    experiments = _index(dossier["experiments"])
    for item in p["verification"]:
        experiment = experiments[item["experiment_id"]]
        status = "未測定（計画）" if experiment.get("status") == "planned" else str(experiment.get("status", "unknown"))
        out.append(f"| {cell(item['hypothesis'])} | {cell(', '.join(item['component_ids']))} | {cell(item['experiment_id'])}：{cell(status)} | {cell(item['alternative_explanation'])} | {cell(item['rejection_condition'])} |")
    return out + ["", "図はこの設計の説明用です。結果の主張は後続の実験記録と結び付け、未実験の利点は仮説として扱います。", ""]


def chapter_for_state(state, workspace, run_dir):
    config = state.get("config", {})
    return render_chapter(state.get("dossier"), workspace, Path(run_dir) / "method-figures", required=method_required(state), target_methods=config.get("target_methods", 5), allow_single_proposal=state.get("execution_contract_version") == 2)


def require_method_report(dossier, state):
    from runtime import Blocked
    if method_required(state) or (isinstance(dossier, dict) and "method_ideas" in dossier):
        errors = validation_issues(dossier, target_methods=state.get("config", {}).get("target_methods", 5), allow_single_proposal=state.get("execution_contract_version") == 2)
        state["method_report_validation"] = {"valid": not errors, "errors": errors, "scope": "structural_only"}
        if errors:
            raise Blocked("Proposed-method chapter is incomplete: " + "; ".join(errors[:8]))


def prepare_preview(state, workspace, run_dir):
    """Render producer diagrams before the reviewer; do not treat them as experiments."""
    if not method_required(state):
        return
    try:
        proposal = state.get("proposal_design") if state.get("execution_contract_version") == 2 else state.get("proposal")
        dossier = json.loads((proposal or {}).get("dossier_json", ""))
    except (ValueError, TypeError):
        state["method_report_preview"] = {"status": "incomplete", "reason": "Producer dossier is not JSON"}
        return
    errors = validation_issues(dossier, target_methods=state["config"].get("target_methods", 5), allow_single_proposal=state.get("execution_contract_version") == 2)
    if errors:
        state["method_report_preview"] = {"status": "incomplete", "errors": errors}
        return
    digest = design_digest(dossier["method_ideas"])
    root = Path(run_dir) / "method-preview" / digest
    lines = render_chapter(dossier, workspace, root / "figures", target_methods=state["config"].get("target_methods", 5), allow_single_proposal=state.get("execution_contract_version") == 2)
    # Rendered chapter uses workspace-relative links. Rebase its preview copy only.
    rel = lambda m: "](" + os.path.relpath(Path(workspace) / m[1], root) + ")"
    body = re.sub(r"\]\(([^)]+)\)", rel, "\n".join(lines))
    immutable_write(root / "chapter.md", body.encode("utf-8"))
    state["method_report_preview"] = {"status": "rendered", "path": (root / "chapter.md").relative_to(workspace).as_posix(), "design_sha256": digest, "scope": "conceptual design; not empirical or visual-review evidence"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for action in ("validate", "render"):
        sub = commands.add_parser(action)
        sub.add_argument("file", type=Path, help="Scholarly dossier with method_ideas")
        sub.add_argument("--target-methods", type=int, default=5, choices=range(3, 21))
        if action == "render":
            sub.add_argument("--out", type=Path, required=True)
            sub.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        source = safe_path(args.file)
        if source.stat().st_size > MAX_DOCUMENT_BYTES:
            raise ValueError("Dossier exceeds 5 MB")
        dossier = json.loads(source.read_text("utf-8"))
        errors = validation_issues(dossier, target_methods=args.target_methods)
        if args.command == "validate":
            print(json.dumps({"valid": not errors, "errors": errors, "scope": "structural_only"}, ensure_ascii=False, indent=2))
            return int(bool(errors))
        if args.strict and errors:
            print(json.dumps({"valid": False, "errors": errors}, ensure_ascii=False), file=sys.stderr)
            return 1
        dest = safe_path(args.out)
        if dest.exists():
            raise ValueError("Refusing to overwrite an existing report")
        lines = render_chapter(dossier, dest.parent, dest.parent / "method-figures", target_methods=args.target_methods)
        immutable_write(dest, ("# 提案手法の説明\n" + "\n".join(lines) + "\n").encode("utf-8"))
        print(dest)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
