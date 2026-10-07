#!/usr/bin/env python3
"""Explicit, reviewed memory sharing through private GitHub repositories and PRs."""

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlencode

import workgraph_tools as wg


SLUG = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


def basic_memory_config():
    if os.environ.get("BASIC_MEMORY_CONFIG_DIR"):
        return Path(os.environ["BASIC_MEMORY_CONFIG_DIR"]) / "config.json"
    if os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]) / "basic-memory/config.json"
    return Path.home() / ".basic-memory/config.json"


def read_object(path):
    value = wg.strict_json(wg.read_text(path)) if path.exists() else {}
    if not isinstance(value, dict):
        raise wg.Invalid("Expected a configuration object")
    return value


def slug(value):
    if not isinstance(value, str) or not SLUG.fullmatch(value):
        raise wg.Invalid("Profile/source ID must use 1-64 lowercase letters, digits, _ or -")
    return value


def command(args, cwd=None):
    # Do not let a caller's GIT_DIR/index/worktree or injected -c environment
    # redirect operations into their active code checkout. Keep credential config.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_TERMINAL_PROMPT="0", GH_PROMPT_DISABLED="1")
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=120,
                                env=environment)
    except FileNotFoundError:
        raise wg.Invalid(f"Required command unavailable: {args[0]}") from None
    except subprocess.TimeoutExpired:
        raise wg.Invalid("Command timed out; inspect remote state with status before retrying") from None
    if result.returncode:
        # External stderr can contain credentials, private paths or raw note text.
        raise wg.Invalid(f"{args[0]} failed (exit {result.returncode}); check authentication, permissions or conflicts")
    return result.stdout.strip()


class GitHub:
    def __init__(self, repo, writable=False):
        if not isinstance(repo, str) or not REPO.fullmatch(repo) or any(p.startswith(".") for p in repo.split("/")):
            raise wg.Invalid("Use a GitHub.com OWNER/REPO identifier")
        command(["gh", "auth", "status", "--hostname", "github.com"])
        data = wg.strict_json(command(["gh", "api", "--hostname", "github.com", f"repos/{repo}"]))
        canonical = data.get("full_name")
        if not isinstance(canonical, str) or canonical.lower() != repo.lower():
            raise wg.Invalid("Repository identity changed; confirm the sharing destination")
        if data.get("private") is not True:
            raise wg.Invalid("Memory sharing requires a private repository")
        if writable and data.get("permissions", {}).get("push") is not True:
            raise wg.Invalid("Repository write permission is required for publishing")
        self.repo = canonical
        self.base = data.get("default_branch")
        self.remote = f"https://github.com/{canonical}.git"

    def git(self, *args, cwd=None):
        return command(["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
                        "-c", "commit.gpgsign=false", "-c", "protocol.file.allow=never",
                        "-c", "user.name=Workgraph sharing", "-c", "user.email=workgraph@users.noreply.github.com", *args], cwd)

    def clone(self, path):
        self.git("clone", "--quiet", "--no-checkout", "--", self.remote, str(path))
        # A remote .gitattributes must not select locally configured smudge/LFS
        # processes. The local info file takes precedence over repository attributes.
        wg.atomic_file(path / ".git/info/attributes", "* -filter -text -ident -eol\n", replace=True)

    def prs(self, branch):
        values = []
        for page in range(1, 11):
            query = urlencode({"state": "all", "head": self.repo.split("/")[0] + ":" + branch,
                               "per_page": 100, "page": page, "sort": "created", "direction": "desc"})
            batch = self.api(f"repos/{self.repo}/pulls?{query}")
            if not isinstance(batch, list):
                raise wg.Invalid("Invalid PR listing")
            for p in batch:
                if p["head"]["repo"]["full_name"].lower() != self.repo.lower() or p["head"]["ref"] != branch:
                    raise wg.Invalid("Sharing PR belongs to another repository or branch")
                values.append({"number": p["number"], "url": p["html_url"],
                    "state": "MERGED" if p["merged_at"] else p["state"].upper(), "mergedAt": p["merged_at"],
                    "baseRefName": p["base"]["ref"], "headRefName": p["head"]["ref"], "head_sha": p["head"]["sha"],
                    "title": p["title"], "body": p.get("body") or ""})
            if len(batch) < 100:
                break
        else:
            raise wg.Invalid("PR history is incomplete; resolve the sharing branch history")
        opened = [p for p in values if p["state"] == "OPEN"]
        if len(opened) > 1:
            raise wg.Invalid("Multiple sharing PRs found; resolve them before publishing")
        return values, opened[0] if opened else None

    def api(self, endpoint, method="GET", payload=None):
        args = ["gh", "api", "--hostname", "github.com", "--method", method,
                "--header", "Accept: application/vnd.github+json", endpoint]
        if payload is not None:
            args.extend(["--input", str(payload)])
        return wg.strict_json(command(args))


