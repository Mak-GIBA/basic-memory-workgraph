#!/usr/bin/env python3
"""Local, explicit Workgraph review, Markdown sharing, Case JSONL and Skill registration."""

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile

from workgraph_sequence import sequence_issues

try:
    import yaml
except ImportError:
    yaml = None


MAX_BYTES = 8 * 1024 * 1024
NOTE_FOLDERS = {"rules", "workflows", "validations", "cases", "corrections", "artifacts", "projects"}
REVIEW_KEYS = {"privacy_review", "review_sha256"}
SHARED_KEYS = {"title", "type", "tags", "schema", "sharing_scope", "training_use",
               "capture_kind", "case_format_version", "integrity_status"}
SENSITIVE = (
    ("private key", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("credential", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b")),
    ("bearer token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}")),
    ("credential assignment", re.compile(r'''(?i)\b(?:api[_-]?key|access[_-]?token|password|secret|authorization)\b["']?\s*[:=]\s*["']?(?!null\b|none\b|\[REDACTED\]|<REDACTED>)[^\s"',}]{6,}''')),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("local path", re.compile(r"(?:/(?:home|Users|root|tmp)/[^\s]+|[A-Za-z]:\\[^\s]+)")),
    ("URL credentials", re.compile(r"https?://[^\s/]+:[^\s/]+@")),
)
WIKI = re.compile(r"!?\[\[([^\]\n]+)\]\]")
MD_LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")


class Invalid(ValueError):
    pass


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_yaml(text):
    if yaml is None:
        raise Invalid("PyYAML is required; install requirements-export.txt in a virtual environment")
    class Loader(yaml.SafeLoader):
        pass
    def mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise Invalid("YAML keys must be unique strings")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result
    Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    try:
        if any(isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken))
               for token in yaml.scan(text)):
            raise Invalid("YAML anchors and aliases are not supported")
        result = yaml.load(text, Loader=Loader)
        if not isinstance(result, dict):
            raise Invalid("Expected YAML object")
        return result
    except yaml.YAMLError:
        raise Invalid("Invalid YAML frontmatter") from None


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Invalid("Duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(text, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(Invalid("Nonfinite JSON number")))
    except (json.JSONDecodeError, UnicodeError):
        raise Invalid("Invalid JSON") from None


def no_symlink(path):
    path = path.expanduser().absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise Invalid("Symlink paths are not supported")
    return path


def relative_path(value):
    if not isinstance(value, str) or "\\" in value:
        raise Invalid("Invalid relative path")
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or any(p in ("", ".", "..") for p in value.split("/"))
            or any(ord(c) < 32 for c in value) or ":" in value):
        raise Invalid("Unsafe relative path")
    if len(path.parts) < 2 or path.parts[0] not in NOTE_FOLDERS or path.suffix != ".md":
        raise Invalid("Only Markdown notes in known note folders are supported")
    return Path(*path.parts)


def read_text(path):
    no_symlink(path)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise Invalid("Missing, oversized, or nonregular file")
    return path.read_text(encoding="utf-8")


def screen(text):
    for name, pattern in SENSITIVE:
        if pattern.search(text):
            raise Invalid(f"Privacy screening failed: {name}; sanitize and review again")


@dataclass
class Note:
    path: str
    metadata: dict
    body: str

    def render(self):
        return "---\n" + yaml.safe_dump(self.metadata, allow_unicode=True, sort_keys=False) + "---\n" + self.body

    def fingerprint(self):
        # Ignore only the review stamp, not sharing/training permissions or content.
        values = {k: v for k, v in self.metadata.items() if k not in REVIEW_KEYS}
        return sha((json_text(values) + self.body).encode())

    def reviewed(self):
        return (self.metadata.get("privacy_review") == "passed"
                and self.metadata.get("review_sha256") == self.fingerprint())


