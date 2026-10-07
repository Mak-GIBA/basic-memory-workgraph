"""Create research workspaces and check evidence/decision contracts, not truth."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import urllib.parse

from literature import ResearchError, checked_dir

SOURCE_TYPES = {"paper", "preprint", "official_doc", "standard", "repository", "experiment", "secondary"}
READ_LEVELS = {"metadata", "abstract", "relevant_sections", "full_text"}
CLAIM_STATUSES = {"observed", "reported", "inferred", "hypothesis", "unknown"}


def blank_dossier(question: str) -> dict:
    return {"schema_version": 1, "question": question, "scope": "TODO:対象・利用条件・除外範囲",
            "checked_as_of": dt.date.today().isoformat(), "constraints": [], "sources": [], "claims": [],
            "candidates": [], "comparison": [], "experiments": [],
            "decision": {"status": "provisional", "candidate_id": None, "rationale": "TODO:比較後に記入",
                         "claim_ids": [], "unresolved": [], "revisit_when": [],
                         "accepted_by": None, "accepted_at": None}}


def create_run(root: Path, slug: str, question: str, templates: Path) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", slug):
        raise ResearchError("Slug must be 1-64 lowercase letters, digits, or hyphens; start with a letter/digit.")
    if not question.strip() or len(question) > 8000:
        raise ResearchError("Provide a non-empty question of at most 8000 characters.")
    root = checked_dir(root, create=True)
    target = root / slug
    if target.exists() or target.is_symlink():
        raise ResearchError("Research workspace already exists; choose another slug. Existing work is never overwritten.")
    target.mkdir(mode=0o700)
    try:
        for source, dest in (("report.md", "design-research.md"), ("decision.md", "decision.md")):
            text = (templates / source).read_text("utf-8")
            (target / dest).write_text(text.replace("{{QUESTION}}", question).replace("{{DATE}}", dt.date.today().isoformat()), "utf-8")
        (target / "evidence.json").write_text(json.dumps(blank_dossier(question), ensure_ascii=False, indent=2) + "\n", "utf-8")
        (target / "research-log.json").write_text(json.dumps({"schema_version": 1, "searches": [], "read_sources": [],
                                                              "failed_requests": [], "stop_reason": None}, indent=2) + "\n", "utf-8")
    except BaseException:
        shutil.rmtree(target)
        raise
    return target


def validate_dossier(data) -> dict:
    errors, warnings = [], []

    def error(where, message):
        errors.append(f"{where}: {message}")

    def text(value, where, required=True):
        if not isinstance(value, str) or (required and not value.strip()):
            error(where, "must be a non-empty string" if required else "must be a string")
            return False
        if required and re.match(r"^(TODO|TBD|PLACEHOLDER)(?:\b|:)", value, flags=re.I):
            error(where, "replace the placeholder with a finding, assumption, or explicit unknown")
            return False
        return True

    def array(parent, key, where):
        value = parent.get(key)
        if not isinstance(value, list):
            error(where + "." + key, "must be an array")
            return []
        return value

    def enum(parent, key, allowed, where):
        value = parent.get(key)
        if not isinstance(value, str) or value not in allowed:
            error(where + "." + key, "must be one of " + ", ".join(sorted(allowed)))
            return None
        return value

    def date(value, where):
        if not isinstance(value, str):
            error(where, "must be an ISO date or datetime")
            return
        try:
            dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            error(where, "must be an ISO date or datetime")

    def index(items, where):
        out = {}
        for i, row in enumerate(items):
            location = f"{where}[{i}]"
            if not isinstance(row, dict):
                error(location, "must be an object")
                continue
            rid = row.get("id")
            if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", rid):
                error(location + ".id", "must be a short identifier starting with a letter")
            elif rid in out:
                error(location + ".id", "duplicate ID")
            else:
                out[rid] = row
        return out

    if not isinstance(data, dict):
        return {"valid": False, "errors": ["root: must be an object"], "warnings": [], "scope": "structural checks only"}
    if data.get("schema_version") != 1 or isinstance(data.get("schema_version"), bool):
        error("schema_version", "must be 1")
    text(data.get("question"), "question")
    text(data.get("scope"), "scope")
    date(data.get("checked_as_of"), "checked_as_of")
    constraints = index(array(data, "constraints", "root"), "constraints")
    sources = index(array(data, "sources", "root"), "sources")
    claims = index(array(data, "claims", "root"), "claims")
    candidates = index(array(data, "candidates", "root"), "candidates")
    experiments = index(array(data, "experiments", "root"), "experiments")
    comparisons = array(data, "comparison", "root")
    for rid, row in constraints.items():
        text(row.get("text"), f"constraint {rid}.text")
        enum(row, "kind", {"hard", "soft"}, f"constraint {rid}")
    for rid, row in sources.items():
        where = f"source {rid}"
        text(row.get("title"), where + ".title")
        enum(row, "source_type", SOURCE_TYPES, where)
        enum(row, "read_level", READ_LEVELS, where)
        review = enum(row, "peer_review_status", {"unverified", "verified", "not_applicable"}, where)
        if review == "verified":
            text(row.get("peer_review_evidence"), where + ".peer_review_evidence")
        date(row.get("retrieved_at"), where + ".retrieved_at")
        text(row.get("study_id"), where + ".study_id")
        enum(row, "correction_status", {"not_checked", "no_notice_found", "notice_found", "not_applicable"}, where)
        url, path = row.get("url"), row.get("local_path")
        valid_url = False
        if isinstance(url, str):
            try:
                u = urllib.parse.urlsplit(url)
                valid_url = u.scheme in {"https", "http"} and bool(u.hostname) and not (u.username or u.password)
            except ValueError:
                pass
        valid_path = isinstance(path, str) and path and not Path(path).is_absolute() and ".." not in Path(path).parts
        if not (valid_url or valid_path):
            error(where, "requires a public source URL or a workspace-relative local_path")
        if row.get("correction_status") == "notice_found":
            text(row.get("correction_note"), where + ".correction_note")
            warnings.append(where + ": correction/retraction notice found; assess impact before relying on this source")
        if row.get("source_type") == "preprint" and review == "verified":
            warnings.append(where + ": link the reviewed publication/version explicitly; arXiv hosting alone does not establish review")

    def claim_refs(row, where, require=False):
        refs = array(row, "claim_ids", where)
        for ref in refs:
            if not isinstance(ref, str) or ref not in claims:
                error(where + ".claim_ids", "references an unknown claim")
        if require and not refs:
            error(where + ".claim_ids", "at least one claim reference is required")
        return [ref for ref in refs if isinstance(ref, str) and ref in claims]

    for rid, row in claims.items():
        where = f"claim {rid}"
        text(row.get("statement"), where + ".statement")
        status = enum(row, "status", CLAIM_STATUSES, where)
        confidence = enum(row, "confidence", {"unassessed", "low", "medium", "high"}, where)
        text(row.get("context"), where + ".context")
        array(row, "limitations", where)
        evidence = array(row, "evidence", where)
        supporting = []
        for ev in evidence:
            if not isinstance(ev, dict):
                error(where + ".evidence", "each reference must be an object")
                continue
            sid = ev.get("source_id")
            relation = enum(ev, "relation", {"supports", "challenges", "mixed", "context"}, where + ".evidence")
            if not isinstance(sid, str) or sid not in sources:
                error(where + ".evidence", "references an unknown source")
                continue
            text(ev.get("locator"), where + ".evidence.locator")
            if relation == "supports":
                supporting.append(sources[sid])
        if status in {"observed", "reported", "inferred"} and not supporting:
            error(where, "requires supporting evidence; otherwise mark it hypothesis/unknown")
        if confidence == "high":
            if status in {"hypothesis", "unknown"}:
                error(where, "a hypothesis/unknown cannot have high confidence")
            if not any(s.get("read_level") in ("relevant_sections", "full_text") for s in supporting):
                error(where, "high confidence requires at least one supporting source read beyond metadata/abstract")
        if status == "observed" and not any(s.get("source_type") == "experiment" for s in supporting):
            error(where, "observed requires an experiment artifact; published experimental results are reported, not locally observed")
        if supporting and all(s.get("read_level") == "metadata" for s in supporting):
            warnings.append(where + ": metadata-only support; use only for bibliographic facts, not method effectiveness")
        if supporting and len({str(s.get("study_id")) for s in supporting}) < len(supporting):
            warnings.append(where + ": multiple source records belong to the same study; do not count them as independent replication")

    hard_ids = {rid for rid, c in constraints.items() if c.get("kind") == "hard"}
    baseline = 0
    evaluations = {}
    if len(candidates) < 2:
        error("candidates", "compare at least two substantive options, including a baseline")
    for rid, row in candidates.items():
        where = f"candidate {rid}"
        text(row.get("name"), where + ".name")
        text(row.get("summary"), where + ".summary")
        if not isinstance(row.get("baseline"), bool):
            error(where + ".baseline", "must be a boolean")
        baseline += row.get("baseline") is True
        evaluated = {}
        for evaluation in array(row, "hard_constraints", where):
            if not isinstance(evaluation, dict):
                error(where, "hard constraint evaluation must be an object")
                continue
            cid = evaluation.get("constraint_id")
            if not isinstance(cid, str) or cid not in hard_ids:
                error(where, "hard constraint evaluation references an unknown hard constraint")
                continue
            if cid in evaluated:
                error(where, "duplicate hard constraint evaluation")
            result = enum(evaluation, "result", {"pass", "fail", "unknown"}, where + ".hard_constraints")
            text(evaluation.get("reason"), where + ".hard_constraints.reason")
            claim_refs(evaluation, where + ".hard_constraints", require=result in {"pass", "fail"})
            evaluated[cid] = result
        if set(evaluated) != hard_ids:
            error(where, "evaluate every hard constraint; use unknown rather than silently omitting one")
        evaluations[rid] = evaluated
    if baseline == 0:
        error("candidates", "include a simplest viable/current-system baseline")
    if not comparisons:
        error("comparison", "include common-criteria findings; unmeasured values must remain unknown or estimated")
    for i, row in enumerate(comparisons):
        where = f"comparison[{i}]"
        if not isinstance(row, dict):
            error(where, "must be an object")
            continue
        text(row.get("criterion"), where + ".criterion")
        text(row.get("finding"), where + ".finding")
        basis = enum(row, "basis", {"measured", "reported", "estimated", "unknown"}, where)
        cid = row.get("candidate_id")
        if not isinstance(cid, str) or cid not in candidates:
            error(where, "references an unknown candidate")
        refs = claim_refs(row, where, require=basis in {"measured", "reported"})
        if basis == "measured" and not any(claims[r].get("status") == "observed" for r in refs):
            error(where, "measured comparisons require an observed claim backed by a local experiment artifact")
        if basis == "estimated":
            text(row.get("assumptions"), where + ".assumptions")
    covered = {}
    for row in comparisons:
        if isinstance(row, dict) and isinstance(row.get("criterion"), str) and isinstance(row.get("candidate_id"), str):
            covered.setdefault(row["criterion"], set()).add(row["candidate_id"])
    for criterion, candidate_ids in covered.items():
        if candidate_ids != set(candidates):
            error("comparison", f"criterion {criterion!r} must cover every candidate (unknown is allowed)")
    for rid, row in experiments.items():
        where = f"experiment {rid}"
        text(row.get("hypothesis"), where + ".hypothesis")
        enum(row, "status", {"planned", "executed"}, where)
        text(row.get("acceptance"), where + ".acceptance")
        for key in ("controls", "metrics", "candidate_ids"):
            entries = array(row, key, where)
            if not entries:
                error(where + "." + key, "must not be empty")
            if key == "candidate_ids":
                for cid in entries:
                    if not isinstance(cid, str) or cid not in candidates:
                        error(where + ".candidate_ids", "references an unknown candidate")
        if row.get("status") == "executed" and not array(row, "artifacts", where):
            error(where, "executed experiments require artifacts; a proposed PoC is not a measured result")
    decision = data.get("decision")
    if not isinstance(decision, dict):
        error("decision", "must be an object")
    else:
        status = enum(decision, "status", {"provisional", "proposed", "accepted", "deferred"}, "decision")
        text(decision.get("rationale"), "decision.rationale")
        refs = claim_refs(decision, "decision", require=status in {"proposed", "accepted"})
        array(decision, "unresolved", "decision")
        array(decision, "revisit_when", "decision")
        cid = decision.get("candidate_id")
        if cid is not None and (not isinstance(cid, str) or cid not in candidates):
            error("decision.candidate_id", "references an unknown candidate")
        if status in {"proposed", "accepted"} and cid is None:
            error("decision", "proposed/accepted requires a candidate")
        selected = evaluations.get(cid, {}) if isinstance(cid, str) else {}
        if "fail" in selected.values():
            error("decision", "cannot select a candidate that fails a hard constraint")
        if status in {"proposed", "accepted"} and "unknown" in selected.values():
            error("decision", "unverified hard constraints require a provisional or deferred decision")
        if status == "accepted":
            text(decision.get("accepted_by"), "decision.accepted_by")
            date(decision.get("accepted_at"), "decision.accepted_at")
            warnings.append("decision: acceptance metadata must correspond to actual human approval; the validator cannot authenticate it")
        if status in {"provisional", "deferred"}:
            warnings.append("decision: unresolved evidence/constraints remain; do not present this as a proven optimum")
    return {"valid": not errors, "errors": errors, "warnings": warnings,
            "scope": "Structural checks only. This does not verify source contents, scientific validity, or the authenticity of human approval."}
