"""Start a fresh bounded research run from an immutable earlier run (stdlib only).

Historical results are context, never new execution receipts. No dependencies are
installed and no source, old report, settings or accepted decision is overwritten.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

MAX_BYTES = 2 * 1024 * 1024
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")


def read_file(path: Path, root: Path) -> bytes:
    root = root.absolute()
    path = Path(os.path.abspath(path))
    if not path.is_relative_to(root):
        raise ValueError("Input must stay within the selected project")
    for node in (path, *path.parents):
        if node.is_symlink():
            raise ValueError("Symlink inputs are not supported")
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("Input is missing, not a file, or exceeds 2 MiB: " + str(path))
    data = path.read_bytes()
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Input is empty or exceeds 2 MiB")
    data.decode("utf-8")
    return data


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_previous(project: Path, previous: str, slug: str) -> dict:
    """Read the exact run, not a mutable topic-level report from a different run."""
    project = Path(os.path.abspath(project.expanduser()))
    path = Path(previous).expanduser()
    path = path if path.is_absolute() else project / path
    path = Path(os.path.abspath(path))
    raw = read_file(path, project)
    state = json.loads(raw)
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise ValueError("Unsupported previous state schema")
    if not isinstance(state.get("config"), dict) or state["config"].get("mode") != "research":
        raise ValueError("Use a previous research run, not an application-fix run")
    run_id = state.get("run_id")
    if path.name != "state.json" or path.parent.name != run_id or path.parent.parent.name != "runs":
        raise ValueError("--prior-run must be the exact runs/<run-id>/state.json")
    workspace = path.parents[2]
    if workspace.parent != project / "docs/design-research":
        raise ValueError("Previous run must be within docs/design-research/<topic>")
    if not SLUG.fullmatch(slug) or slug == workspace.name:
        raise ValueError("Use a new safe slug; never overwrite the earlier topic report")
    if (project / "docs/design-research" / slug).exists():
        raise ValueError("Reassessment needs a new topic directory")
    if state.get("status") != "research_complete" or not isinstance(state.get("dossier"), dict):
        raise ValueError("Previous research is not complete; use resume for an interrupted run")
    report = path.parent / "reports/report.md"
    if not report.is_file():
        report = path.parent / "reports/design-research.md"  # owned legacy snapshot
    report_raw = read_file(report, project)
    return {
        "schema_version": 1, "run_id": run_id,
        "previous_state": path.relative_to(project).as_posix(),
        "previous_state_sha256": digest(raw),
        "previous_report": report.relative_to(project).as_posix(),
        "previous_report_sha256": digest(report_raw),
        "previous_status": state["status"],
        "previous_source": state.get("expected_source", {}),
        "previous_dossier": state["dossier"],
        "previous_report_text": report_raw.decode("utf-8"),
        "evidence_status": "historical_context_only",
    }


def assert_unchanged(context: dict, project: Path) -> None:
    for kind in ("state", "report"):
        path = project / context["previous_" + kind]
        if digest(read_file(path, project)) != context["previous_" + kind + "_sha256"]:
            raise ValueError("Earlier research changed during reassessment; start a fresh run")


def snapshot_requirements(args, project: Path, run_dir: Path, workspace: Path) -> dict | None:
    name = getattr(args, "requirements", None)
    if not name:
        return None
    path = Path(name)
    path = path if path.is_absolute() else project / path
    path = Path(os.path.abspath(path))
    if path.is_relative_to(workspace):
        raise ValueError("Requirements must not be a generated research output")
    if any(part in {'.git', '.ssh', '.aws'} or part.startswith('.env') for part in path.relative_to(project).parts):
        raise ValueError("Sensitive files must not be used as requirements")
    raw = read_file(path, project)
    target = run_dir / "inputs/bound-requirements.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    # Requirements are explicit project input, not sent to search or any new service.
    with target.open("xb") as stream:
        stream.write(raw)
    target.chmod(0o600)
    return {"project_path": path.relative_to(project).as_posix(),
            "snapshot": target.relative_to(workspace).as_posix(), "sha256": digest(raw)}


def check_requirements(context: dict, project: Path, workspace: Path) -> None:
    for path in (project / context["project_path"], workspace / context["snapshot"]):
        if digest(read_file(path, project)) != context["sha256"]:
            raise ValueError("Requirements or their research snapshot changed; rerun research")


def _quality_issues(dossier: dict, state: dict) -> list[str]:
    if not state.get("reassessment_context"):
        return []
    out = []
    review = dossier.get("reassessment")
    if not isinstance(review, dict):
        return ["reassessment: explain changed requirements, old evidence and new alternatives"]
    for field in ("changed_conditions", "retained_findings", "invalidated_findings",
                  "comparability", "decision_delta", "next_experiment"):
        if not isinstance(review.get(field), str) or not review[field].strip():
            out.append("reassessment." + field + ": substantive explanation required")
    rows = review.get("candidate_roles", [])
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        return out + ["reassessment.candidate_roles must be a list of objects"]
    candidates = {r.get("id") for r in dossier.get("candidates", []) if isinstance(r, dict) and isinstance(r.get("id"), str)}
    experiments = {r.get("id") for r in dossier.get("experiments", []) if isinstance(r, dict) and isinstance(r.get("id"), str)}
    seen = set()
    for row in rows:
        cid = row.get("candidate_id")
        if not isinstance(cid, str) or cid not in candidates or cid in seen:
            out.append("candidate_roles: missing, duplicate or unknown candidate ID")
        if isinstance(cid, str):
            seen.add(cid)
        if row.get("role") not in {"incumbent", "incremental", "distant", "alternative", "simpler"}:
            out.append("candidate_roles: unknown role")
        if not isinstance(row.get("mechanism"), str) or not row["mechanism"].strip():
            out.append("candidate_roles: mechanism required")
    if seen != candidates:
        out.append("candidate_roles: cover every candidate exactly once")
    incumbents = [r for r in rows if r.get("role") == "incumbent"]
    distant = [r for r in rows if r.get("role") == "distant"]
    context = state.get("reassessment_context")
    previous = context.get("previous_dossier", {}) if isinstance(context, dict) else {}
    if previous:
        old_candidates = {r["id"] for r in previous.get("candidates", [])
                          if isinstance(r, dict) and isinstance(r.get("id"), str)}
        selected = previous.get("decision", {}).get("candidate_id")
        for row in incumbents:
            old_id = row.get("previous_candidate_id")
            if not isinstance(old_id, str) or old_id not in old_candidates:
                out.append("Incumbent must link to a real previous_candidate_id")
            elif selected and old_id != selected:
                out.append("Incumbent must retain the previous selected candidate for comparison")
    if not incumbents or not distant:
        out.append("Compare the previous incumbent and at least one distant mechanism")
    incumbent_mechanisms = {r.get("mechanism", "").strip().casefold() for r in incumbents
                            if isinstance(r.get("mechanism"), str)}
    for row in distant:
        mechanism = row.get("mechanism", "")
        if not isinstance(mechanism, str) or mechanism.strip().casefold() in incumbent_mechanisms:
            out.append("Distant alternative cannot merely rename the incumbent mechanism")
        for field in ("difference", "falsification", "command", "prerequisites"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                out.append("Distant alternative needs " + field)
        if not isinstance(row.get("experiment_id"), str) or row["experiment_id"] not in experiments:
            out.append("Distant alternative must link to a real planned/executed dossier experiment")
    target = state.get("config", {}).get("target_methods", 5)
    if not isinstance(target, int) or isinstance(target, bool) or not 3 <= target <= 20:
        return out + ["Invalid comparison target"]
    if len(candidates) < target and not str(review.get("comparison_exception", "")).strip():
        out.append("Explain why fewer than the approximate five methods are useful/feasible")
    return out


def quality_issues(dossier, state):
    try:
        if not isinstance(dossier, dict) or not isinstance(state, dict):
            return ["Expected a dossier and state object"]
        return _quality_issues(dossier, state)
    except (TypeError, AttributeError, KeyError, ValueError) as exc:
        return ["Malformed report/reassessment fields: " + str(exc)]


def main(argv=None) -> int:
    if os.environ.get("DR_GAN_CHILD"):
        raise ValueError("Recursive harness invocation refused inside a child role")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".")
    parser.add_argument("--prior-run", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--brief", required=True, help="Changed requirements or reason for a new search")
    args, extra = parser.parse_known_args(argv)
    if not args.brief.strip():
        parser.error("A nonempty reassessment reason is required")
    project = Path(os.path.abspath(Path(args.project).expanduser()))
    context = load_previous(project, args.prior_run, args.slug)
    context["change_request"] = args.brief
    import harness
    # Reuse the same parser, sandbox, budgets and execution loop, not a second engine.
    parsed = harness.parser().parse_args([
        "research", "--project", str(project), "--slug", args.slug,
        "--brief", args.brief, "--reader-friendly", *extra])
    if not 1 <= parsed.max_iterations <= 5 or parsed.phase_timeout < 1:
        parser.error("Keep the existing 1–5 iteration and positive timeout limits")
    if parsed.project != str(project) or parsed.slug != args.slug or parsed.brief != args.brief:
        parser.error("Reassessment identity cannot be overridden")
    assert_unchanged(context, project)
    parsed.reassessment_context = context
    import signal
    from runtime import Cancelled
    def stopped(signum, frame):
        raise Cancelled(f"Interrupted by signal {signum}")
    previous_handlers = {s: signal.signal(s, stopped) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        return harness.execution(parsed)
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        assert_unchanged(context, project)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as exc:
        print("blocked: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