def parse_note(text, path):
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", text, re.S)
    if not match:
        raise Invalid("Note needs YAML frontmatter")
    metadata = safe_yaml(match[1])
    # Normalize YAML timestamps as Basic Memory does, without changing note body.
    def normalize(value):
        if isinstance(value, dict):
            return {k: normalize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [normalize(v) for v in value]
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if value is None or isinstance(value, (str, bool, int, float)):
            return value
        raise Invalid("Unsupported frontmatter value")
    metadata = normalize(metadata)
    if not isinstance(metadata.get("title"), str) or not isinstance(metadata.get("type"), str):
        raise Invalid("Note title/type must be strings")
    return Note(path, metadata, match[2])


def load_note(root, relative):
    rel = relative_path(relative)
    return parse_note(read_text(root / rel), rel.as_posix())


def iter_notes(root):
    for folder in sorted(NOTE_FOLDERS):
        directory = root / folder
        no_symlink(directory)
        if directory.exists():
            for path in sorted(directory.rglob("*")):
                no_symlink(path)
                if path.suffix == ".md" and path.is_file():
                    yield path.relative_to(root).as_posix()


def text_piece(value, nullable=False):
    if value is None and nullable:
        return
    if (not isinstance(value, dict) or set(value) != {"summary", "excerpt"}
            or not isinstance(value["summary"], str) or not value["summary"].strip()
            or (value["excerpt"] is not None and not isinstance(value["excerpt"], str))):
        raise Invalid("Interaction text requires summary and optional excerpt")


def interaction_data(note):
    meta = note.metadata
    if (meta.get("type", "").lower() != "case" or meta.get("capture_kind") != "interaction_case"
            or type(meta.get("case_format_version")) is not int or meta["case_format_version"] not in (1, 2)):
        raise Invalid("Not a supported structured Case v1/v2")
    # The dedicated section is the sole canonical payload. No prose reconstruction.
    sections = re.findall(r"^## Interaction\s*\n(.*?)(?=^## |\Z)", note.body, re.M | re.S)
    if len(sections) != 1:
        raise Invalid("Expected one Interaction section")
    blocks = re.findall(r"^```json\s*\n(.*?)^```\s*$", sections[0], re.M | re.S)
    if len(blocks) != 1:
        raise Invalid("Expected one JSON interaction block")
    data = strict_json(blocks[0])
    if (not isinstance(data, dict) or type(data.get("version")) is not int
            or data["version"] != meta["case_format_version"]):
        raise Invalid("Interaction version does not match frontmatter")
    return data


def interaction(note):
    data = interaction_data(note)
    if data["version"] == 2:
        issues = sequence_issues(data)
        if issues:
            # Only controlled codes/locations, never user-supplied text in errors.
            raise Invalid("Invalid progressive Case: " + issues[0]["code"] + " at " + issues[0]["location"])
        return data
    expected = {"version", "request", "initial", "corrections", "final", "outcome", "acceptance",
                "checks", "lessons", "transfer_use"}
    if not isinstance(data, dict) or set(data) != expected or type(data["version"]) is not int or data["version"] != 1:
        raise Invalid("Unsupported or incomplete interaction shape")
    for key in ("request", "initial", "final"):
        text_piece(data[key], nullable=key == "initial")
    if not isinstance(data["corrections"], list):
        raise Invalid("Corrections must be an ordered array")
    for item in data["corrections"]:
        if not isinstance(item, dict) or set(item) != {"feedback", "change", "result"}:
            raise Invalid("Invalid correction round")
        for key in item:
            text_piece(item[key], nullable=key == "result")
    if data["outcome"] not in ("verified", "partial", "unverified", "rejected"):
        raise Invalid("Invalid outcome")
    if data["acceptance"] not in ("accepted", "rejected", "unknown"):
        raise Invalid("Invalid acceptance")
    for key in ("checks", "lessons"):
        if not isinstance(data[key], list) or any(not isinstance(v, str) or not v.strip() for v in data[key]):
            raise Invalid("Checks and lessons must be string arrays")
    if data["outcome"] == "verified" and not data["checks"]:
        raise Invalid("Verified cases require performed checks")
    if not isinstance(data["transfer_use"], str) or not data["transfer_use"].strip():
        raise Invalid("A concrete transfer use is required")
    return data


def atomic_file(path, content, replace=False):
    path = no_symlink(path)
    if path.exists() and not replace:
        raise Invalid("Output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
        f.write(content.encode())
    try:
        if replace:
            temporary.replace(path)
        else:
            # link is exclusive even if another process created the output meanwhile.
            os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def review(args):
    root = no_symlink(args.memory_dir)
    note = load_note(root, args.note)
    require_integrity(note)
    note.metadata.update(sharing_scope=args.sharing, training_use=args.training)
    if args.training == "approved" or note.metadata.get("capture_kind") == "interaction_case":
        screen(json_text(interaction(note)))
    screen(note.render())
    note.metadata["privacy_review"] = "passed"
    note.metadata["review_sha256"] = note.fingerprint()
    if not args.dry_run:
        atomic_file(root / note.path, note.render(), replace=True)
    return {"reviewed": 1, "dry_run": args.dry_run}


def export_path(root, output):
    output = no_symlink(output)
    if output == root or root in output.parents:
        raise Invalid("Export destination must be outside the memory directory")
    if output.exists():
        raise Invalid("Output already exists")
    return output


def alias_index(notes):
    index = {}
    for note in notes:
        path = PurePosixPath(note.path)
        for alias in (note.path, str(path.with_suffix("")), path.stem,
                      note.metadata["title"], note.metadata.get("permalink")):
            if isinstance(alias, str) and alias:
                index.setdefault(alias, set()).add(note.path)
    return index


def sanitize_links(body, index, included):
    def wiki(match):
        target = match[1].split("|", 1)[0].split("#", 1)[0].strip()
        matches = index.get(target, set())
        if len(matches) != 1 or not matches <= included:
            return "[omitted]"
        return "[[" + str(PurePosixPath(next(iter(matches))).with_suffix("")) + "]]"
    def inline(text):
        changed = WIKI.sub(wiki, text)
        return MD_LINK.sub(lambda m: m[0] if m[1].startswith("https://") else "[omitted]", changed)

    def json_value(value):
        if isinstance(value, str):
            return inline(value)
        if isinstance(value, list):
            return [json_value(v) for v in value]
        if isinstance(value, dict):
            return {k: json_value(v) for k, v in value.items()}
        return value

    # Re-encode JSON instead of interpolating Markdown targets into JSON strings.
    # This preserves valid interaction data even when filenames contain quotes.
    blocks = {}
    def json_block(match):
        token = f"WORKGRAPH_JSON_BLOCK_{len(blocks)}_{sha(body.encode())}"
        blocks[token] = "```json\n" + json_text(json_value(strict_json(match[1]))) + "```\n"
        return token + "\n"
    body = re.sub(r"^```json\s*\n(.*?)^```\s*$", json_block, body, flags=re.M | re.S)
    lines = []
    for line in body.splitlines(keepends=True):
        if line.strip() in blocks:
            lines.append(blocks[line.strip()])
            continue
        changed = WIKI.sub(wiki, line)
        # Avoid exporting meaningless relation lines or leaking their descriptive text.
        if "[omitted]" in changed and re.match(r"^\s*-\s+\w+\s+\[\[", line):
            continue
        # Only external HTTPS links survive; local links/labels and file URIs do not.
        changed = MD_LINK.sub(lambda m: m[0] if m[1].startswith("https://") else "[omitted]", changed)
        lines.append(changed)
    return "".join(lines)


def skipped_note(relative, reason):
    try:
        screen(relative)
        label = relative
    except Invalid:
        label = "sha256:" + sha(relative.encode())
    return {"note": label, "reason": reason}


def integrity_status(note):
    status = note.metadata.get("integrity_status", "unreviewed")
    if status not in ("unreviewed", "checked", "needs_review"):
        raise Invalid("Invalid integrity status")
    return status


def require_integrity(note):
    if integrity_status(note) == "needs_review":
        raise Invalid("Knowledge needs integrity review before export permission can be used")
    # Even a checked status never bypasses validation of current content.
    if note.metadata.get("capture_kind") == "interaction_case":
        interaction(note)


def audit(args):
    """Read-only diagnostics and bounded dependency candidates, never auto-repair."""
    root = no_symlink(args.memory_dir)
    if not root.is_dir():
        raise Invalid("Memory directory does not exist")
    selected = relative_path(args.note).as_posix() if args.note else None
    notes, issues, legacy = {}, [], []

    def report(path, code, location, action):
        # Paths can contain personal data; never echo content, titles, IDs or links.
        label = skipped_note(path, "")["note"]
        issues.append({"note": label, "code": code, "location": location, "action": action})

    paths = list(iter_notes(root))
    if selected and selected not in paths:
        raise Invalid("Audit target is not an existing note in a known folder")
    inspected = set(paths if selected is None else [selected])
    for path in paths:
        try:
            notes[path] = load_note(root, path)
        except (Invalid, UnicodeError, OSError, TypeError, RecursionError):
            if path in inspected:
                report(path, "invalid_note", "/", "Check note structure locally; contents are omitted from this report.")
    for path in sorted(inspected & notes.keys()):
        note = notes[path]
        try:
            screen(note.render())
            screen(path)
        except Invalid:
            report(path, "privacy_concern", "/", "Sanitize locally before sharing; do not copy private text into a repair log.")
        try:
            if integrity_status(note) == "needs_review":
                report(path, "needs_review", "/integrity_status", "Resolve the recorded concern against available evidence before positive reuse.")
        except Invalid:
            report(path, "invalid_integrity_status", "/integrity_status", "Use unreviewed, checked, or needs_review.")
        if note.metadata.get("capture_kind") == "interaction_case":
            try:
                data = interaction_data(note)
                if data["version"] == 2:
                    for item in sequence_issues(data):
                        report(path, item["code"], item["location"], item["action"])
                else:
                    interaction(note)
            except (Invalid, TypeError, RecursionError):
                report(path, "invalid_interaction", "/Interaction", "Inspect the declared format and canonical JSON; do not reconstruct missing history.")
        elif note.metadata.get("type", "").lower() == "case":
            legacy.append(skipped_note(path, "Legacy freeform Case; no structured sequence checks performed"))

    index = alias_index(notes.values())
    dependents = {}
    for path, note in notes.items():
        # Parse relation lines only, never infer dependencies from ordinary mentions.
        for kind, target in re.findall(r"^- (\w+) \[\[([^\]\n]+)\]\]\s*$", note.body, re.M):
            matches = index.get(target.split("|", 1)[0].split("#", 1)[0].strip(), set())
            if len(matches) != 1:
                if path in inspected:
                    report(path, "unresolved_relation", "/Relations", "Check the destination, ambiguity or external project; do not delete the relation automatically.")
                continue
            destination = next(iter(matches))
            if kind in ("generalized_to", "learned", "packaged_as"):
                dependents.setdefault(path, set()).add(destination)
            elif kind in ("learned_from", "occurred_in", "implements", "implements_workflow"):
                dependents.setdefault(destination, set()).add(path)

    flagged = {path for path in inspected if any(
        item["note"] == skipped_note(path, "")["note"] for item in issues)}
    affected = []
    for source in sorted(flagged):
        seen, frontier = {source}, {source}
        for depth in (1, 2):
            next_level = set()
            for parent in frontier:
                next_level.update(dependents.get(parent, set()) - seen)
            for target in sorted(next_level):
                affected.append({"note": skipped_note(target, "")["note"],
                                 "source": skipped_note(source, "")["note"], "depth": depth,
                                 "action": "Inspect affected claims and independent evidence; do not invalidate the entire note automatically."})
            seen.update(next_level)
            frontier = next_level
    return {"read_only": True, "checked": len(inspected), "issues": issues,
            "affected": affected, "legacy": legacy,
            "limits": "Structural checks only. A clean result does not verify chronology, evidence truth, or user satisfaction."}


def candidates(root, predicate):
    if not root.is_dir():
        raise Invalid("Memory directory does not exist")
    notes, selected, skipped = [], [], []
    for rel in iter_notes(root):
        try:
            note = load_note(root, rel)
            notes.append(note)
            if predicate(note):
                require_integrity(note)
                if not note.reviewed():
                    raise Invalid("Missing or stale privacy review")
                selected.append(note)
        except (Invalid, UnicodeError) as exc:
            skipped.append(skipped_note(rel, str(exc)))
    return notes, selected, skipped


def export_share(args):
    root = no_symlink(args.memory_dir)
    output = export_path(root, args.output)
    all_notes, selected, skipped = candidates(root, lambda n:
        n.metadata.get("sharing_scope", "private") == args.scope
        and (args.include_cases or PurePosixPath(n.path).parts[0] != "cases"))
    index = alias_index(all_notes)
    # Preflight raw notes as well as transformed output. Removal of known private
    # links is permitted, but cannot be used to hide a failed privacy review.
    safe = []
    for note in selected:
        try:
            screen(note.render())
            screen(note.path)
            if note.metadata.get("capture_kind") == "interaction_case":
                screen(json_text(interaction(note)))
            screen(sanitize_links(note.body, index, set()))
            safe.append(note)
        except Invalid as exc:
            skipped.append(skipped_note(note.path, str(exc)))
    included = {n.path for n in safe}
    contents = {}
    for note in safe:
        meta = {k: v for k, v in note.metadata.items() if k in SHARED_KEYS}
        # Shared files carry no training authorization into another environment.
        meta["training_use"] = "excluded"
        meta["privacy_review"] = "pending"
        exported = Note(note.path, meta, sanitize_links(note.body, index, included))
        if meta.get("capture_kind") == "interaction_case":
            interaction(exported)
        screen(exported.render())
        contents[note.path] = exported.render()
    manifest = {"version": 1, "scope": args.scope, "notes": [
        {"path": p, "sha256": sha(c.encode())} for p, c in sorted(contents.items())]}
    if not args.dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".workgraph-share-", dir=output.parent))
        try:
            for rel, content in contents.items():
                atomic_file(stage / rel, content)
            atomic_file(stage / "manifest.json", json_text(manifest))
            stage.rename(output)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return {"exported": len(contents), "skipped": skipped, "dry_run": args.dry_run}


