"""Pure structural checks for progressive interaction Cases. No I/O or model calls.

Checks constrain claims to recorded evidence; they cannot prove that the evidence
or its semantic interpretation is true. Diagnostics never include note contents.
"""
import re


ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\Z")
SIGNALS = {"none", "commit_request", "push_request", "checkpoint_request",
           "downstream_use", "reuse_request", "scope_narrowing", "repeated_correction",
           "revert_request", "explicit_acceptance", "explicit_rejection"}
POSITIVE = {"commit_request", "push_request", "downstream_use", "reuse_request",
            "scope_narrowing", "explicit_acceptance"}
STRONG = {"downstream_use", "reuse_request", "explicit_acceptance"}
NEGATIVE = {"repeated_correction", "revert_request", "explicit_rejection"}


def sequence_issues(data):
    issues = []

    def issue(code, location, action):
        issues.append({"code": code, "location": location, "action": action})

    def shape(value, keys, location):
        if not isinstance(value, dict) or set(value) != set(keys.split()):
            issue("invalid_shape", location, "Restore the documented fields without inventing missing evidence.")
            return False
        return True

    def text(value, location, nullable=False):
        if value is None and nullable:
            return True
        if (not isinstance(value, dict) or set(value) != {"summary", "excerpt"}
                or not isinstance(value.get("summary"), str) or not value["summary"].strip()
                or (value.get("excerpt") is not None and not isinstance(value["excerpt"], str))):
            issue("invalid_text", location, "Use a summary and an optional sanitized excerpt; unknown is not a quotation.")
            return False
        return True

    def string(value, location, nullable=False):
        if value is None and nullable:
            return True
        if not isinstance(value, str) or not value.strip():
            issue("missing_context", location, "State known context or use null where allowed.")
            return False
        return True

    ids = set()

    def identity(value, location):
        if not isinstance(value, str) or not ID.fullmatch(value):
            issue("invalid_id", location, "Use a stable opaque identifier, not a path or personal identifier.")
        elif value in ids:
            issue("duplicate_id", location, "Check the original sequence before disambiguating identifiers.")
        else:
            ids.add(value)

    def enum(value, choices, location):
        if not isinstance(value, str) or value not in choices:
            issue("invalid_value", location, "Use one of the documented values.")
            return False
        return True

    def references(value, location):
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
            issue("invalid_references", location, "Provide an array of existing step identifiers.")
            return []
        if len(value) != len(set(value)):
            issue("duplicate_evidence", location, "Do not count the same observation twice.")
        return value

    if not shape(data, "version context request steps latest_output_id state outcome acceptance acceptance_evidence_ids assessments repairs transfer_use", "/"):
        return issues
    if type(data["version"]) is not int or data["version"] != 2:
        issue("invalid_version", "/version", "Use version 2; do not silently convert a legacy Case.")
    if shape(data["context"], "purpose audience deliverable constraints scope", "/context"):
        for key, value in data["context"].items():
            string(value, "/context/" + key, nullable=key != "scope")
    text(data["request"], "/request")
    string(data["transfer_use"], "/transfer_use")
    enum(data["state"], ("open", "completed", "abandoned"), "/state")
    enum(data["outcome"], ("unverified", "partial", "verified", "rejected"), "/outcome")
    enum(data["acceptance"], ("unknown", "accepted", "rejected"), "/acceptance")
    if not isinstance(data["steps"], list):
        issue("invalid_steps", "/steps", "Keep the observed steps in an ordered array.")
        return issues

    steps, outputs, latest = {}, set(), None
    for i, step in enumerate(data["steps"]):
        loc = f"/steps/{i}"
        if not isinstance(step, dict):
            issue("invalid_step", loc, "Restore the documented step structure.")
            continue
        kind = step.get("kind")
        if not enum(kind, ("output", "correction", "action", "verification"), loc + "/kind"):
            continue
        extra = "change" if kind == "output" else "result" if kind == "verification" else "signal group_id"
        if not shape(step, "id kind actor target_id content " + extra, loc):
            continue
        identity(step["id"], loc + "/id")
        enum(step["actor"], ("user", "assistant", "tool"), loc + "/actor")
        text(step["content"], loc + "/content")
        target = step["target_id"]
        if target is not None and (not isinstance(target, str) or target not in outputs):
            issue("invalid_target", loc + "/target_id", "Target an earlier output; if the source is unknown use null, not a guessed order.")
        if kind == "output":
            text(step["change"], loc + "/change", nullable=True)
            if isinstance(step["id"], str):
                outputs.add(step["id"])
                latest = step["id"]
        elif kind == "verification":
            enum(step["result"], ("passed", "failed", "inconclusive"), loc + "/result")
        else:
            enum(step["signal"], SIGNALS, loc + "/signal")
            if not isinstance(step["group_id"], str) or not ID.fullmatch(step["group_id"]):
                issue("invalid_group", loc + "/group_id", "Group correlated actions, including commit and push in the same delivery episode.")
        if isinstance(step["id"], str):
            steps[step["id"]] = step
    if data["latest_output_id"] != latest:
        issue("latest_output_mismatch", "/latest_output_id", "Identify the latest recorded output, or null if no output is known.")
    if data["outcome"] == "verified" and not any(
            s.get("kind") == "verification" and s.get("result") == "passed"
            and s.get("target_id") == latest and latest is not None for s in steps.values()):
        issue("unsupported_verification", "/outcome", "Record a performed check on the latest output, or retain an unverified/partial outcome.")
    if data["outcome"] == "verified" and any(
            s.get("kind") == "verification" and s.get("result") == "failed"
            and s.get("target_id") == latest and latest is not None for s in steps.values()):
        issue("conflicting_verification", "/outcome", "Inspect failed checks on this output; retain partial/rejected status while failures remain recorded for it.")

    acceptance_ids = references(data["acceptance_evidence_ids"], "/acceptance_evidence_ids")
    if data["acceptance"] != "unknown":
        required = "explicit_acceptance" if data["acceptance"] == "accepted" else "explicit_rejection"
        if not acceptance_ids or not all(
                ref in steps and steps[ref].get("actor") == "user"
                and steps[ref].get("signal") == required
                and steps[ref].get("target_id") == latest and latest is not None
                for ref in acceptance_ids):
            issue("unsupported_acceptance", "/acceptance", "Implicit adoption belongs in assessments; keep explicit acceptance unknown without matching user evidence.")
        elif acceptance_ids:
            ordered = list(steps)
            last_cited = max(ordered.index(ref) for ref in acceptance_ids)
            contrary = NEGATIVE if data["acceptance"] == "accepted" else {"explicit_acceptance"}
            if any(s.get("actor") == "user" and s.get("target_id") == latest
                   and s.get("signal") in tuple(contrary)
                   for s in list(steps.values())[last_cited + 1:]):
                issue("stale_acceptance", "/acceptance", "Reassess later contrary user evidence; preserve the earlier action without claiming it remains current acceptance.")
    elif acceptance_ids:
        issue("unexpected_acceptance_evidence", "/acceptance_evidence_ids", "Keep evidence on its actual output; unknown latest acceptance has no explicit acceptance references.")

    if not isinstance(data["assessments"], list):
        issue("invalid_assessments", "/assessments", "Keep interpretations separate from the ordered observations.")
        return issues
    for i, assessment in enumerate(data["assessments"]):
        loc = f"/assessments/{i}"
        if not shape(assessment, "id target_id aspect judgment evidence_ids counterevidence_ids rationale", loc):
            continue
        identity(assessment["id"], loc + "/id")
        target = assessment["target_id"]
        if not isinstance(target, str) or target not in outputs:
            issue("invalid_assessment_target", loc + "/target_id", "Attach the interpretation to an existing output and a specific aspect.")
        string(assessment["aspect"], loc + "/aspect")
        text(assessment["rationale"], loc + "/rationale")
        judgment = assessment["judgment"]
        enum(judgment, ("supported", "tentative", "unknown", "contradicted"), loc + "/judgment")
        evidence = references(assessment["evidence_ids"], loc + "/evidence_ids")
        counter = references(assessment["counterevidence_ids"], loc + "/counterevidence_ids")
        if set(evidence) & set(counter):
            issue("conflicting_evidence", loc, "Distinguish the observation's supported and opposed claims.")
        for ref in evidence + counter:
            if ref not in steps or steps[ref].get("target_id") != target:
                issue("evidence_target_mismatch", loc, "Use actual observations referring to this output; do not transfer another version's reception.")
        positive = [steps[ref] for ref in evidence if ref in steps
                    and steps[ref].get("actor") == "user"
                    and steps[ref].get("signal") in tuple(POSITIVE)
                    and steps[ref].get("target_id") == target]
        negative = [steps[ref] for ref in evidence + counter if ref in steps
                    and steps[ref].get("actor") == "user"
                    and steps[ref].get("signal") in tuple(NEGATIVE)
                    and steps[ref].get("target_id") == target]
        if judgment in ("supported", "tentative") and not positive:
            issue("unsupported_adoption", loc, "Require a targeted user action; autonomous actions and checks do not establish adoption.")
        if judgment == "supported" and (counter or not any(s["signal"] in STRONG for s in positive)):
            issue("overstated_adoption", loc, "Commit/push or narrowing alone is tentative; consider counterevidence and actual reuse/downstream use.")
        if judgment == "contradicted" and not negative:
            issue("unsupported_contradiction", loc, "Record a targeted correction/reversal instead of inferring rejection from silence.")
        cited = set(evidence + counter)
        if judgment in ("supported", "tentative") and any(
                s.get("actor") == "user" and s.get("signal") in tuple(NEGATIVE)
                and s.get("target_id") == target and ref not in cited
                for ref, s in steps.items()):
            issue("unconsidered_counterevidence", loc, "Inspect later corrections or reversals on this output; explain their scope before reusing the interpretation.")

    if not isinstance(data["repairs"], list):
        issue("invalid_repairs", "/repairs", "Keep concise evidence-backed corrections to the memory itself.")
        return issues
    for i, repair in enumerate(data["repairs"]):
        loc = f"/repairs/{i}"
        if not shape(repair, "id reason evidence changes", loc):
            continue
        identity(repair["id"], loc + "/id")
        text(repair["reason"], loc + "/reason")
        text(repair["evidence"], loc + "/evidence")
        changes = repair["changes"]
        if not isinstance(changes, list) or not changes:
            issue("missing_repair_changes", loc, "Record only necessary sanitized before/after changes, never an unsanitized backup.")
            continue
        for j, change in enumerate(changes):
            at = f"{loc}/changes/{j}"
            if shape(change, "location before after", at):
                location = change["location"]
                if not isinstance(location, str) or not re.fullmatch(r"/(?:[A-Za-z0-9_/-]+)", location):
                    issue("invalid_repair_location", at, "Use a JSON pointer inside the Case, not a filesystem path.")
                if change["before"] == change["after"]:
                    issue("empty_repair", at, "Do not append no-op or timestamp-only maintenance records.")
    return issues