def files(root):
    result = {}
    if not root.exists():
        return result
    wg.no_symlink(root)
    if not root.is_dir():
        raise wg.Invalid("Bundle must be a directory")
    for path in root.rglob("*"):
        wg.no_symlink(path)
        if path.is_file():
            result[path.relative_to(root).as_posix()] = wg.read_text(path)
        elif not path.is_dir():
            raise wg.Invalid("Nonregular bundle resource")
    return result


def validate_bundle(bundle, output):
    # Reuse the existing checksum, screening, schema and path validation unchanged.
    if wg.strict_json(wg.read_text(bundle / "manifest.json")).get("scope") != "team":
        raise wg.Invalid("GitHub sharing requires a team-scoped bundle")
    return wg.import_share(argparse.Namespace(memory_dir=output, bundle=bundle, dry_run=False))


def profile_conflicts(profiles, name, profile):
    for other_name, other in profiles.items():
        if other_name == name:
            continue
        if profile["role"] == "receive" and other["memory_dir"] == profile["memory_dir"]:
            raise wg.Invalid("Receiving requires a separate directory for each source")
        if (profile["role"] == other["role"] == "publish" and other["repo"].lower() == profile["repo"].lower()
                and other["source_id"] == profile["source_id"]):
            raise wg.Invalid("Source ID already belongs to another publishing profile")