def import_share(args):
    root, bundle = no_symlink(args.memory_dir), no_symlink(args.bundle)
    manifest = strict_json(read_text(bundle / "manifest.json"))
    if (not isinstance(manifest, dict) or manifest.get("version") != 1
            or manifest.get("scope") not in ("team", "public") or not isinstance(manifest.get("notes"), list)):
        raise Invalid("Unsupported share manifest")
    pending, unchanged, conflicts, seen = [], 0, [], set()
    for entry in manifest["notes"]:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise Invalid("Invalid manifest entry")
        rel = relative_path(entry["path"]).as_posix()
        if rel in seen:
            raise Invalid("Duplicate manifest path")
        seen.add(rel)
        text = read_text(bundle / rel)
        if sha(text.encode()) != entry["sha256"]:
            raise Invalid("Bundle content checksum mismatch")
        screen(text)
        screen(rel)
        note = parse_note(text, rel)
        # An import is reference data, not an attestation that the knowledge is sound.
        status = integrity_status(note)
        note.metadata = {k: v for k, v in note.metadata.items() if k in SHARED_KEYS}
        if "integrity_status" in note.metadata:
            note.metadata["integrity_status"] = "needs_review" if status == "needs_review" else "unreviewed"
        note.metadata.update(sharing_scope="private", training_use="excluded", privacy_review="pending",
                             import_source=rel)
        content = note.render()
        target = no_symlink(root / rel)
        if target.exists():
            if read_text(target) == content:
                unchanged += 1
            else:
                conflicts.append(rel)
        else:
            pending.append((target, content))
    actual = set()
    for path in bundle.rglob("*"):
        no_symlink(path)
        if path.is_file():
            actual.add(path.relative_to(bundle).as_posix())
    if actual != seen | {"manifest.json"}:
        raise Invalid("Bundle has unlisted or missing files")
    if conflicts:
        return {"imported": 0, "unchanged": unchanged, "conflicts": conflicts, "dry_run": args.dry_run}
    written = []
    if not args.dry_run:
        try:
            for target, content in pending:
                atomic_file(target, content)
                written.append(target)
        except OSError:
            for target in written:
                target.unlink()
            raise
    return {"imported": len(pending), "unchanged": unchanged, "conflicts": [], "dry_run": args.dry_run}


