"""Artifact validation adds file checks to the existing scholarly ledger contract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import socket
import ipaddress
import urllib.error
import urllib.parse
import urllib.request

from dossier import validate_dossier
from runtime import Blocked, atomic_json, now, regular_path, relative, scrub, sha256


def existing_artifact(root, value):
    path = regular_path(Path(root) / relative(value))
    if not path.is_file() or path.stat().st_size == 0:
        raise Blocked(f"Evidence file is missing or empty: {value}")
    return path


def verify_artifacts(data, root, trusted=None):
    """Presence/hashes are verified; neither scientific truth nor human approval is."""
    result = validate_dossier(data)
    errors = list(result["errors"])
    artifacts = {}

    def inspect(value, where):
        try:
            path = existing_artifact(root, value)
            actual = sha256(path)
            if trusted is not None:
                receipt = next((r for r in trusted.values() if r["path"] == value), None)
                if not receipt or receipt["sha256"] != actual:
                    raise Blocked("Artifact has no matching immutable harness record")
            artifacts[value] = actual
        except (Blocked, OSError, TypeError) as exc:
            errors.append(f"{where}: {exc}")

    if isinstance(data, dict):
        for source in data.get("sources", []):
            if isinstance(source, dict) and source.get("local_path"):
                inspect(source["local_path"], f"source {source.get('id')}")
        for experiment in data.get("experiments", []):
            if not isinstance(experiment, dict) or experiment.get("status") != "executed":
                continue
            for path in experiment.get("artifacts", []):
                inspect(path, f"experiment {experiment.get('id')}")
                if trusted is not None:
                    receipt = next((r for r in trusted.values() if r["path"] == path), {})
                    if (receipt.get("kind") != "experiment" or
                            receipt.get("experiment_id") != experiment.get("id") or
                            receipt.get("exit_code") != 0 or receipt.get("timed_out") or
                            receipt.get("truncated")):
                        errors.append(f"experiment {experiment.get('id')}: no successful matching execution")
        if trusted is not None:
            sources = {s["id"]: s for s in data.get("sources", []) if isinstance(s, dict) and "id" in s}
            for claim in data.get("claims", []):
                if not isinstance(claim, dict) or claim.get("status") != "observed":
                    continue
                supporting = [sources.get(e.get("source_id"), {}) for e in claim.get("evidence", [])
                              if isinstance(e, dict) and e.get("relation") == "supports"]
                observed = []
                for source in supporting:
                    record = next((r for r in trusted.values()
                                   if r["path"] == source.get("local_path")), {})
                    if record.get("kind") == "experiment" and record.get("exit_code") == 0:
                        observed.append(record)
                if not observed:
                    errors.append(f"claim {claim.get('id')}: observed needs a real experiment receipt")
    return {**result, "valid": not errors, "errors": errors, "artifacts": artifacts,
            "scope": "Structure, local artifact existence and hashes. Harness receipts are checked "
                     "when supplied. Source truth and human approval are not certified."}


def add_record(state, workspace, path, *, kind, description, **metadata):
    path = regular_path(path)
    if not path.is_file() or path.stat().st_size == 0:
        raise Blocked("Cannot register missing/empty evidence")
    value = path.relative_to(workspace).as_posix()
    key = "EV-" + str(len(state["evidence"]) + 1).zfill(5)
    record = {"id": key, "kind": kind, "description": description, "path": value,
              "sha256": sha256(path), "iteration": state["iteration"], "recorded_at": now(),
              "source_fingerprint": hashlib.sha256(json.dumps(
                  state["expected_source"], sort_keys=True).encode()).hexdigest(), **metadata}
    state["evidence"][key] = record
    return key


def assert_records(state, workspace):
    for record in state["evidence"].values():
        path = existing_artifact(workspace, record["path"])
        if sha256(path) != record["sha256"]:
            raise Blocked(f"Evidence changed after capture: {record['id']}")
        if record["kind"] in {"test", "experiment"}:
            receipt = json.loads(path.read_text("utf-8"))
            for output in receipt["outputs"].values():
                target = regular_path(Path(workspace) / relative(output["path"]))
                if not target.is_file() or sha256(target) != output["sha256"]:
                    raise Blocked(f"Execution output changed: {record['id']}")


def public_url(value):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password):
        raise Blocked("A source needs a credential-free public HTTP(S) URL")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or
                                      (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise Blocked("Source host could not be resolved") from exc
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise Blocked("Private network addresses are not reference sources")
    return value


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def source_receipt(source, destination, allow_network):
    """Archive access metadata, avoiding redistribution of complete papers/webpages."""
    result = {"source_id": source["id"], "title": source["title"], "url": source["url"],
              "locator": source.get("locator", ""), "checked_at": now(),
              "status": "unavailable", "reason": "Live source retrieval was not enabled",
              "read_level_claimed": source.get("read_level", "metadata")}
    if allow_network:
        try:
            public_url(source["url"])
            opener = urllib.request.build_opener(PublicRedirect())
            request = urllib.request.Request(source["url"], headers={
                "User-Agent": "DesignResearch/1.2 (evidence verification)"})
            with opener.open(request, timeout=15) as response:
                body = response.read(5 * 1024 * 1024 + 1)
                if len(body) > 5 * 1024 * 1024 or not body:
                    raise Blocked("Source response is empty or exceeds 5 MB")
                result.update(status="retrieved", reason="Transport access verified; claim "
                              "interpretation remains the reviewer's responsibility",
                              final_url=response.geturl(), bytes=len(body),
                              content_sha256=hashlib.sha256(body).hexdigest(),
                              content_type=response.headers.get("Content-Type", ""))
        except (Blocked, OSError, urllib.error.URLError, ValueError) as exc:
            result["reason"] = scrub(str(exc))
    atomic_json(destination, result)
    return result
