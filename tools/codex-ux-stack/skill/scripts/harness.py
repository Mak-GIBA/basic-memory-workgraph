#!/usr/bin/env python3
"""Screenshot-first Codex generator/evaluator orchestration (stdlib only)."""
from __future__ import annotations

import argparse
import collections
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib

HERE = Path(__file__).resolve().parent
VERSION = "1.1.0"
VIEWPORTS = {"desktop": (1440, 900), "tablet": (768, 1024), "mobile": (390, 844)}
PERSPECTIVES = ["first_time", "mistake", "hurried", "skips_explanation"]
STATES = ["normal", "empty", "invalid_input", "cancel", "back", "double_click",
          "loading", "success", "failure"]
SEVERITIES = ["Critical", "High", "Medium", "Low"]
REPORTS = ["ui-ux-review.md", "ui-ux-reference-apps.md", "ui-ux-fix-report.md"]


class Blocked(Exception):
    pass


class Cancelled(Exception):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def log(message):
    print(f"[UX-GAN] {message}", flush=True)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex[:8])
    try:
        with tmp.open("w", encoding="utf-8") as f:
            os.chmod(tmp, 0o600)
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(argv, cwd=None, timeout=30, env=None):
    try:
        return subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Blocked(f"Command failed: {argv[0]}: {e}") from e


def runtime_root():
    if os.environ.get("UX_GAN_RUNTIME"):
        return Path(os.environ["UX_GAN_RUNTIME"]).resolve()
    config = HERE.parent / "runtime.json"
    if config.exists():
        return Path(json.loads(config.read_text())["runtime"]).resolve()
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "ux-stack/runtime"


def design_guidance():
    """Use the harness's own bundle; source checkouts use the distribution's canonical files."""
    root = HERE.parent / "references/design"
    try:
        if root.exists():
            spec = json.loads((root / "index.json").read_text(encoding="utf-8"))
        else:
            distribution = HERE.parents[1]
            if not (distribution / "install_ux_stack.py").is_file():
                raise Blocked("Missing bundled design references; update the owned harness with --force")
            spec = json.loads((distribution / "sources.json").read_text(encoding="utf-8"))["design"]
            root = distribution / spec["directory"] / "references"
        required = {"review-policy.md", "ooui-modeling.md", "cognitive-load.md", "quality-gates.md", "sources.md"}
        if (set(spec["references"]) != required or len(spec["references"]) != len(required)
                or spec["entry"] != "review-policy.md" or spec["version"] != VERSION):
            raise Blocked("Invalid design reference index")
        references = []
        summary = None
        for name in spec["references"]:
            path = root / name
            body = path.read_text(encoding="utf-8")
            if not body.strip():
                raise Blocked("Empty design reference: " + name)
            references.append({"name": name, "path": str(path.resolve()), "sha256": digest(path)})
            if name == spec["entry"]:
                summary = body
        return {"version": spec["version"], "summary": summary, "references": references}
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as e:
        raise Blocked("Cannot read bundled design references; update the owned harness with --force") from e


def capabilities():
    checks = {}
    for name in ("codex", "node", "git"):
        checks[name] = bool(shutil.which(name))
    if checks["codex"]:
        r = command(["codex", "exec", "--help"])
        checks["codex_exec"] = r.returncode == 0 and all(
            x in r.stdout for x in ("--json", "--output-schema", "--output-last-message", "--sandbox"))
    else:
        checks["codex_exec"] = False
    root = runtime_root()
    checks["playwright_package"] = (root / "node_modules/playwright/package.json").is_file()
    checks["bridge"] = (HERE / "visual-browser.cjs").is_file()
    try:
        design_guidance()
        checks["design_references"] = True
    except Blocked as e:
        checks["design_references"] = False
        checks["design_error"] = str(e)
    return checks


def browser_smoke():
    env = dict(os.environ, UX_GAN_RUNTIME=str(runtime_root()))
    r = command(["node", str(HERE / "visual-browser.cjs"), "--smoke"], env=env, timeout=45)
    if r.returncode:
        raise Blocked("Chromium could not launch. Install its OS dependencies/browser; "
                      "no code-only evaluation is allowed. " + scrub(r.stderr[-700:]))
    return json.loads(r.stdout)


def sandbox_smoke(project=None):
    help_result = command(["codex", "sandbox", "--help"])
    # Current CLI selects the OS backend; older versions expose 'linux'.
    suffix = ["linux"] if "Commands:" in help_result.stdout and "linux" in help_result.stdout else []
    r = command(["codex", "-c", 'sandbox_mode="read-only"', "sandbox", *suffix,
                 "--", "/bin/true"], cwd=project, timeout=15)
    if r.returncode:
        raise Blocked("Codex command sandbox cannot start on this host. "
                      "Fix the host/container sandbox support; permissions are not bypassed. "
                      + scrub(r.stderr[-500:]))
    return True


def doctor(args):
    checks = capabilities()
    try:
        if checks["playwright_package"] and checks["node"]:
            checks["browser_launch"] = bool(browser_smoke().get("ready"))
        else:
            checks["browser_launch"] = False
    except Blocked as e:
        checks["browser_launch"] = False
        checks["browser_error"] = str(e)
    if checks["codex_exec"]:
        try:
            checks["codex_sandbox"] = sandbox_smoke(Path(args.project).resolve())
        except Blocked as e:
            checks["codex_sandbox"] = False
            checks["sandbox_error"] = str(e)
    good = all(v for k, v in checks.items() if not k.endswith("_error"))
    print(json.dumps({"version": VERSION, "ready": good, "checks": checks,
                      "runtime": str(runtime_root())}, ensure_ascii=False, indent=2))
    return 0 if good else 1


def fingerprint(project):
    """Hash tracked/visible untracked source; generated harness output is excluded."""
    git = command(["git", "-C", str(project), "rev-parse", "HEAD"])
    head = git.stdout.strip() if git.returncode == 0 else ""
    if head:
        r = command(["git", "-C", str(project), "ls-files", "-z", "--cached",
                     "--others", "--exclude-standard"])
        if r.returncode:
            raise Blocked("Cannot inspect the repository working tree")
        names = sorted(set(x for x in r.stdout.split("\0") if x))
    else:
        names = []
        for root, dirs, files in os.walk(project):
            dirs[:] = [d for d in dirs if d not in
                       (".git", "node_modules", "__pycache__", ".next", ".cache", ".venv",
                        "dist", "build", "test-results", "playwright-report")]
            names.extend(str((Path(root) / f).relative_to(project)) for f in files)
    files = {}
    for name in names:
        if name.startswith(("artifacts/ux-gan/", "docs/ui-ux-review-assets/")):
            continue
        if name in {"docs/" + r for r in REPORTS}:
            continue
        p = project / name
        if p.is_symlink():
            value = "symlink:" + os.readlink(p)
        elif p.is_file():
            value = digest(p) + ":" + str(p.stat().st_mode & 0o777)
        else:
            value = "missing"
        files[name] = value
    return {"head": head, "files": files}


def assert_source(expected, project):
    actual = fingerprint(project)
    if actual != expected:
        changed = sorted(k for k in expected["files"].keys() | actual["files"].keys()
                         if expected["files"].get(k) != actual["files"].get(k))
        raise Blocked("Source changed outside a declared fix phase; re-audit is needed. "
                      + ", ".join(changed[:8]))


def obj(fields):
    return {"type": "object", "properties": fields, "required": list(fields),
            "additionalProperties": False}


def arr(item):
    return {"type": "array", "items": item}