def export_cases(args):
    root = no_symlink(args.memory_dir)
    output = export_path(root, args.output)
    all_notes, selected, skipped = candidates(root, lambda n:
        PurePosixPath(n.path).parts[0] == "cases" and n.metadata.get("training_use") == "approved")
    index = alias_index(all_notes)
    rows = []
    for note in selected:
        try:
            data = interaction(note)
            screen(note.render())
            screen(json_text(data))
            screen(note.path)
            # Related nodes are identifiers only: never follow links into private data.
            relations = []
            for kind, target in re.findall(r"^- (\w+) \[\[([^\]\n]+)\]\]\s*$", note.body, re.M):
                # Keep opaque references, not potentially identifying titles or paths.
                matches = index.get(target.split("|", 1)[0].split("#", 1)[0].strip(), set())
                if len(matches) == 1:
                    relations.append({"type": kind, "target_id": sha(next(iter(matches)).encode())})
            row = {"format_version": 1, "source_id": sha(note.path.encode()),
                   "interaction": data, "relations": relations}
            if data["version"] == 2:
                row["integrity_status"] = integrity_status(note)
            rows.append(row)
        except Invalid as exc:
            skipped.append(skipped_note(note.path, str(exc)))
    if not args.dry_run:
        atomic_file(output, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))
    return {"exported": len(rows), "skipped": skipped, "dry_run": args.dry_run}


