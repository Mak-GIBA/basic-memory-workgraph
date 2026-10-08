#!/usr/bin/env python3
"""Literature discovery and evidence checks for the design-research skill."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from dossier import create_run, validate_dossier
from literature import BASES, Client, ResearchError, clean_query, links, lookup, mark_families, search, utcnow

HERE = Path(__file__).resolve().parent


def bounded_int(low, high):
    def parse(value):
        try:
            n = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be an integer") from exc
        if not low <= n <= high:
            raise argparse.ArgumentTypeError(f"must be in [{low}, {high}]")
        return n
    return parse


def emit(data):
    print(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    network = argparse.ArgumentParser(add_help=False)
    mode = network.add_mutually_exclusive_group()
    mode.add_argument("--allow-network", action="store_true", help="Allow sending a non-sensitive research query to the selected scholarly providers")
    mode.add_argument("--offline", action="store_true", help="Use exact cached responses only; stale entries are labeled")
    network.add_argument("--cache-dir", type=Path, default=Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "design-research")
    network.add_argument("--cache-ttl", type=bounded_int(0, 2592000), default=86400)
    network.add_argument("--timeout", type=bounded_int(1, 30), default=15)
    s = commands.add_parser("search", parents=[network], help="Search one bounded page per provider")
    s.add_argument("--provider", choices=[*BASES, "all"], default="all")
    s.add_argument("--query", required=True)
    s.add_argument("--limit", type=bounded_int(1, 50), default=10, help="Maximum per provider (not a full literature census)")
    s.add_argument("--offset", type=bounded_int(0, 9950), default=0)
    s.add_argument("--year-from", type=bounded_int(1900, 2100))
    s.add_argument("--year-to", type=bounded_int(1900, 2100))
    l = commands.add_parser("lookup", parents=[network], help="Resolve metadata by an exact scholarly identifier")
    l.add_argument("--provider", choices=BASES, required=True)
    l.add_argument("--id", required=True)
    c = commands.add_parser("links", parents=[network], help="Follow one page of Semantic Scholar citations/references")
    c.add_argument("--id", required=True)
    c.add_argument("--direction", choices=["references", "citations"], default="references")
    c.add_argument("--limit", type=bounded_int(1, 50), default=10)
    c.add_argument("--offset", type=bounded_int(0, 9950), default=0)
    init = commands.add_parser("init", help="Create a new, never-overwritten research workspace")
    init.add_argument("--slug", required=True)
    init.add_argument("--question", required=True)
    init.add_argument("--root", type=Path, default=Path("docs/design-research"))
    check = commands.add_parser("validate", help="Check a completed evidence.json (structure, not scientific truth)")
    check.add_argument("path", type=Path)
    check.add_argument("--check-artifacts", action="store_true",
                       help="Also verify workspace-relative artifact existence and hashes")
    check.add_argument("--artifacts-root", type=Path,
                       help="Artifact workspace for an archived ledger (default: ledger parent)")
    commands.add_parser("providers", help="Show capabilities; does not contact services")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            path = create_run(args.root, args.slug, args.question, HERE.parent / "templates")
            emit({"created": str(path), "note": "Fill the templates and evidence ledger. The initial skeleton intentionally fails validation."})
            return 0
        if args.command == "validate":
            if args.path.stat().st_size > 5_000_000:
                raise ResearchError("Evidence JSON exceeds 5 MB.")
            data = json.loads(args.path.read_text("utf-8"))
            if args.check_artifacts:
                from evidence import verify_artifacts
                result = verify_artifacts(data, args.artifacts_root or (args.path.parent.parent if args.path.parent.name == ".internal" else args.path.parent))
            else:
                result = validate_dossier(data)
            emit(result)
            return 0 if result["valid"] else 1
        if args.command == "providers":
            emit({"providers": BASES, "operations": ["search", "lookup", "links (Semantic Scholar)"],
                  "retrieval": "metadata/abstracts and links only; use available browser/PDF tools to read full text",
                  "no_required_mcp": True, "registration": "No MCP is registered by this package.",
                  "optional_keys": ["SEMANTIC_SCHOLAR_API_KEY", "CROSSREF_MAILTO"],
                  "limits": "1-50 items/page/provider, at most one page per call; no automatic recursive expansion"})
            return 0
        if args.command == "search":
            clean_query(args.query)
            if args.year_from and args.year_to and args.year_from > args.year_to:
                raise ResearchError("year-from must not exceed year-to.")
        client = Client(args.cache_dir, offline=args.offline, allow_network=args.allow_network,
                        ttl=args.cache_ttl, timeout=args.timeout)
        results = []
        providers = list(BASES) if args.command == "search" and args.provider == "all" else [getattr(args, "provider", "semantic-scholar")]
        for provider in providers:
            try:
                if args.command == "search":
                    result = search(client, provider, args.query, args.limit, args.offset, args.year_from, args.year_to)
                elif args.command == "lookup":
                    result = lookup(client, provider, args.id)
                else:
                    result = links(client, args.id, args.direction, args.limit, args.offset)
                results.append(result)
            except ResearchError as exc:
                results.append({"provider": provider, "status": "error", "error": str(exc), "papers": []})
        failed = any(r["status"] == "error" for r in results)
        papers = mark_families([paper for r in results for paper in r.pop("papers")])
        emit({"schema_version": 1, "operation": args.command, "requested_at": utcnow(),
              "query_or_id": getattr(args, "query", getattr(args, "id", None)),
              "providers": results, "papers": papers, "result_count": len(papers), "has_failures": failed,
              "warning": "Search hits and citation counts do not establish effectiveness, peer review, independent replication, or absence of retraction."})
        return 2 if failed else 0
    except (ResearchError, OSError, ValueError) as exc:
        # No HTTP response body, credentials, environment dump, or traceback is printed.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if sys.version_info < (3, 10):
        print("Python 3.10+ required", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(main())