S = {"type": "string"}
B = {"type": "boolean"}
I = {"type": "integer"}


def enum(values):
    return {"type": "string", "enum": values}


EVIDENCE = obj({"id": S, "path": S, "screen_id": S, "flow_id": S, "description": S,
                "target": S, "url": S, "source": enum(["live", "official_reference"]),
                "viewport": obj({"width": I, "height": I})})
COMMON = {"reason": S, "browser_backend": enum(
    ["browser-plugin", "playwright-mcp", "local-playwright", "unavailable"]),
    "fallback_reason": S, "evidence": arr(EVIDENCE)}
PLAN_SCHEMA = obj({
    **COMMON, "status": enum(["ready", "blocked"]),
    "first_impression": obj({k: S for k in
                            ["purpose", "next_action", "primary_cta", "unknown_terms", "hesitations"]}),
    "screens": arr(obj({"id": S, "name": S, "url": S})),
    "flows": arr(obj({"id": S, "name": S, "steps": arr(S), "required": B,
                     "states": arr(enum(STATES))})), "test_commands": arr(S),
})
REFERENCE_SCHEMA = obj({
    **COMMON, "status": enum(["ready", "partial", "blocked"]),
    "apps": arr(obj({"name": S, "url": S, "checked_at": S,
                     "observation_kind": enum(["live", "official_screenshot", "unavailable"]),
                     "evidence_ids": arr(S),
                     "patterns": arr(obj({k: S for k in ["pattern", "why", "application", "avoid"]})),
                     "limitations": S})),
})
ISSUE = obj({
    "id": S, "title": S, "severity": enum(SEVERITIES), "screen_id": S, "flow_id": S,
    "root_cause": S,
    "action": S, "problem": S, "confusion": S, "why": S, "improvement": S,
    "evidence_ids": arr(S), "status": enum(["open", "resolved", "unverified"]),
    "verified_after_ids": arr(S),
})
AUDIT_SCHEMA = obj({
    **COMMON, "status": enum(["reviewed", "blocked"]), "issues": arr(ISSUE),
    "coverage": arr(obj({"flow_id": S, "viewport": enum(list(VIEWPORTS)),
                         "state": enum(STATES), "perspective": enum(PERSPECTIVES),
                         "result": enum(["passed", "failed", "not_tested"]), "notes": S,
                         "steps": arr(obj({"action": S, "before_evidence_id": S,
                                           "after_evidence_id": S, "result": S}))})),
    "screen_reviews": arr(obj({"screen_id": S, **{k: S for k in
        ["purpose", "information", "cta", "interaction", "copy", "visibility", "consistency"]}})),
    "friction": arr(obj({"flow_id": S, "point": S, "improvement": S,
                         "blocking": B, "evidence_ids": arr(S)})),
    "copy_issues": arr(obj({"current": S, "problem": S, "suggested": S})),
    "consistency": arr(S),
    "responsive": arr(obj({"viewport": enum(list(VIEWPORTS)), "problem": S,
                           "evidence_ids": arr(S)})),
    "simplicity": obj({"primary_action": S, "step_count": I, "decision_points": I,
                       "mobile_density": enum(["low", "medium", "high"]),
                       "regressed": B, "change_rationale": S, "evidence_ids": arr(S)}),
    "second_pass_complete": B,
})
FIX_SCHEMA = obj({
    "status": enum(["changed", "blocked"]), "reason": S, "fixed_issue_ids": arr(S),
    "changed_files": arr(S),
    "changes": arr(obj({"issue_ids": arr(S), "description": S, "simplicity_reason": S})),
    "tests": arr(obj({"command": S, "passed": B, "output_summary": S})),
})


def validate_schema(value, schema, location="$"):
    typ = schema["type"]
    types = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int}
    if not isinstance(value, types[typ]) or typ == "integer" and isinstance(value, bool):
        raise Blocked(f"Invalid structured output at {location}: expected {typ}")
    if "enum" in schema and value not in schema["enum"]:
        raise Blocked(f"Invalid value at {location}")
    if typ == "object":
        if set(value) != set(schema["required"]):
            raise Blocked(f"Missing or unknown fields at {location}")
        for k, sub in schema["properties"].items():
            validate_schema(value[k], sub, location + "." + k)
    if typ == "array":
        for n, item in enumerate(value):
            validate_schema(item, schema["items"], f"{location}[{n}]")


def png_dimensions(path):
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise Blocked("Evidence is not a PNG: " + str(path))
    pos, size, idat, ended = 8, None, bytearray(), False
    while pos + 12 <= len(data):
        n = struct.unpack(">I", data[pos:pos+4])[0]
        tag, chunk = data[pos+4:pos+8], data[pos+8:pos+8+n]
        if pos+12+n > len(data):
            raise Blocked("Truncated PNG: " + str(path))
        crc = struct.unpack(">I", data[pos+8+n:pos+12+n])[0]
        if zlib.crc32(tag+chunk) & 0xffffffff != crc:
            raise Blocked("Corrupt PNG: " + str(path))
        if tag == b"IHDR":
            size = struct.unpack(">II", chunk[:8])
        if tag == b"IDAT":
            idat.extend(chunk)
        if tag == b"IEND":
            ended = True
            break
        pos += n+12
    if not ended or not size or not idat or not (320 <= size[0] <= 2560 and 400 <= size[1] <= 2160):
        raise Blocked("Evidence must be a full supported viewport PNG: " + str(path))
    try:
        d = zlib.decompressobj()
        raw = d.decompress(idat, 40_000_000)
        if not raw or not d.eof:
            raise ValueError("invalid pixel data")
    except (ValueError, zlib.error) as e:
        raise Blocked("Unreadable PNG: " + str(path)) from e
    return size


def validated_evidence(result, role_dir, backend, project, run_id):
    seen = set()
    receipts = {}
    for file in (role_dir / "screenshots").rglob("browser-receipts.jsonl"):
        for line in file.read_text().splitlines():
            frame = json.loads(line)
            if frame.get("kind") == "frame":
                receipts[Path(frame["path"]).resolve()] = frame
    archived = {}
    for e in result.get("evidence", []):
        if not all(e[k].strip() for k in ("description", "target", "url")):
            raise Blocked("Screenshot evidence must identify its UI target, description and URL")
        if not e["id"] or e["id"] in seen:
            raise Blocked("Duplicate/empty evidence ID")
        seen.add(e["id"])
        p = Path(e["path"])
        if not p.is_absolute():
            p = role_dir / p
        if p.is_symlink() or not p.resolve().is_relative_to((role_dir / "screenshots").resolve()):
            raise Blocked("Screenshot escaped its role directory: " + str(p))
        p = p.resolve()
        if not p.is_file() or p.stat().st_size > 25_000_000:
            raise Blocked("Missing/oversized screenshot: " + str(p))
        size = png_dimensions(p)
        if size != (e["viewport"]["width"], e["viewport"]["height"]):
            raise Blocked("Screenshot size does not match recorded viewport")
        if backend == "local-playwright":
            frame = receipts.get(p)
            if not frame or frame["sha256"] != digest(p) or frame["url"] != e["url"] or frame.get("source") != e["source"]:
                raise Blocked("Screenshot lacks a matching browser-generated receipt")
        dest = project / "docs/ui-ux-review-assets" / run_id / role_dir.name / p.relative_to(role_dir / "screenshots")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
        archived[e["id"]] = {**e, "path": str(dest), "sha256": digest(dest),
                              "captured_at": receipts.get(p, {}).get("captured_at", now())}
    return archived