SKILL_MANIFEST = ".workgraph-registration.json"


def skill_files(source):
    source = no_symlink(source)
    if not source.is_dir():
        raise Invalid("Skill source must be a directory")
    files = {}
    for path in sorted(source.rglob("*")):
        no_symlink(path)
        if path.is_dir():
            continue
        rel = path.relative_to(source).as_posix()
        if rel == SKILL_MANIFEST:
            continue
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise Invalid("Unsupported Skill resource")
        if any(part.startswith(".") for part in Path(rel).parts):
            raise Invalid("Hidden Skill resources are not supported")
        data = path.read_bytes()
        try:
            screen(data.decode("utf-8"))
        except UnicodeDecodeError:
            pass  # Binary assets require the reviewer's inspection.
        files[rel] = sha(data)
    if "SKILL.md" not in files:
        raise Invalid("SKILL.md is required")
    return files


def skill_digest(args):
    files = skill_files(args.source)
    return {"source_sha256": sha(json_text(files).encode()), "files": len(files)}


def register_skill(args):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.name) or len(args.name) >= 64:
        raise Invalid("Invalid Skill name")
    codex = no_symlink(args.codex_dir)
    config = strict_json(read_text(codex / "basic-memory-workgraph/config.json"))
    if (not isinstance(config, dict) or config.get("mode", "smart") not in ("smart", "always")
            or config.get("skillMode", "review") != "auto"):
        raise Invalid("Skill registration requires auto persistence and skillMode=auto")
    if not args.workflow.strip():
        raise Invalid("Originating Workflow reference is required")
    screen(args.workflow)
    source = no_symlink(args.source)
    files = skill_files(source)
    skill_text = read_text(source / "SKILL.md")
    match = re.match(r"\A---\n(.*?)\n---\n(.+)\Z", skill_text, re.S)
    if not match:
        raise Invalid("Skill needs frontmatter and instructions")
    meta = safe_yaml(match[1])
    if meta.get("name") != args.name or not isinstance(meta.get("description"), str) or not meta["description"].strip():
        raise Invalid("Skill name/description do not match registration")
    validation = strict_json(read_text(args.validation))
    if (not isinstance(validation, dict) or validation.get("passed") is not True
            or validation.get("decision") not in ("create_skill", "update_existing")
            or not isinstance(validation.get("reviewer"), str) or not validation["reviewer"].strip()
            or not isinstance(validation.get("checks"), list) or not validation["checks"]
            or any(not isinstance(v, str) or not v.strip() for v in validation["checks"])
            or validation.get("source_sha256") != sha(json_text(files).encode())):
        raise Invalid("Successful review and validation bound to the current Skill content are required")
    screen(json_text(validation))
    skills = no_symlink(codex / "skills")
    target = no_symlink(skills / args.name)
    if source == target or target in source.parents or source in target.parents:
        raise Invalid("Stage Skills outside their registration destination")
    manifest = {"version": 1, "name": args.name, "workflow": args.workflow, "files": files,
                "validation": validation}
    if target.exists():
        old = strict_json(read_text(target / SKILL_MANIFEST))
        if (not isinstance(old, dict) or old.get("version") != 1 or old.get("name") != args.name
                or old.get("workflow") != args.workflow or old.get("files") != skill_files(target)):
            raise Invalid("Target is unmanaged, user-modified, or belongs to another Workflow")
        if old["files"] == files:
            return {"registered": 0, "unchanged": 1, "dry_run": args.dry_run}
        if validation["decision"] != "update_existing":
            raise Invalid("Replacing a managed Skill requires update_existing review")
    elif validation["decision"] != "create_skill":
        raise Invalid("New registration requires create_skill review")
    if args.dry_run:
        return {"registered": 1, "unchanged": 0, "dry_run": True}
    codex.mkdir(parents=True, exist_ok=True)
    skills.mkdir(parents=True, exist_ok=True)
    # Stage outside discoverable skills; same filesystem as the destination.
    stage = Path(tempfile.mkdtemp(prefix=".workgraph-skill-", dir=codex))
    backup = None
    published = False
    try:
        for rel in files:
            dest = stage / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / rel, dest)
        if skill_files(stage) != files:
            raise Invalid("Skill changed while staging")
        atomic_file(stage / SKILL_MANIFEST, json_text(manifest))
        if target.exists():
            # Recheck immediately before swapping; preserve the old tree for rollback.
            if strict_json(read_text(target / SKILL_MANIFEST)) != old or skill_files(target) != old["files"]:
                raise Invalid("Registered Skill changed while staging")
            backup = Path(tempfile.mkdtemp(prefix=".workgraph-previous-", dir=codex))
            backup.rmdir()
            target.rename(backup)
        try:
            stage.rename(target)
            published = True
        except OSError:
            if backup is not None:
                backup.rename(target)
                backup = None
            raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        if published and backup is not None and backup.exists():
            shutil.rmtree(backup)
    return {"registered": 1, "unchanged": 0, "dry_run": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command, handler in (("review", review), ("export-share", export_share),
                             ("import-share", import_share), ("export-cases", export_cases)):
        p = sub.add_parser(command)
        p.set_defaults(handler=handler)
        p.add_argument("--memory-dir", type=Path, required=True)
        p.add_argument("--dry-run", action="store_true")
        if command == "review":
            p.add_argument("--note", required=True, help="Relative Markdown path; reviewing attests inspection of sanitized content")
            p.add_argument("--sharing", choices=("private", "team", "public"), default="private")
            p.add_argument("--training", choices=("excluded", "approved"), default="excluded")
        elif command == "import-share":
            p.add_argument("--bundle", type=Path, required=True)
        else:
            p.add_argument("--output", type=Path, required=True)
            if command == "export-share":
                p.add_argument("--scope", choices=("team", "public"), required=True)
                p.add_argument("--include-cases", action="store_true")
    p = sub.add_parser("audit", help="Read-only structural checks; semantic repair remains evidence-driven")
    p.set_defaults(handler=audit)
    p.add_argument("--memory-dir", type=Path, required=True)
    p.add_argument("--note", help="Optional relative note path; otherwise inspect all known note folders")
    p.add_argument("--dry-run", action="store_true", help="Accepted for consistency; audit never writes")
    p = sub.add_parser("skill-digest")
    p.set_defaults(handler=skill_digest)
    p.add_argument("--source", type=Path, required=True)
    p = sub.add_parser("register-skill")
    p.set_defaults(handler=register_skill)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--workflow", required=True)
    p.add_argument("--validation", type=Path, required=True)
    p.add_argument("--codex-dir", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    p.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = args.handler(args)
    except (Invalid, OSError, UnicodeError, TypeError, RecursionError) as exc:
        # Do not echo file contents or YAML parser snippets containing secrets.
        message = str(exc) if isinstance(exc, Invalid) else type(exc).__name__
        parser.exit(1, f"Workgraph operation failed: {message}\n")
    print(json_text(result), end="")
    if result.get("conflicts") or result.get("skipped") or result.get("issues"):
        sys.exit(2)


if __name__ == "__main__":
    main()
