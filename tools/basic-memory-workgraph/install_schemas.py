#!/usr/bin/env python3
"""Install known schema revisions while preserving application metadata and customization."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from configure_workgraph import write_file
from workgraph_tools import safe_yaml, yaml


SOURCE = Path(__file__).resolve().parent


def split_note(text):
    match = re.fullmatch(r"---\r?\n(.*?)\r?\n---\r?\n(.*)", text, re.S)
    if not match:
        raise ValueError("Missing template frontmatter")
    return safe_yaml(match[1]), match[2], match[1]


def equal(left, right):
    """Typed equality: YAML true must not compare equal to schema version 1."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(equal(a, b) for a, b in zip(left, right))
    return left == right


def has_yaml_comments(frontmatter):
    # Be conservative rather than discard potentially meaningful comments during
    # reserialization. A quoted # can also cause a safe skip.
    return bool(re.search(r"(?:^|\s)#", frontmatter))


def migrate(existing, current, historical):
    """Return new text, unchanged text, or None for a genuine/unknown customization."""
    installed, body, raw_yaml = split_note(existing)
    latest, latest_body, _ = split_note(current)
    owned = set(latest)
    previous = [split_note(text)[:2] for text in historical]
    for metadata, _ in previous:
        owned.update(metadata)
    projected = {k: v for k, v in installed.items() if k in owned}
    if equal(projected, latest) and body.strip() == latest_body.strip():
        return existing  # Preserve formatting, timestamps and comments without churn.
    if has_yaml_comments(raw_yaml):
        return None
    for metadata, prior_body in previous:
        if equal(projected, metadata) and body.strip() == prior_body.strip():
            # Only top-level app/user metadata not owned by the template is carried.
            # Custom edits inside schema/settings/body are deliberately not merged.
            merged = {k: v for k, v in installed.items() if k not in owned}
            merged = {**latest, **merged}
            return "---\n" + yaml.safe_dump(merged, allow_unicode=True, sort_keys=False) + "---\n" + latest_body
    return None


def prepare_schemas(memory_dir, source=SOURCE):
    legacy = json.loads((source / "legacy-schema-hashes.json").read_text())
    sources = sorted((source / "templates/schemas").glob("*.md"))
    sources.append(source / "templates/Work-Knowledge-Graph.md")
    changes, preserved = [], []
    for template in sources:
        relative = template.relative_to(source / "templates")
        destination = memory_dir / relative
        content = template.read_text(encoding="utf-8")
        if destination.is_symlink() or any(p.is_symlink() for p in destination.parents):
            raise ValueError(f"Refusing symlink: {destination}")
        if destination.exists():
            old = destination.read_bytes()
            if old == content.encode():
                continue
            # Exact old bytes need no YAML parser (fresh installs/configure-only
            # continue to work with the standard library).
            if hashlib.sha256(old).hexdigest() != legacy.get(relative.as_posix()):
                history = [p.read_text(encoding="utf-8") for p in sorted(
                    (source / "schema-history").glob("*/" + relative.as_posix()))]
                try:
                    migrated = migrate(old.decode("utf-8"), content, history)
                except (ValueError, TypeError, UnicodeError, RecursionError):
                    migrated = None
                if migrated is None:
                    reason = "customized or unrecognized template" if yaml is not None else "PyYAML required for metadata-aware migration"
                    preserved.append({"path": str(destination), "reason": reason, "template": str(template)})
                    continue
                if migrated == old.decode("utf-8"):
                    continue
                content = migrated
        changes.append((destination, content))
    return changes, preserved


def install(memory_dir, dry_run=False):
    changes, preserved = prepare_schemas(memory_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    if not dry_run:
        for path, content in changes:
            write_file(path, content, stamp)
    for item in preserved:
        print(f"Preserved {item['path']}: {item['reason']}; compare with {item['template']}")
    return preserved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        preserved = install(args.memory_dir.expanduser().absolute(), args.dry_run)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Schema installation failed: {exc}\n")
    if preserved:
        parser.exit(2)


if __name__ == "__main__":
    main()