class Sharing:
    def __init__(self, codex_dir, registry=None):
        self.home = wg.no_symlink(codex_dir) / "basic-memory-workgraph"
        self.config_path = self.home / "github-sharing.json"
        self.registry = registry or basic_memory_config()

    def config(self):
        wg.no_symlink(self.config_path)
        data = read_object(self.config_path) if self.config_path.exists() else {"version": 1, "profiles": {}}
        if data.get("version") != 1 or not isinstance(data.get("profiles"), dict):
            raise wg.Invalid("Unsupported GitHub sharing configuration")
        return data

    def profile(self, name):
        profiles = self.config()["profiles"]
        if name is None:
            if len(profiles) != 1:
                raise wg.Invalid("Specify --profile; first-time use requires setup")
            name = next(iter(profiles))
        slug(name)
        if name not in profiles:
            raise wg.Invalid("Sharing profile not configured")
        profile = profiles[name]
        slug(profile["source_id"])
        if profile["role"] not in ("publish", "receive") or profile.get("scope") != "team":
            raise wg.Invalid("Invalid sharing profile")
        if not isinstance(profile["include_cases"], bool):
            raise wg.Invalid("Invalid Case sharing setting")
        if not Path(profile["memory_dir"]).is_absolute():
            raise wg.Invalid("Memory path must be absolute")
        root = wg.no_symlink(Path(profile["memory_dir"])).resolve()
        if root == self.home or self.home.is_relative_to(root) or root.is_relative_to(self.home):
            raise wg.Invalid("Memory must be outside Workgraph configuration")
        return name, profile, root

    @contextmanager
    def lock(self, name):
        directory = wg.no_symlink(self.home / "github-state")
        directory.mkdir(parents=True, exist_ok=True)
        path = wg.no_symlink(directory / (slug(name) + ".lock"))
        with path.open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise wg.Invalid("Another sharing operation is running") from None
            yield

    def setup(self, args):
        name, source = slug(args.profile), slug(args.source_id)
        data = self.config()
        hub = GitHub(args.repo, writable=args.role == "publish")
        base = args.base or hub.base
        if not base or base.startswith("-"):
            raise wg.Invalid("A valid base branch is required")
        hub.git("check-ref-format", "--branch", base)
        if not hub.git("ls-remote", "--heads", hub.remote, "refs/heads/" + base):
            raise wg.Invalid("Base branch is missing; initialize the private repository with a README first")
        registry = read_object(wg.no_symlink(self.registry)).get("projects", {})
        project = args.project
        if args.role == "publish":
            if project is None:
                project = read_object(self.home.parent / "basic-memory.json").get("basicMemory", {}).get("primaryProject")
            entry = registry.get(project)
            registered = entry if isinstance(entry, str) else entry.get("path") if isinstance(entry, dict) and entry.get("mode", "local") == "local" else None
            if not registered:
                raise wg.Invalid("Publishing requires a registered local Basic Memory project")
            if not Path(registered).is_absolute():
                raise wg.Invalid("Registered memory path must be absolute")
            root = wg.no_symlink(Path(registered)).resolve()
            if args.memory_dir is not None and wg.no_symlink(args.memory_dir) != root:
                raise wg.Invalid("Memory directory does not match the registered project")
            if not root.is_dir():
                raise wg.Invalid("Memory directory does not exist")
        else:
            project = project or "shared-" + source
            if args.memory_dir is None:
                raise wg.Invalid("Receiving setup requires --memory-dir for a dedicated project")
            root = wg.no_symlink(args.memory_dir).resolve()
            entry = registry.get(project)
            registered = entry if isinstance(entry, str) else entry.get("path") if isinstance(entry, dict) and entry.get("mode", "local") == "local" else None
            if entry is not None and (not registered or wg.no_symlink(Path(registered)) != root):
                raise wg.Invalid("Receiving project name is already used by a different project")
            existing = data["profiles"].get(name)
            managed = existing and existing.get("role") == "receive" and existing.get("memory_dir") == str(root)
            if root.exists() and any(root.iterdir()) and not managed:
                raise wg.Invalid("Receiving requires an empty dedicated memory directory")
            for other_name, other in data["profiles"].items():
                if other_name != name and wg.no_symlink(Path(other["memory_dir"])).resolve() == root:
                    raise wg.Invalid("Receiving requires a separate directory for each source")
        if not isinstance(project, str) or not project.strip() or project.startswith("-"):
            raise wg.Invalid("A valid Basic Memory project name is required")
        if root == self.home or root.is_relative_to(self.home) or self.home.is_relative_to(root):
            raise wg.Invalid("Memory must be outside Workgraph configuration")
        profile = {"repo": hub.repo, "source_id": source, "base": base, "project": project,
                   "memory_dir": str(root), "role": args.role, "scope": "team", "include_cases": args.include_cases}
        profile_conflicts(data["profiles"], name, profile)
        # Profile identities are immutable: changing them could overwrite another source.
        if name in data["profiles"] and data["profiles"][name] != profile:
            raise wg.Invalid("Profile already exists with different settings; use a new profile name")
        if not args.dry_run:
            with self.lock("configuration"):
                data = self.config()
                if name in data["profiles"] and data["profiles"][name] != profile:
                    raise wg.Invalid("Profile changed during setup")
                profile_conflicts(data["profiles"], name, profile)
                if args.role == "receive" and entry is None:
                    command(["bm", "project", "add", project, str(root), "--local"])
                data["profiles"][name] = profile
                if not self.config_path.exists() or self.config() != data:
                    wg.atomic_file(self.config_path, wg.json_text(data), replace=True)
        return {"profile": name, "configured": not args.dry_run, "dry_run": args.dry_run, "repo": hub.repo}

    def context(self, name, role=None):
        name, profile, root = self.profile(name)
        if role and profile["role"] != role:
            raise wg.Invalid(f"This operation requires a {role} profile")
        entry = read_object(wg.no_symlink(self.registry)).get("projects", {}).get(profile["project"])
        registered = entry if isinstance(entry, str) else entry.get("path") if isinstance(entry, dict) and entry.get("mode", "local") == "local" else None
        if not registered or wg.no_symlink(Path(registered)).resolve() != root:
            raise wg.Invalid("Registered project changed; confirm the sharing profile")
        hub = GitHub(profile["repo"], writable=role == "publish")
        hub.git("check-ref-format", "--branch", profile["base"])
        return name, profile, root, hub

    def publish(self, name, dry_run=False):
        name, profile, root, hub = self.context(name, "publish")
        if dry_run:
            return self._publish(profile, root, hub, True)
        with self.lock(name):
            return self._publish(profile, root, hub, False)

    def _publish(self, profile, root, hub, dry_run):
        branch = "workgraph-share/" + profile["source_id"]
        relative = "bundles/" + profile["source_id"]
        history, opened = hub.prs(branch)
        if opened and opened["baseRefName"] != profile["base"]:
            raise wg.Invalid("Existing sharing PR has a different base branch")
        if not opened and history and history[0]["state"] == "CLOSED" and not history[0]["mergedAt"]:
            raise wg.Invalid("Previous sharing PR was closed without merging; resolve it before retrying")
        with tempfile.TemporaryDirectory(prefix="workgraph-github-") as temp:
            temp = Path(temp)
            bundle = temp / "bundle"
            exported = wg.export_share(argparse.Namespace(memory_dir=root, output=bundle, scope="team",
                                                          include_cases=profile["include_cases"], dry_run=False))
            if exported["skipped"]:
                return {"status": "blocked", "skipped": exported["skipped"], "dry_run": dry_run}
            validate_bundle(bundle, temp / "validate-export")
            repo = temp / "repo"
            hub.clone(repo)
            base = "refs/remotes/origin/" + profile["base"]
            base_sha = hub.git("rev-parse", "--verify", base, cwd=repo)
            remote_branch = "refs/remotes/origin/" + branch
            refs = hub.git("for-each-ref", "--format=%(refname)", remote_branch, cwd=repo).splitlines()
            start = remote_branch if refs else base
            if opened and not refs:
                raise wg.Invalid("Sharing PR branch is missing")
            hub.git("checkout", "--quiet", "-b", branch, start, cwd=repo)
            # Only our managed directory may differ from the current base.
            changed = hub.git("diff", "--name-only", base + "...HEAD", cwd=repo).splitlines()
            if any(not path.startswith(relative + "/") for path in changed):
                raise wg.Invalid("Sharing branch contains unrelated changes")
            hub.git("merge", "--quiet", "--no-edit", base, cwd=repo)
            target = wg.no_symlink(repo / relative)
            previous, desired = files(target), files(bundle)
            if previous:
                validate_bundle(target, temp / "validate-existing")
            added = sorted(desired.keys() - previous.keys() - {"manifest.json"})
            removed = sorted(previous.keys() - desired.keys() - {"manifest.json"})
            updated = sorted(p for p in desired.keys() & previous.keys() if p != "manifest.json" and desired[p] != previous[p])
            result = {"status": "unchanged", "added": len(added), "updated": len(updated), "removed": len(removed),
                      "exported": exported["exported"], "dry_run": dry_run, "pr_url": opened["url"] if opened else None}
            if not previous and not exported["exported"]:
                return result
            if previous != desired:
                result["status"] = "planned" if dry_run else "published"
                if not dry_run:
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.copytree(bundle, target)
                    hub.git("add", "--", relative, cwd=repo)
                    hub.git("-c", "user.name=Workgraph sharing", "-c", "user.email=workgraph@users.noreply.github.com",
                            "commit", "--quiet", "-m", "Update reviewed shared memory: " + profile["source_id"], cwd=repo)
            differs_base = bool(hub.git("diff", "--name-only", base, "HEAD", "--", relative, cwd=repo))
            if dry_run:
                return result
            if not differs_base and not opened:
                result["status"] = "unchanged"
                return result
            cumulative = hub.git("diff", "--name-status", base_sha, "HEAD", "--", relative, cwd=repo)
            counts = {key: sum(line.startswith(key + "\t") for line in cumulative.splitlines()) for key in ("A", "M", "D")}
            body = ("共有を許可し、内容を確認したメモリを更新します。\n\n"
                f"追加 {counts['A']}、変更 {counts['M']}、削除 {counts['D']} ファイル（manifestを含む）。\n\n"
                "共有範囲・レビュー指紋・秘密情報・リンク・bundleの整合性を検査しました。"
                "内容をレビューし、問題がなければマージしてください。受け取り側はマージ後に取り込みます。\n")
            title = "共有メモリを更新: " + profile["source_id"]
            if previous == desired and opened and opened["title"] == title and opened["body"] == body:
                return result
            pushed = opened["head_sha"] if opened else None
            if previous != desired or not opened:
                # A non-force push rejects concurrent writers; a retry re-reads remote state.
                hub.git("push", "--quiet", "origin", "HEAD:refs/heads/" + branch, cwd=repo)
                pushed = hub.git("rev-parse", "HEAD", cwd=repo)
                observed = hub.git("ls-remote", "origin", "refs/heads/" + branch, cwd=repo).split()
                if not observed or observed[0] != pushed:
                    raise wg.Invalid("Remote branch changed after push; inspect status before retrying")
            # Re-read: an earlier timed-out create may already have succeeded.
            _, current = hub.prs(branch)
            payload = {"title": title, "body": body}
            request = temp / "pr-request.json"
            if current:
                if current["title"] != title or current["body"] != body:
                    request.write_text(wg.json_text(payload), encoding="utf-8")
                    hub.api(f"repos/{hub.repo}/pulls/{current['number']}", "PATCH", request)
            else:
                payload.update(base=profile["base"], head=branch, maintainer_can_modify=False)
                request.write_text(wg.json_text(payload), encoding="utf-8")
                hub.api(f"repos/{hub.repo}/pulls", "POST", request)
            _, verified = hub.prs(branch)
            if (not verified or verified["baseRefName"] != profile["base"] or verified["head_sha"] != pushed
                    or verified["title"] != title or verified["body"] != body):
                raise wg.Invalid("PR read-back failed; inspect status before retrying")
            result.update(status="published", pr_url=verified["url"], commit=pushed)
            return result

    def pull(self, name, dry_run=False):
        name, profile, root, hub = self.context(name, "receive")
        if dry_run:
            return self._pull(name, profile, root, hub, True)
        with self.lock(name):
            return self._pull(name, profile, root, hub, False)

    def _pull(self, name, profile, root, hub, dry_run):
        state_path = wg.no_symlink(self.home / "github-state" / (name + ".json"))
        old_state = wg.strict_json(wg.read_text(state_path)) if state_path.exists() else None
        identity = {key: profile[key] for key in ("repo", "source_id", "memory_dir", "base")}
        if old_state and (old_state.get("version") != 1 or old_state.get("identity") != identity):
            raise wg.Invalid("Import state belongs to a different source")
        baseline = old_state["files"] if old_state else {}
        if not isinstance(baseline, dict) or any(not re.fullmatch(r"[a-f0-9]{64}", h) for h in baseline.values()):
            raise wg.Invalid("Invalid import baseline")
        for rel in baseline:
            wg.relative_path(rel)
        with tempfile.TemporaryDirectory(prefix="workgraph-receive-") as temp:
            temp = Path(temp)
            repo = temp / "repo"
            hub.clone(repo)
            ref = "refs/remotes/origin/" + profile["base"]
            commit = hub.git("rev-parse", "--verify", ref, cwd=repo)
            hub.git("checkout", "--quiet", "--detach", ref, cwd=repo)
            staged = temp / "imported"
            bundle = wg.no_symlink(repo / "bundles" / profile["source_id"])
            validate_bundle(bundle, staged)
            desired = files(staged)
            pending, conflicts, unchanged = [], [], 0
            # Keep removed files in the baseline so later reappearance still detects local edits.
            next_files = dict(baseline)
            for rel, text in desired.items():
                note = wg.parse_note(text, rel)
                # Stable provenance avoids rewriting every note on unrelated repo commits.
                note.metadata["import_source"] = {"repo": hub.repo, "source_id": profile["source_id"], "path": rel}
                text = note.render()
                target = wg.no_symlink(root / wg.relative_path(rel))
                original = wg.read_text(target) if target.exists() else None
                digest = wg.sha(text.encode())
                if original == text:
                    unchanged += 1
                elif rel in baseline and (original is None or wg.sha(original.encode()) != baseline[rel]):
                    conflicts.append(rel)
                elif original is not None and rel not in baseline:
                    conflicts.append(rel)
                else:
                    pending.append((target, text, original))
                next_files[rel] = digest
            removed = sorted(baseline.keys() - desired.keys())
            result = {"status": "blocked" if conflicts else "planned" if dry_run else "imported" if pending else "unchanged",
                      "imported": 0 if conflicts else len(pending), "unchanged": unchanged,
                      "conflicts": conflicts, "removed": removed, "commit": commit, "dry_run": dry_run}
            if conflicts or dry_run:
                return result
            state = {"version": 1, "identity": identity, "commit": commit, "files": next_files}
            state_text = wg.json_text(state)
            original_state = wg.read_text(state_path) if state_path.exists() else None
            touched = []
            try:
                for path, text, original in pending:
                    if (wg.read_text(path) if path.exists() else None) != original:
                        raise wg.Invalid("Local memory changed during import")
                    touched.append((path, original, text))
                    wg.atomic_file(path, text, replace=original is not None)
                if not state_path.exists() or wg.read_text(state_path) != state_text:
                    touched.append((state_path, original_state, state_text))
                    wg.atomic_file(state_path, state_text, replace=True)
            except (OSError, ValueError):
                for path, original, written in reversed(touched):
                    current = wg.read_text(path) if path.exists() else None
                    if current == original:
                        continue
                    if current != written:
                        # Preserve a concurrent external edit rather than undoing it.
                        continue
                    if original is None:
                        path.unlink(missing_ok=True)
                    else:
                        wg.atomic_file(path, original, replace=True)
                raise
            return result

    def status(self, name):
        name, profile, _, hub = self.context(name)
        _, opened = hub.prs("workgraph-share/" + profile["source_id"])
        path = wg.no_symlink(self.home / "github-state" / (name + ".json"))
        state = wg.strict_json(wg.read_text(path)) if path.exists() else {}
        return {"profile": name, "repo": hub.repo, "role": profile["role"],
                "pr_url": opened["url"] if opened else None, "last_import_commit": state.get("commit")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-dir", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    parser.add_argument("--basic-memory-config", type=Path, default=basic_memory_config())
    commands = parser.add_subparsers(dest="action", required=True)
    setup = commands.add_parser("setup", help="Configure an existing private sharing repository")
    setup.add_argument("--profile", required=True)
    setup.add_argument("--repo", required=True)
    setup.add_argument("--source-id", required=True)
    setup.add_argument("--role", choices=("publish", "receive"), default="publish")
    setup.add_argument("--project")
    setup.add_argument("--memory-dir", type=Path)
    setup.add_argument("--base")
    setup.add_argument("--include-cases", action="store_true")
    setup.add_argument("--dry-run", action="store_true")
    for action in ("publish", "pull", "status"):
        item = commands.add_parser(action)
        item.add_argument("--profile")
        if action != "status":
            item.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        sharing = Sharing(args.codex_dir, args.basic_memory_config)
        if args.action == "setup":
            result = sharing.setup(args)
        elif args.action == "status":
            result = sharing.status(args.profile)
        else:
            result = getattr(sharing, args.action)(args.profile, args.dry_run)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        parser.exit(1, f"Sharing failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") == "blocked":
        parser.exit(2)


if __name__ == "__main__":
    main()