def validate_plan(plan, evidence):
    if not plan["screens"] or not plan["flows"]:
        raise Blocked("Planner produced no screens/flows")
    for key in ("screens", "flows"):
        ids = [x["id"] for x in plan[key]]
        if len(ids) != len(set(ids)) or not all(ids):
            raise Blocked("Invalid planner IDs")
    if not any(f["required"] for f in plan["flows"]):
        raise Blocked("Planner did not identify a required main flow")
    if not any(e["source"] == "live" for e in evidence.values()):
        raise Blocked("First impression has no live target screenshot")


def validate_audit(audit, evidence, plan, previous=None):
    screen_ids = {s["id"] for s in plan["screens"]}
    flow_ids = {f["id"] for f in plan["flows"]}
    if not any(c["steps"] and c["result"] != "not_tested" for c in audit["coverage"]):
        raise Blocked("No actual user-flow interaction was reviewed")
    ids = [i["id"] for i in audit["issues"]]
    if len(ids) != len(set(ids)):
        raise Blocked("Duplicate issue IDs")
    for issue in audit["issues"]:
        if issue["screen_id"] not in screen_ids or issue["flow_id"] not in flow_ids:
            raise Blocked("Issue refers to an unknown screen/flow")
        if not issue["evidence_ids"] or not all(i in evidence for i in issue["evidence_ids"]):
            raise Blocked("Issue lacks current screenshot evidence: " + issue["id"])
        if any(evidence[x]["source"] != "live" for x in issue["evidence_ids"]):
            raise Blocked("External references cannot prove a target-app issue")
        if not any(evidence[x]["screen_id"] == issue["screen_id"] and
                   evidence[x]["flow_id"] == issue["flow_id"] for x in issue["evidence_ids"]):
            raise Blocked("Issue evidence does not match its screen/flow")
        if issue["status"] == "resolved" and (not issue["verified_after_ids"] or
                not all(i in evidence and evidence[i]["source"] == "live" for i in issue["verified_after_ids"])):
            raise Blocked("Resolved issue lacks freshly captured after evidence")
        if issue["status"] == "resolved" and not any(
                c["flow_id"] == issue["flow_id"] and
                any(step["after_evidence_id"] in issue["verified_after_ids"] for step in c["steps"])
                for c in audit["coverage"]):
            raise Blocked("Resolved issue's after image is not from replaying its flow")
    if previous:
        old_ids = {i["id"] for i in previous["issues"]}
        if not old_ids.issubset(ids):
            raise Blocked("Evaluator dropped earlier findings instead of verifying their status")
    for c in audit["coverage"]:
        if c["flow_id"] not in flow_ids:
            raise Blocked("Coverage refers to unknown flow")
        if c["result"] != "not_tested" and not c["steps"]:
            raise Blocked("Executed flow has no operation evidence")
        for step in c["steps"]:
            for key in ("before_evidence_id", "after_evidence_id"):
                e = evidence.get(step[key])
                if not e or e["source"] != "live":
                    raise Blocked("Operation lacks live before/after images")
                if (e["viewport"]["width"], e["viewport"]["height"]) != VIEWPORTS[c["viewport"]]:
                    raise Blocked("Coverage viewport does not match its actual image")
    review_ids = [r["screen_id"] for r in audit["screen_reviews"]]
    if len(review_ids) != len(set(review_ids)) or any(
            i not in screen_ids or not any(e["screen_id"] == i and e["source"] == "live"
                                          for e in evidence.values()) for i in review_ids):
        raise Blocked("Screen review lacks a corresponding current screen image")
    for section in ("friction", "responsive"):
        for item in audit[section]:
            if not item["evidence_ids"] or not all(x in evidence for x in item["evidence_ids"]):
                raise Blocked(section + " lacks screenshot evidence")
    if not audit["simplicity"]["evidence_ids"] or not all(
            i in evidence for i in audit["simplicity"]["evidence_ids"]):
        raise Blocked("Simplicity judgement lacks current screenshot evidence")


def gate(audit, plan, references, tests):
    reasons = []
    remaining = [i for i in audit["issues"] if i["status"] != "resolved"]
    if any(i["severity"] in ("Critical", "High") for i in remaining):
        reasons.append("Critical/High issues remain")
    if any(i["status"] == "unverified" for i in remaining):
        reasons.append("Issues remain unverified")
    if any(f["blocking"] for f in audit["friction"]):
        reasons.append("Main-flow confusion remains")
    if audit["simplicity"]["regressed"]:
        reasons.append("UI simplicity regressed")
    for flow in plan["flows"]:
        if not flow["required"]:
            continue
        for c in audit["coverage"]:
            if c["flow_id"] == flow["id"] and (c["state"] == "normal" or c["state"] in flow["states"]) and c["result"] != "passed":
                reasons.append(f"Required case unverified/failed: {flow['id']} / {c['viewport']} / {c['state']} / {c['perspective']}")
        for viewport in VIEWPORTS:
            if not any(c["flow_id"] == flow["id"] and c["viewport"] == viewport
                       and c["state"] == "normal" and c["result"] == "passed"
                       for c in audit["coverage"]):
                reasons.append(f"Required flow unverified/failed: {flow['id']} / {viewport}")
        for state in flow["states"]:
            if not any(c["flow_id"] == flow["id"] and c["state"] == state
                       and c["result"] == "passed" for c in audit["coverage"]):
                reasons.append(f"Required state unverified/failed: {flow['id']} / {state}")
    if not audit["second_pass_complete"] or not set(PERSPECTIVES).issubset(
            {c["perspective"] for c in audit["coverage"] if c["result"] != "not_tested"}):
        reasons.append("Second pass / four perspectives incomplete")
    if not references or references["status"] != "ready":
        reasons.append("Reference comparison incomplete")
    if not tests or not all(t["passed"] for t in tests):
        reasons.append("Required checks not completed")
    return reasons


def metric(audit, reasons):
    weights = {"Critical": 100, "High": 20, "Medium": 2, "Low": 1}
    return sum(weights[i["severity"]] for i in audit["issues"] if i["status"] != "resolved") + len(reasons)*30


def scrub(value):
    secrets = [v for k, v in os.environ.items()
               if re.search(r"TOKEN|PASSWORD|SECRET|API_KEY", k, re.I) and len(v) >= 8]
    def clean(v):
        if isinstance(v, dict):
            return {k: ("[image omitted; see evidence]" if k == "data" and v.get("type") == "image"
                        else clean(x)) for k, x in v.items()}
        if isinstance(v, list):
            return [clean(x) for x in v]
        if isinstance(v, str):
            for secret in secrets:
                v = v.replace(secret, "[redacted]")
            return re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._-]{12,}", r"\1[redacted]", v)
        return v
    return clean(value)


def terminate(proc):
    if proc and proc.poll() is None:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()


def stream_process(argv, cwd, env, log_path, timeout):
    """Bounded process with progress heartbeats, private redacted event logs."""
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, start_new_session=True)
    start = heartbeat = time.monotonic()
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    buffer = b""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("w", encoding="utf-8") as out:
            os.chmod(log_path, 0o600)
            while True:
                for key, _ in selector.select(0.5):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        txt = line.decode("utf-8", errors="replace")
                        try:
                            out.write(json.dumps(scrub(json.loads(txt)), ensure_ascii=False) + "\n")
                        except ValueError:
                            out.write(json.dumps({"stderr": scrub(txt)}, ensure_ascii=False) + "\n")
                elapsed = time.monotonic() - start
                if time.monotonic() - heartbeat >= 20:
                    log(f"実行中: {log_path.parent.name} ({int(elapsed)}s)")
                    heartbeat = time.monotonic()
                if elapsed > timeout:
                    raise Blocked(f"Phase timeout ({timeout}s): {log_path.parent.name}")
                if proc.poll() is not None and not selector.get_map():
                    break
            if buffer:
                out.write(json.dumps({"stderr": scrub(buffer.decode(errors="replace"))}) + "\n")
        return proc.returncode
    finally:
        selector.close()
        terminate(proc)
        proc.stdout.close()


def select_backend(config):
    if config["browser"] != "auto":
        return config["browser"], "Explicitly selected local Playwright"
    plugins = command(["codex", "plugin", "list", "--json"])
    if plugins.returncode:
        raise Blocked("Could not inspect Codex browser plugins")
    try:
        raw = json.loads(plugins.stdout)
        installed = raw.get("installed", []) if isinstance(raw, dict) else raw
        if any(p.get("name") == "browser" and p.get("enabled", True) for p in installed):
            return "browser-plugin", ""
        mcp = command(["codex", "mcp", "list", "--json"])
        if mcp.returncode:
            raise Blocked("Could not inspect Codex MCP servers")
        servers = json.loads(mcp.stdout)
        if isinstance(servers, dict):
            servers = servers.get("servers", [])
        if any(p.get("name") == "playwright" and p.get("enabled", True) for p in servers):
            return "playwright-mcp", "Browser plugin not available"
    except (ValueError, AttributeError) as e:
        raise Blocked("Malformed Codex browser capability output") from e
    return "local-playwright", "Browser plugin and configured Playwright MCP not available"


BASE_PROMPT = """You are a role in a screenshot-first UI/UX generator/evaluator harness.
Follow repository rules and the user's scope. You are NOT doing human usability testing.
Write human-facing report fields in Japanese unless the user's brief requests another
language. Preserve the schema keys and enum values.
Use the audience in the user's brief; otherwise start with a first-time user with
low/moderate IT literacy and little domain knowledge. Preserve needed expert workflows.
Apply the supplied design_guidance summary to each role; read linked details as needed.
Do not infer meaning that is not in the UI. Choose each next action AFTER looking at a
screenshot; then interact and look at the resulting screenshot. DOM/accessibility text
is allowed to locate a control after that visual decision, and code only to investigate
an already observed problem. Save full viewport PNGs in the given screenshots directory.
Include every PNG used in your final evidence list with path, URL, viewport and UI target.
Native browser screenshots must be copied there. Local ux_* tools automatically capture,
display and record actual before/after images. Tool image responses are the visual source.
Use only test fixtures/test accounts. Do not send messages, publish, pay or alter production.
Do not install dependencies in the app, change git HEAD, commit, reset or deploy.
Do not invoke any harness again: UX_GAN_CHILD=1. Do not expose credentials or personal data.
Do not manufacture observations, image files, scores or test results. Return blocked if
the required environment is unavailable. Explain mocks, missing states and uncertainty.
Do not quota-limit findings: cover the app, then revisit the top and main flows.
"""


def role_prompt(role, state, role_dir):
    data = {"project": state["config"]["project"], "url": state["config"]["url"],
            "screenshots_directory": str(role_dir / "screenshots"),
            "browser_backend": state["backend"], "fallback_reason": state["fallback_reason"],
            "user_brief": state["config"]["brief"], "reference_urls": state["config"]["reference_urls"],
            "repository_rule_files": state["rules"], "design_guidance": design_guidance()}
    instructions = {
        "planner": """FIRST open the top page, look at its image, and record your first impression
before reading application UI source. Identify purpose, next step, primary action,
unknown terms and hesitations. Then discover screens/flows from actual navigation and
README/routes. Do not propose new features. Mark the actual core flows required and list
applicable states (do not assume every flow has a form). Capture all three viewport widths.
Identify the visible objects, attributes, collection/detail views, contextual actions,
related-object navigation and retained state. Note justified fixed-target/task-first flows.
Suggest existing required test commands from repo instructions/manifests; never destructive
production operations. Ready requires at least one target screenshot, screens and main flows.""",
        "references": """Find about three comparable apps for this purpose using web search and
primary official demos/help. The provided URLs are optional seeds. For each candidate show
real publicly accessible screens or official UI screenshots, with source URL and date.
An official screenshot is NOT live app operation. Do not sign up, log in, pay or post.
For each observed design pattern record why it helps a novice, a focused application to
the target and what should NOT be copied. If a source is inaccessible record the limitation.
Compare object/action context, navigation, memory support, information priority and recovery,
not just styling. A pattern is a proposal for this audience, not proof it improves this app.
Ready requires at least one genuinely image-observed app, with meaningful patterns and
an attempted comparison of three candidates. Otherwise return partial/blocked.
Use official_reference evidence. Do not copy an entire competitor UI into this app.""",
        "reviewer": """Operate ALL available major flows. Compare screenshots at desktop 1440x900,
tablet 768x1024 and mobile 390x844. Cover applicable empty, invalid input, cancel, back,
double click, loading, success and failure states. Record before/after evidence for every
executed coverage item. Revisit the top and main task with four perspectives: first_time,
mistake, hurried, skips_explanation. Second pass complete means this was actually done.
Record issues, including small hesitations, with specific cause and recommendation.
Use stable issue IDs and a stable descriptive root_cause to group related issues.
Carry ALL earlier issues forward. Only mark resolved after
replaying that operation with fresh image evidence of its outcome. Do not accept a fixer's
claim as verification. Judge current primary action, step count, decision points and mobile
density. Compare simplicity to the baseline, with images: regressed=true if fixes cluttered
the UI, hid required information, increased searching/backtracking/re-entry, lost state,
added competing actions or made the main task harder. Element/step counts alone do not
establish regression. Good labels may replace vague
icons; prefer removing/merging/reordering over adding permanent help/panels/buttons.
In screen_reviews.information/interaction describe objects, views, action context and
justified exceptions. In friction identify remembering, searching, comparing, mapping,
guessing and backtracking burdens with actual flow evidence. Record the representative
flow and counting method in simplicity.change_rationale; link step_count/decision_points
to observed operations, and describe re-entry, recovery and hidden required information.
Check functional completeness, display bugs and actual outcomes independently of OOUI.
Blocking friction must represent obstacles or meaningful uncertainty in a main task.
Separate open findings from unverified ones, and report limitations instead of guessing.""",
        "fixer": """Fix the selected highest-impact root-cause groups, at most three groups.
Reproduce the image-grounded findings first. Preserve other working-tree edits and existing
features. Prefer consolidation, removal of duplication, information order and precise copy.
Use object/context and cognitive-load guidance for each selected issue. Preserve required
information, appropriate confirmations, expert actions and drafts; do not create unnecessary
object pages or force every workflow into a list/detail layout. For Japanese UI drafts,
recommend available yomiyasu while preserving meaning and short labels; never install it.
For every added visible control/explanation, explain why a simpler change is insufficient.
Do not expand scope or add unsolicited features. Make the smallest coherent fix, run
appropriate existing checks and report every changed source file relative to project.
Do not touch harness outputs, screenshot evidence, repo rules or final report files.
You are not authorized to call an issue resolved; a separate reviewer will verify it."""
    }
    data["plan"] = state.get("plan")
    if role == "reviewer":
        data["previous_audit"] = state.get("audit")
        data["baseline_simplicity"] = state.get("baseline_simplicity")
        data["reference_apps"] = state.get("references")
    if role == "fixer":
        data["selected_issues"] = state["selected_issues"]
        data["audit"] = state["audit"]
        data["reference_apps"] = state.get("references")
    if state.get("input_review"):
        data["prior_review_archive"] = state["input_review"]
    return BASE_PROMPT + "\nROLE: " + role + "\n" + instructions[role] + "\n\nINPUT:\n" + json.dumps(data, ensure_ascii=False)


def run_role(role, schema, state, run_dir, iteration):
    tag = f"{iteration:03d}-{role}"
    role_dir = run_dir / tag
    attempt = 0
    while True:
        attempt += 1
        actual_dir = role_dir if attempt == 1 else run_dir / (tag + "-fallback")
        if actual_dir.exists():
            actual_dir = run_dir / (actual_dir.name + "-" + uuid.uuid4().hex[:8])
        actual_dir.mkdir(parents=True, exist_ok=True)
        (actual_dir / "screenshots").mkdir(exist_ok=True)
        schema_path = actual_dir / "schema.json"
        output_path = actual_dir / "result.json"
        atomic_json(schema_path, schema)
        prompt = role_prompt(role, state, actual_dir)
        (actual_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        argv = ["codex", "exec", "-C", state["config"]["project"],
                "--sandbox", "workspace-write" if role == "fixer" else "read-only",
                "--json", "--ephemeral", "--output-schema", str(schema_path),
                "--output-last-message", str(output_path), "-c", 'web_search="live"']
        if not state["expected_source"]["head"]:
            argv.append("--skip-git-repo-check")
        if state["config"].get("model"):
            argv += ["--model", state["config"]["model"]]
        if state["backend"] == "local-playwright":
            # Invocation-only MCP config. Personal config is never overwritten.
            bridge = {
                "command": "node", "args": [str(HERE / "visual-browser.cjs")],
                "env": {"UX_GAN_RUNTIME": str(runtime_root()),
                        "UX_GAN_SCREENSHOTS": str(actual_dir / "screenshots"),
                        "UX_GAN_TARGET": state["config"]["url"]},
                "startup_timeout_sec": 60, "tool_timeout_sec": 60
            }
            for key in ("UX_GAN_BROWSER_EXECUTABLE", "PLAYWRIGHT_BROWSERS_PATH"):
                if os.environ.get(key):
                    bridge["env"][key] = os.environ[key]
            def toml(v):
                if isinstance(v, dict):
                    return "{" + ", ".join(json.dumps(k)+ " = " + toml(x) for k, x in v.items()) + "}"
                if isinstance(v, list):
                    return "[" + ", ".join(toml(x) for x in v) + "]"
                return json.dumps(v)
            for k, v in bridge.items():
                argv += ["-c", f"mcp_servers.ux_gan_browser.{k}={toml(v)}"]
            if state.get("failed_native_backend") == "playwright-mcp":
                argv += ["-c", "mcp_servers.playwright.enabled=false"]
        attached = []
        if role in ("fixer", "reviewer") and state.get("evidence"):
            attached = [e["path"] for e in state["evidence"].values()
                        if e["source"] == "live"][:4]
            for p in attached:
                argv += ["--image", p]
        env = dict(os.environ, UX_GAN_CHILD="1")
        # Pass prompt through an argv element; never interpolate it into shell code.
        argv += ["--", prompt]
        atomic_json(actual_dir / "invocation.json",
                    {"role": role, "browser": state["backend"], "attached_images": attached,
                     "sandbox": "workspace-write" if role == "fixer" else "read-only",
                     "started_at": now()})
        log(f"{tag}: {state['backend']} / {state['config'].get('model') or 'Codex設定のモデル'}")
        code = stream_process(argv, state["config"]["project"], env,
                              actual_dir / "events.jsonl", state["config"]["phase_timeout"])
        if role != "fixer":
            assert_source(state["expected_source"], Path(state["config"]["project"]))
        if not output_path.is_file():
            raise Blocked(f"{tag}: Codex produced no structured output (exit {code})")
        try:
            result = json.loads(output_path.read_text())
        except ValueError as e:
            raise Blocked(f"{tag}: malformed JSON") from e
        validate_schema(result, schema)
        if role != "fixer" and result["status"] == "blocked" and state["backend"] != "local-playwright":
            # Explicit recorded fallback, not an undocumented switch to code-only.
            reason = result["reason"]
            state["failed_native_backend"] = state["backend"]
            state["backend"] = "local-playwright"
            state["fallback_reason"] += "; " + reason
            state["history"].append({"phase": tag, "result": "blocked", "reason": reason,
                                     "fallback": "local-playwright"})
            log("ブラウザー経路が失敗。記録してローカルPlaywrightへ切替: " + reason[:180])
            browser_smoke()
            continue
        if code:
            raise Blocked(f"{tag}: Codex exited {code}; see its event log")
        if result["status"] == "blocked":
            raise Blocked(f"{tag}: " + result["reason"])
        if role == "fixer":
            return result, {}, actual_dir
        if result["browser_backend"] != state["backend"]:
            raise Blocked("Role used a different browser backend without a recorded fallback")
        evidence = validated_evidence(result, actual_dir, state["backend"],
                                      Path(state["config"]["project"]), state["run_id"])
        if not evidence and not (role == "references" and result["status"] == "partial"):
            raise Blocked(f"{tag}: no actual screenshot evidence")
        atomic_json(actual_dir / "evidence.json", evidence)
        return result, evidence, actual_dir


def wait_ready(url, process=None):
    end = time.monotonic() + 60
    while time.monotonic() < end:
        if process and process.poll() is not None:
            raise Blocked("Owned preview server exited before becoming ready")
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status < 500:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    raise Blocked("App URL did not become ready in 60s: " + url)


def run_tests(state, run_dir):
    commands = state["config"]["test_commands"] or state["plan"]["test_commands"]
    if not commands:
        return [{"command": "", "passed": False,
                 "output_summary": "No existing required checks were identified; validation remains incomplete."}]
    tests = []
    for n, cmd in enumerate(commands):
        log("検証: " + cmd)
        code = stream_process(["bash", "-c", cmd], state["config"]["project"], dict(os.environ),
                              run_dir / f"tests-{state['iteration']:03d}-{n}.jsonl",
                              state["config"]["phase_timeout"])
        tests.append({"command": cmd, "passed": code == 0, "output_summary": f"exit {code}"})
    assert_source(state["expected_source"], Path(state["config"]["project"]))
    return tests


def snapshot_review(path, run_dir):
    if not path or not path.is_file():
        return ""
    text = path.read_text()
    folder = run_dir / "input"
    folder.mkdir(exist_ok=True)
    def image_copy(m):
        raw = m.group(1)
        if urllib.parse.urlparse(raw).scheme:
            return m.group(0)
        p = (path.parent / urllib.parse.unquote(raw.split("#")[0])).resolve()
        if p.is_file() and p.suffix.lower() == ".png":
            dest = folder / "images" / (digest(p)[:12] + "-" + p.name)
            dest.parent.mkdir(exist_ok=True)
            shutil.copy2(p, dest)
            return m.group(0).replace(raw, "images/" + dest.name)
        return m.group(0)
    text = re.sub(r"\]\(([^)]+\.png)\)", image_copy, text)
    dest = folder / (path.stem + "-" + digest(path)[:8] + ".md")
    dest.write_text(text)
    return str(dest)


def cell(value):
    return str(value).replace("|", r"\|").replace("\n", "<br>")


def evidence_md(ids, evidence, report_path, previews=1):
    parts = []
    for n, ident in enumerate(dict.fromkeys(ids)):
        e = evidence[ident]
        rel = os.path.relpath(e["path"], report_path.parent).replace(os.sep, "/")
        rel = urllib.parse.quote(rel, safe="/.-_")
        caption = f"{e['description']} — {e['target']} ({e['viewport']['width']}×{e['viewport']['height']})"
        parts.append(f"[{caption}]({rel})")
        if n < previews:
            parts.append(f"\n![{caption}]({rel})\n")
    return "\n\n".join(parts)


def counts(audit):
    result = collections.Counter(i["severity"] for i in audit["issues"] if i["status"] != "resolved")
    return {s: result[s] for s in SEVERITIES}


def observed_counts(state):
    ev = state.get("evidence", {})
    screens = {e["screen_id"] for e in ev.values() if e["source"] == "live"}
    flows = {c["flow_id"] for c in state.get("audit", {}).get("coverage", [])
             if c["result"] != "not_tested" and c["steps"]}
    return len(screens), len(flows)


def publish(state, run_dir):
    """Render from validated structures. Do not erase an existing review on early failure."""
    if not state.get("audit"):
        return
    project = Path(state["config"]["project"])
    docs = project / "docs"
    docs.mkdir(exist_ok=True)
    audit, plan, ev = state["audit"], state["plan"], state["evidence"]
    stats = counts(audit)
    review_path = docs / REPORTS[0]
    open_issues = [i for i in audit["issues"] if i["status"] != "resolved"]
    sorted_issues = sorted(open_issues, key=lambda i: (SEVERITIES.index(i["severity"]), i["id"]))
    observed_screens, observed_flows = observed_counts(state)
    text = ["# UI/UX Review", "", "## 1. Executive Summary", "",
            f"実行ID: {state['run_id']} / 状態: **{state['status']}** / 確認日時: {now()}",
            f"対象の版: {state['expected_source']['head'] or 'Git管理なし'}。未コミット内容を含むソース指紋も実行記録に保存。",
            f"**実際に確認した{observed_screens}画面、{observed_flows}主要フロー。** "
            + " / ".join(f"{s} {stats[s]}件" for s in SEVERITIES) + "（未解消件数）。",
            f"発見した対象は{len(plan['screens'])}画面、{len(plan['flows'])}主要フロー。未確認はcoverageで区別。",
            "AIが初見ユーザーの視点で実画面を評価した結果。人間のユーザーテストは未実施。", ""]
    text += ["OOUIの構造、認知負荷、機能の充足、表示、実操作を分けて確認します。"
             "適用した共通基準・参照資料と版は各ロールのprompt.txtに保存しています。", ""]
    for k, label in [("purpose", "何のサービスか"), ("next_action", "最初の操作"),
                     ("primary_cta", "主操作"), ("unknown_terms", "分からない言葉"),
                     ("hesitations", "初見で迷った点")]:
        text.append(f"- {label}: {plan['first_impression'][k]}")
    text += ["", "優先する問題:", ""]
    text += [f"- {i['id']}: {i['title']}（{i['severity']}）" for i in sorted_issues[:10]]
    if not sorted_issues:
        text.append("- 確認範囲で未解消の指摘はありません。未確認事項は実行結果を参照してください。")
    text += ["", "## 2. Reviewed User Flows", "", "| Flow | 必須 | 確認結果 |",
             "|---|---|---|"]
    for f in plan["flows"]:
        items = [c for c in audit["coverage"] if c["flow_id"] == f["id"]]
        text.append(f"| {cell(f['name'])} | {'Yes' if f['required'] else 'No'} | "
                    f"{cell(', '.join(c['viewport']+'/'+c['state']+': '+c['result'] for c in items))} |")
    screen_names = {s["id"]: s["name"] for s in plan["screens"]}
    for heading, sevs in [("3. High Priority Issues", ["Critical", "High"]),
                           ("4. Medium Priority Issues", ["Medium"]),
                           ("5. Low Priority / Polish", ["Low"])]:
        text += ["", "## " + heading, ""]
        issues = [i for i in sorted_issues if i["severity"] in sevs]
        if not issues:
            text.append("未解消の指摘なし。")
        for issue in issues:
            text += [f"### {issue['id']}: {issue['title']}", "",
                     f"**Severity:** {issue['severity']}", "",
                     f"**Screen:** {screen_names[issue['screen_id']]}", "",
                     f"**User action:**  \n{issue['action']}", "",
                     f"**Problem:**  \n{issue['problem']}", "",
                     f"**Why this is confusing:**  \n{issue['confusion']}\n\n{issue['why']}", "",
                     f"**Recommended improvement:**  \n{issue['improvement']}", "",
                     f"**Status:** {issue['status']}", "",
                     "**Evidence:**", "",
                     evidence_md(issue["evidence_ids"], ev, review_path), ""]
    text += ["", "## 6. Screen-by-Screen Review", ""]
    for r in audit["screen_reviews"]:
        text += [f"### {screen_names.get(r['screen_id'], r['screen_id'])}", ""]
        for k, label in [("purpose", "目的"), ("information", "情報設計"), ("cta", "CTA"),
                         ("interaction", "操作性"), ("copy", "文言"), ("visibility", "視認性"),
                         ("consistency", "一貫性")]:
            text.append(f"- {label}: {r[k]}")
        text.append("")
    text += ["## 7. User Flow Friction", ""]
    for f in audit["friction"]:
        text += [f"- {f['flow_id']}: {f['point']} → {f['improvement']}",
                 evidence_md(f["evidence_ids"], ev, review_path, 0), ""]
    text += ["## 8. Terminology / Copy Issues", "",
             "| Current | Problem | Suggested |", "|---|---|---|"]
    text += [f"| {cell(c['current'])} | {cell(c['problem'])} | {cell(c['suggested'])} |"
             for c in audit["copy_issues"]]
    text += ["", "## 9. Consistency Issues", ""]
    text += ["- " + c for c in audit["consistency"]] or ["指摘なし。"]
    text += ["", "## 10. Responsive Issues", ""]
    for r in audit["responsive"]:
        text += [f"- {r['viewport']}: {r['problem']}",
                 evidence_md(r["evidence_ids"], ev, review_path, 0), ""]
    text += ["", "## 11. Recommended Fix Order", "",
             "ユーザー体験への影響が大きい順。主操作の統合・情報整理を優先し、画面の情報量を再確認する。", ""]
    text += [f"{n}. {i['id']}: {i['title']}" for n, i in enumerate(sorted_issues, 1)]
    text += ["", "未確認・停止理由:", "", state.get("reason") or "記録した確認範囲を参照。", ""]
    reference_path = docs / REPORTS[1]
    refs = ["# Reference Apps", "", "公開画面・公式画像と、実操作による確認を区別しています。",
            f"実行ID: {state['run_id']}", ""]
    ref_ev = state.get("reference_evidence", {})
    for app in state.get("references", {}).get("apps", []):
        refs += [f"## {app['name']}", "",
                 f"[出典]({app['url']}) / {app['checked_at']} / {app['observation_kind']}", "",
                 app["limitations"], ""]
        for p in app["patterns"]:
            refs += [f"- 工夫: {p['pattern']}", f"  - 初見ユーザーへの効果: {p['why']}",
                     f"  - 適用案: {p['application']}", f"  - 採用しない部分: {p['avoid']}", ""]
        refs += [evidence_md(app["evidence_ids"], ref_ev, reference_path, 2), ""]
    refs += ["確認結果: " + state.get("references", {}).get("reason", "未確認"), ""]
    fix_path = docs / REPORTS[2]
    fixes = ["# UI/UX Fix Report", "", f"実行ID: {state['run_id']} / **{state['status']}**",
             state.get("reason", ""), "", "## 修正と再確認", ""]
    base_ev = state.get("baseline_evidence", {})
    for issue in audit["issues"]:
        if issue["status"] != "resolved":
            continue
        old = next((i for i in state.get("baseline_audit", {}).get("issues", [])
                    if i["id"] == issue["id"]), None)
        fixes += [f"### {issue['id']}: {issue['title']}", "", "変更前:", ""]
        if old:
            fixes += [evidence_md(old["evidence_ids"], base_ev, fix_path), ""]
        else:
            fixes += ["初回ベースライン後に発見されたため、変更前は該当反復の記録を参照。", ""]
        fixes += ["変更後（別の評価実行で再確認）:", "",
                  evidence_md(issue["verified_after_ids"], ev, fix_path), ""]
    fixes += ["## 画面の簡潔さ", "",
              "情報の発見、判断、状態保持、往復・再入力と表示密度を、同じフローの前後で比較します。"
              "要素数や操作数だけで良否を決めず、AIの所見と測定値を区別します。", "",
              json.dumps(audit["simplicity"], ensure_ascii=False), "",
              "## 検証", "", "| Command | Result |", "|---|---|"]
    fixes += [f"| {cell(t['command'])} | {'PASS' if t['passed'] else 'FAIL'} |"
              for t in state.get("tests", [])]
    fixes += ["", "## 残件と未確認", ""]
    fixes += [f"- {i['id']}: {i['title']} / {i['severity']} / {i['status']}" for i in sorted_issues]
    fixes += ["", "実送信・公開・課金・本番データ操作、人間による使いやすさの確認は、この結果の保証範囲に含まれません。",
              "個別の実行範囲・仮応答・未確認条件はcoverageとロール記録を参照してください。", ""]
    for path, body in [(review_path, "\n".join(text)), (reference_path, "\n".join(refs)),
                       (fix_path, "\n".join(fixes))]:
        expected = state["report_hashes"].get(path.name)
        actual = digest(path) if path.exists() else None
        if actual != expected:
            raise Blocked("Report was edited concurrently; preserved it: " + str(path))
        archive = run_dir / path.name
        # Rewrite image links for per-run report copies.
        archive_body = re.sub(r"\]\((ui-ux-review-assets/[^)]+)\)",
                              lambda m: "](" + os.path.relpath(docs / urllib.parse.unquote(m[1]),
                                                              run_dir).replace(os.sep, "/") + ")",
                              body)
        archive.write_text(archive_body, encoding="utf-8")
        tmp = path.with_suffix(".tmp-" + state["run_id"])
        tmp.write_text(body, encoding="utf-8")
        os.replace(tmp, path)
        state["report_hashes"][path.name] = digest(path)


def reference_valid(result, evidence):
    seen = 0
    for app in result["apps"]:
        if app["observation_kind"] == "unavailable":
            if app["evidence_ids"]:
                raise Blocked("Unavailable reference claims screenshot evidence")
            continue
        parsed = urllib.parse.urlparse(app["url"])
        if parsed.scheme not in ("http", "https") or not app["checked_at"]:
            raise Blocked("Reference source/date is missing")
        if not app["patterns"] or not app["evidence_ids"] or not all(
                i in evidence and evidence[i]["source"] == "official_reference" for i in app["evidence_ids"]):
            raise Blocked("Reference app lacks observed images or useful patterns")
        seen += 1
    if result["status"] == "ready" and (len(result["apps"]) < 3 or seen < 1):
        raise Blocked("Reference comparison claimed ready without three attempted candidates")


def persist(state, run_dir):
    atomic_json(run_dir / "state.json", state)
    atomic_json(run_dir / "status.json", {
        "run_id": state["run_id"], "status": state["status"], "reason": state.get("reason", ""),
        "iteration": state["iteration"], "updated_at": now(),
        "counts": counts(state["audit"]) if state.get("audit") else {},
        "screens": observed_counts(state)[0],
        "flows": observed_counts(state)[1],
    })


def workflow(state, run_dir):
    project = Path(state["config"]["project"])
    assert_source(state["expected_source"], project)
    if not state.get("plan"):
        result, evidence, _ = run_role("planner", PLAN_SCHEMA, state, run_dir, 0)
        validate_plan(result, evidence)
        state["plan"], state["plan_evidence"] = result, evidence
        state["evidence"] = evidence
        persist(state, run_dir)
    if not state.get("references"):
        result, evidence, _ = run_role("references", REFERENCE_SCHEMA, state, run_dir, 0)
        reference_valid(result, evidence)
        state["references"], state["reference_evidence"] = result, evidence
        persist(state, run_dir)
    if not state.get("audit"):
        result, evidence, _ = run_role("reviewer", AUDIT_SCHEMA, state, run_dir, 0)
        validate_audit(result, evidence, state["plan"])
        state["audit"], state["evidence"] = result, evidence
        state["baseline_audit"], state["baseline_evidence"] = result, evidence
        state["baseline_simplicity"] = result["simplicity"]
        persist(state, run_dir)
    if state["config"]["mode"] == "audit":
        state["status"] = "reviewed"
        state["reason"] = "レビューのみ。アプリコードの修正は行っていません。"
        if state["references"]["status"] != "ready":
            state["reason"] += " 類似アプリ比較は未完了: " + state["references"]["reason"]
        publish(state, run_dir)
        persist(state, run_dir)
        return 0
    if not state.get("tests"):
        state["tests"] = run_tests(state, run_dir)
    reasons = gate(state["audit"], state["plan"], state["references"], state["tests"])
    score = metric(state["audit"], reasons)
    state.setdefault("best_metric", score)
    state.setdefault("plateau", 0)
    while reasons and state["iteration"] < state["config"]["max_iterations"]:
        priorities = sorted([i for i in state["audit"]["issues"] if i["status"] != "resolved"],
                            key=lambda i: (SEVERITIES.index(i["severity"]), i["id"]))
        if not priorities:
            state["status"] = "incomplete"
            state["reason"] = "; ".join(reasons)
            publish(state, run_dir)
            persist(state, run_dir)
            return 2
        groups = list(dict.fromkeys(i["root_cause"] or i["id"] for i in priorities))[:3]
        state["selected_issues"] = [i for i in priorities if (i["root_cause"] or i["id"]) in groups]
        state["iteration"] += 1
        assert_source(state["expected_source"], project)
        before = state["expected_source"]
        state["status"] = "running"
        state["fix_in_progress"] = True
        persist(state, run_dir)
        result, _, role_dir = run_role("fixer", FIX_SCHEMA, state, run_dir, state["iteration"])
        actual = fingerprint(project)
        declared = set(result["changed_files"])
        if any(Path(p).is_absolute() or ".." in Path(p).parts for p in declared):
            raise Blocked("Fixer declared invalid source paths")
        changed = {k for k in before["files"].keys() | actual["files"].keys()
                   if before["files"].get(k) != actual["files"].get(k)}
        if actual["head"] != before["head"] or not changed.issubset(declared):
            raise Blocked("Unexpected source changes during fix; preserved all changes")
        if not set(result["fixed_issue_ids"]).issubset({i["id"] for i in state["selected_issues"]}):
            raise Blocked("Fixer claimed issues outside the selected batch")
        state["expected_source"] = actual
        state["fix_in_progress"] = False
        state["history"].append({"iteration": state["iteration"], "fix": result,
                                 "source": actual, "role_dir": str(role_dir)})
        # A failed subsequent reviewer can resume from this source without re-running the fixer.
        state["pending_review"] = True
        state["tests"] = run_tests(state, run_dir)
        persist(state, run_dir)
        old = state["audit"]
        result, evidence, _ = run_role("reviewer", AUDIT_SCHEMA, state, run_dir, state["iteration"])
        validate_audit(result, evidence, state["plan"], old)
        state["audit"], state["evidence"] = result, evidence
        state["pending_review"] = False
        reasons = gate(result, state["plan"], state["references"], state["tests"])
        current = metric(result, reasons)
        if current < state["best_metric"]:
            state["best_metric"], state["plateau"] = current, 0
        else:
            state["plateau"] += 1
        state["reason"] = "; ".join(reasons)
        publish(state, run_dir)
        persist(state, run_dir)
        if reasons and state["plateau"] >= 2:
            state["status"] = "stalled"
            break
    if not reasons:
        state["status"], state["reason"] = "passed", "主要操作・重大問題・画像・検証・簡潔さの条件を確認しました。"
    elif state["status"] != "stalled":
        state["status"], state["reason"] = "incomplete", "; ".join(reasons)
    publish(state, run_dir)
    persist(state, run_dir)
    return 0 if state["status"] == "passed" else 2


def execution(args):
    if os.environ.get("UX_GAN_CHILD") == "1":
        raise Blocked("Recursive harness execution refused inside a child role")
    project = Path(args.project).resolve()
    if not project.is_dir():
        raise Blocked("Project directory does not exist")
    artifacts = project / "artifacts/ux-gan"
    artifacts.mkdir(parents=True, exist_ok=True)
    lock = (artifacts / ".lock").open("a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise Blocked("Another harness is already running for this project")
    process, server_log, state, run_dir = None, None, None, None
    try:
        if args.mode == "resume":
            if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_id):
                raise Blocked("Invalid run ID")
            run_dir = artifacts / args.run_id
            state = json.loads((run_dir / "state.json").read_text())
            if Path(state["config"]["project"]) != project:
                raise Blocked("Run belongs to a different project")
            if state.get("fix_in_progress"):
                raise Blocked("Fix phase was interrupted or unvalidated; preserve the diff and start a new audit/run")
            assert_source(state["expected_source"], project)
            if state["status"] in ("passed", "reviewed"):
                log("Already complete: " + state["run_id"])
                return 0
        else:
            parsed = urllib.parse.urlparse(args.url or "")
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise Blocked("--url must be a reachable http/https app URL")
            run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
            run_dir = artifacts / run_id
            run_dir.mkdir()
            config = {"project": str(project), "url": args.url, "mode": args.mode,
                      "start_command": args.start_command, "test_commands": args.test_command,
                      "reference_urls": args.reference_url, "max_iterations": args.max_iterations,
                      "phase_timeout": args.phase_timeout, "model": args.model,
                      "browser": args.browser, "brief": args.brief}
            rule_paths = []
            for parent in [*reversed(project.parents), project]:
                for name in ("AGENTS.md", "CONTRIBUTING.md"):
                    if (parent / name).is_file():
                        rule_paths.append(str(parent / name))
            state = {"version": VERSION, "run_id": run_id, "config": config, "status": "running",
                     "iteration": 0, "history": [], "rules": rule_paths,
                     "expected_source": fingerprint(project),
                     "report_hashes": {r: digest(project / "docs" / r) if (project / "docs" / r).exists()
                                      else None for r in REPORTS},
                     "started_at": now(), "reason": ""}
            review = Path(args.review).resolve() if args.review else project / "docs/ui-ux-review.md"
            state["input_review"] = snapshot_review(review, run_dir)
            for report in REPORTS[1:]:
                snapshot_review(project / "docs" / report, run_dir)
        log("RUN_ID=" + state["run_id"] + " / " + str(run_dir))
        checks = capabilities()
        if not checks["codex_exec"]:
            raise Blocked("Codex CLI with structured exec output is required")
        if not checks["design_references"]:
            raise Blocked(checks["design_error"])
        sandbox_smoke(project)
        if "backend" not in state:
            state["backend"], state["fallback_reason"] = select_backend(state["config"])
        if state["backend"] == "local-playwright":
            browser_smoke()
        persist(state, run_dir)
        # Reuse an existing ready server. Only own/stop a process that we started.
        try:
            with urllib.request.urlopen(state["config"]["url"], timeout=2) as r:
                ready = r.status < 500
        except (OSError, urllib.error.URLError):
            ready = False
        if not ready and state["config"]["start_command"]:
            server_log = (run_dir / "preview.log").open("w")
            os.chmod(run_dir / "preview.log", 0o600)
            process = subprocess.Popen(["bash", "-c", state["config"]["start_command"]],
                                       cwd=project, stdin=subprocess.DEVNULL, stdout=server_log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
        wait_ready(state["config"]["url"], process)
        if state.get("pending_review"):
            result, evidence, _ = run_role("reviewer", AUDIT_SCHEMA, state, run_dir, state["iteration"])
            validate_audit(result, evidence, state["plan"], state["audit"])
            state["audit"], state["evidence"], state["pending_review"] = result, evidence, False
            state["tests"] = run_tests(state, run_dir)
            persist(state, run_dir)
        return workflow(state, run_dir)
    except (Blocked, Cancelled, KeyboardInterrupt, OSError, ValueError) as e:
        status = "cancelled" if isinstance(e, (Cancelled, KeyboardInterrupt)) else "blocked"
        if state is not None and run_dir is not None:
            state["status"], state["reason"] = status, str(e) or "Interrupted"
            # Do not publish stale baseline images after an unreviewed source fix.
            if state.get("audit") and not state.get("pending_review") and not state.get("fix_in_progress"):
                with contextlib.suppress(Blocked):
                    assert_source(state["expected_source"], project)
                    publish(state, run_dir)
            persist(state, run_dir)
        log(status + ": " + (str(e) or "Interrupted"))
        return 130 if status == "cancelled" else 1
    finally:
        terminate(process)
        if server_log:
            server_log.close()
            preview = run_dir / "preview.log"
            with contextlib.suppress(OSError):
                preview.write_text(scrub(preview.read_text(errors="replace")), encoding="utf-8")
        lock.close()


def parser():
    p = argparse.ArgumentParser(description="Screenshot-first Codex UI/UX review and fix harness")
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="mode", required=True)
    for mode in ("audit", "run", "resume", "doctor"):
        cmd = sub.add_parser(mode)
        cmd.add_argument("--project", default=".")
        if mode == "doctor":
            continue
        if mode == "resume":
            cmd.add_argument("run_id")
            continue
        cmd.add_argument("--url", required=True)
        cmd.add_argument("--start-command")
        cmd.add_argument("--test-command", action="append", default=[])
        cmd.add_argument("--review")
        cmd.add_argument("--reference-url", action="append", default=[])
        cmd.add_argument("--max-iterations", type=int, default=5)
        cmd.add_argument("--phase-timeout", type=int, default=1800)
        cmd.add_argument("--model")
        cmd.add_argument("--browser", choices=["auto", "local-playwright"], default="auto")
        cmd.add_argument("--brief", default="初見ユーザーが迷わず使えるかを画像で検証する。画面を煩雑にせず主要操作を分かりやすくする。")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if args.mode not in ("doctor", "resume") and (args.max_iterations < 1 or args.phase_timeout < 1):
        raise Blocked("Iteration/time limits must be positive")
    def interrupt(_sig, _frame):
        raise Cancelled("Interrupted; existing edits/evidence preserved")
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    return doctor(args) if args.mode == "doctor" else execution(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Blocked, OSError, ValueError) as exc:
        log("blocked: " + str(exc))
        sys.exit(1)
