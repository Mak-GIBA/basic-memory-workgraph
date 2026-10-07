"""Real Git round trips with fictional notes and an in-process GitHub CLI server."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

SOURCE = Path(__file__).resolve().parent.parent / "tools/basic-memory-workgraph"
sys.path.insert(0, str(SOURCE))
import workgraph_github as github
import workgraph_tools as wg
import configure_workgraph as configure


class FakeCLI:
    def __init__(self, base):
        self.base = base
        self.remote = base / "remote.git"
        self.registry = base / "registry.json"
        self.registry.write_text('{"projects": {}}')
        self.private, self.push, self.auth = True, True, True
        self.prs, self.calls = [], []
        self.fail_create_after = False
        self.fail_push_after = False
        self.before_push = None
        self.real = github.command
        self.git("init", "--bare", "--initial-branch=main", str(self.remote))
        self.seed = base / "seed"
        self.git("clone", str(self.remote), str(self.seed))
        (self.seed / "README.md").write_text("Fictional memory repository\n")
        self.git("add", ".", cwd=self.seed)
        self.git("commit", "-m", "Initialize", cwd=self.seed)
        self.git("push", "origin", "main", cwd=self.seed)

    def git(self, *args, cwd=None):
        result = subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *args],
                                cwd=cwd, capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout.strip()

    def __call__(self, args, cwd=None):
        self.calls.append(list(args))
        if args[0] == "git":
            # Production forbids file transports; this test permits its isolated bare repository.
            args = [str(self.remote) if a == "https://github.com/example/memories.git" else
                    "protocol.file.allow=always" if a == "protocol.file.allow=never" else a for a in args]
            if "push" in args and self.before_push:
                callback, self.before_push = self.before_push, None
                callback()
            result = self.real(args, cwd)
            if "push" in args and self.fail_push_after:
                self.fail_push_after = False
                raise wg.Invalid("Simulated response loss after push")
            return result
        if args[:3] == ["gh", "auth", "status"]:
            if not self.auth:
                raise wg.Invalid("Not authenticated")
            return ""
        if args[:2] == ["gh", "api"]:
            endpoint = next(a for a in args if a.startswith("repos/"))
            method = args[args.index("--method") + 1] if "--method" in args else "GET"
            if "/pulls" not in endpoint:
                return json.dumps({"full_name": "example/memories", "private": self.private,
                                   "permissions": {"push": self.push}, "default_branch": "main"})
            def rest(p):
                return {"number": p["number"], "html_url": p["url"], "merged_at": p["mergedAt"],
                        "state": "open" if p["state"] == "OPEN" else "closed", "title": p["title"], "body": p["body"],
                        "base": {"ref": p["baseRefName"]}, "head": {"ref": p["headRefName"],
                        "sha": self.git("rev-parse", p["headRefName"], cwd=self.remote),
                        "repo": {"full_name": "example/memories"}}}
            if method == "GET":
                query = parse_qs(urlparse(endpoint).query)
                branch = query["head"][0].split(":", 1)[1]
                matches = [rest(p) for p in reversed(self.prs) if p["headRefName"] == branch]
                page = int(query["page"][0])
                return json.dumps(matches[(page - 1) * 100:page * 100])
            payload = json.loads(Path(args[args.index("--input") + 1]).read_text())
            if method == "POST":
                p = {"number": len(self.prs) + 1, "url": "https://github.com/example/memories/pull/" + str(len(self.prs) + 1),
                     "state": "OPEN", "mergedAt": None, "baseRefName": payload["base"],
                     "headRefName": payload["head"], "title": payload["title"], "body": payload["body"]}
                self.prs.append(p)
                if self.fail_create_after:
                    self.fail_create_after = False
                    raise wg.Invalid("Simulated response loss after PR creation")
                return json.dumps(rest(p))
            p = next(p for p in self.prs if p["number"] == int(endpoint.rsplit("/", 1)[1]))
            p.update(title=payload["title"], body=payload["body"])
            return json.dumps(rest(p))
        if args[:3] == ["bm", "project", "add"]:
            data = json.loads(self.registry.read_text())
            data["projects"][args[3]] = {"path": args[4], "mode": "local"}
            Path(args[4]).mkdir(parents=True, exist_ok=True)
            self.registry.write_text(json.dumps(data))
            return ""
        raise AssertionError(args)

    def merge(self):
        p = next(p for p in self.prs if p["state"] == "OPEN")
        self.git("fetch", "origin", cwd=self.seed)
        self.git("merge", "--no-edit", "origin/" + p["headRefName"], cwd=self.seed)
        self.git("push", "origin", "main", cwd=self.seed)
        p.update(state="MERGED", mergedAt="2026-01-01T00:00:00Z")


class GitHubSharingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.server = FakeCLI(self.root)
        self.patcher = patch.object(github, "command", self.server)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.memory = self.root / "source memory"
        self.memory.mkdir()
        self.receiver = self.root / "received"
        self.codex = self.root / "codex"
        self.codex.mkdir()
        (self.codex / "basic-memory.json").write_text('{"basicMemory":{"primaryProject":"source"}}')
        self.server.registry.write_text(json.dumps({"projects": {"source": {"path": str(self.memory), "mode": "local"}}}))
        self.sharing = github.Sharing(self.codex, self.server.registry)

    def setup(self, role="publish", **overrides):
        args = argparse.Namespace(profile=role, source_id="source", repo="example/memories", role=role,
            base=None, project=None, memory_dir=self.receiver if role == "receive" else None,
            include_cases=False, dry_run=False)
        for key, value in overrides.items():
            setattr(args, key, value)
        return self.sharing.setup(args)

    def note(self, rel="rules/units.md", body="Preserve denominator definitions.", review=True, **metadata):
        note = wg.Note(rel, {"title": "Units", "type": "rule", **metadata}, "\n" + body + "\n")
        path = self.memory / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(note.render())
        if review:
            wg.review(argparse.Namespace(memory_dir=self.memory, note=rel, sharing="team", training="excluded", dry_run=False))
        return path

    def snapshot(self):
        return {str(p.relative_to(self.codex)): p.read_bytes() for p in self.codex.rglob("*") if p.is_file()}

    def test_publish_update_no_change_merge_and_next_pr(self):
        self.note()
        self.note("rules/private.md", review=False)
        self.setup()
        result = self.sharing.publish(None)
        self.assertEqual(result["status"], "published")
        self.assertEqual(len(self.server.prs), 1)
        calls = len(self.server.calls)
        again = self.sharing.publish(None)
        self.assertEqual(again["status"], "unchanged")
        self.assertFalse(any("PATCH" in c for c in self.server.calls[calls:]))
        self.note(body="Align denominators before comparing values.")
        self.assertEqual(self.sharing.publish(None)["updated"], 1)
        self.assertEqual(len(self.server.prs), 1)
        self.server.merge()
        self.note(body="Include units with aligned denominators.")
        self.sharing.publish(None)
        self.assertEqual(len(self.server.prs), 2)
        tree = self.server.git("ls-tree", "-r", "--name-only", "workgraph-share/source", cwd=self.server.remote)
        self.assertNotIn("private.md", tree)
        self.assertFalse(any("--force" in c for c in self.server.calls))

    def test_pull_waits_for_merge_and_updates_preserve_provenance(self):
        self.note()
        self.setup()
        self.setup("receive")
        self.sharing.publish("publish")
        with self.assertRaises(wg.Invalid):
            self.sharing.pull("receive")
        self.assertFalse((self.receiver / "rules/units.md").exists())
        self.server.merge()
        result = self.sharing.pull("receive")
        self.assertEqual(result["imported"], 1)
        note = wg.load_note(self.receiver, "rules/units.md")
        self.assertEqual(note.metadata["sharing_scope"], "private")
        self.assertEqual(note.metadata["training_use"], "excluded")
        self.assertEqual(note.metadata["privacy_review"], "pending")
        self.assertEqual(note.metadata["import_source"]["repo"], "example/memories")
        before = (self.receiver / "rules/units.md").read_bytes()
        self.assertEqual(self.sharing.pull("receive")["unchanged"], 1)
        self.assertEqual((self.receiver / "rules/units.md").read_bytes(), before)
        self.note(body="New verified reference data.")
        self.sharing.publish("publish")
        self.server.merge()
        self.assertEqual(self.sharing.pull("receive")["imported"], 1)
        self.assertIn("New verified", (self.receiver / "rules/units.md").read_text())

    def test_conflicts_stop_entire_batch_and_local_deletion_is_protected(self):
        self.note()
        self.setup()
        self.setup("receive")
        self.sharing.publish("publish")
        self.server.merge()
        self.sharing.pull("receive")
        target = self.receiver / "rules/units.md"
        for original in ("Local edit\n", None):
            if original is None:
                target.unlink()
            else:
                target.write_text(original)
            self.note("rules/new.md")
            self.note(body="Upstream change: " + ("edited" if original else "deleted") + ".")
            self.sharing.publish("publish")
            self.server.merge()
            result = self.sharing.pull("receive")
            self.assertEqual(result["conflicts"], ["rules/units.md"])
            self.assertFalse((self.receiver / "rules/new.md").exists())
            self.assertEqual(target.read_text() if target.exists() else None, original)

    def test_removed_notes_are_reported_without_deletion(self):
        source = self.note()
        self.setup()
        self.setup("receive")
        self.sharing.publish("publish")
        self.server.merge()
        self.sharing.pull("receive")
        original = (self.receiver / "rules/units.md").read_bytes()
        source.unlink()
        self.assertEqual(self.sharing.publish("publish")["removed"], 1)
        self.server.merge()
        self.assertEqual(self.sharing.pull("receive")["removed"], ["rules/units.md"])
        self.assertEqual((self.receiver / "rules/units.md").read_bytes(), original)

    def test_setup_publish_and_pull_dry_run_do_not_mutate(self):
        self.note()
        before = self.snapshot()
        registry = self.server.registry.read_bytes()
        self.setup(dry_run=True)
        self.setup("receive", dry_run=True)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.server.registry.read_bytes(), registry)
        self.assertFalse(self.receiver.exists())
        self.setup()
        before = self.snapshot()
        remote = self.server.git("show-ref", cwd=self.server.remote)
        self.assertEqual(self.sharing.publish(None, True)["status"], "planned")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.server.git("show-ref", cwd=self.server.remote), remote)
        self.assertEqual(self.server.prs, [])
        self.sharing.publish(None)
        self.server.merge()
        self.setup("receive")
        before = self.snapshot()
        self.sharing.pull("receive", True)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.receiver / "rules/units.md").exists())

    def test_failed_checks_do_not_push_or_silently_export_subset(self):
        path = self.note()
        self.setup()
        path.write_text(path.read_text() + "Changed without review\n")
        self.note("rules/second.md")
        result = self.sharing.publish(None)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(self.server.prs, [])
        self.assertFalse(any(c[0] == "git" and "push" in c for c in self.server.calls))

    def test_empty_share_does_not_create_pr(self):
        self.note(review=False)
        self.setup()
        self.assertEqual(self.sharing.publish(None)["status"], "unchanged")
        self.assertEqual(self.server.prs, [])

    def test_public_repo_permission_and_auth_fail_closed(self):
        self.note()
        self.setup()
        for field in ("private", "push", "auth"):
            with self.subTest(field=field):
                setattr(self.server, field, False)
                with self.assertRaises(wg.Invalid):
                    self.sharing.publish(None)
                setattr(self.server, field, True)
        self.assertEqual(self.server.prs, [])

    def test_lost_create_response_retry_does_not_duplicate_pr(self):
        self.note()
        self.setup()
        self.server.fail_create_after = True
        with self.assertRaises(wg.Invalid):
            self.sharing.publish(None)
        self.assertIsNotNone(self.sharing.status(None)["pr_url"])
        self.sharing.publish(None)
        self.assertEqual(len(self.server.prs), 1)

    def test_lost_push_response_retry_creates_single_pr(self):
        self.note()
        self.setup()
        self.server.fail_push_after = True
        with self.assertRaises(wg.Invalid):
            self.sharing.publish(None)
        self.assertEqual(self.server.prs, [])
        self.sharing.publish(None)
        self.assertEqual(len(self.server.prs), 1)

    def test_existing_pr_description_is_recovered_after_failed_update(self):
        self.note()
        self.setup()
        self.sharing.publish(None)
        self.server.prs[0]["body"] = "Stale summary after a response failure"
        self.sharing.publish(None)
        self.assertNotIn("Stale summary", self.server.prs[0]["body"])
        self.assertEqual(len(self.server.prs), 1)

    def test_reverting_an_open_pr_back_to_base_is_pushed(self):
        self.note(body="Original memory.")
        self.setup()
        self.sharing.publish(None)
        self.server.merge()
        self.note(body="Intermediate revision.")
        self.sharing.publish(None)
        self.note(body="Original memory.")
        self.sharing.publish(None)
        diff = self.server.git("diff", "--name-only", "main", "workgraph-share/source", cwd=self.server.remote)
        self.assertEqual(diff, "")
        self.assertEqual(len(self.server.prs), 2)

    def test_pr_history_is_paginated_and_closed_unmerged_pr_is_not_reopened(self):
        self.note()
        self.setup()
        self.sharing.publish(None)
        original = self.server.prs[0]
        self.server.prs = [{**original, "number": i + 2, "state": "MERGED", "mergedAt": "2026-01-01"}
                           for i in range(100)] + [original]
        self.sharing.publish(None)
        pages = [c for c in self.server.calls if any("page=2" in a for a in c)]
        self.assertTrue(pages)
        original["state"] = "CLOSED"
        with self.assertRaises(wg.Invalid):
            self.sharing.publish(None)

    def test_concurrent_push_is_rejected_without_overwriting_remote(self):
        self.note()
        self.setup()
        self.sharing.publish(None)
        def advance_remote():
            self.server.git("fetch", "origin", cwd=self.server.seed)
            self.server.git("checkout", "-b", "workgraph-share/source", "origin/workgraph-share/source", cwd=self.server.seed)
            (self.server.seed / "reviewer.txt").write_text("Concurrent writer")
            self.server.git("add", ".", cwd=self.server.seed)
            self.server.git("commit", "-m", "Concurrent writer", cwd=self.server.seed)
            self.server.git("push", "origin", "workgraph-share/source", cwd=self.server.seed)
        self.note(body="A second sender revision.")
        self.server.before_push = advance_remote
        with self.assertRaises(wg.Invalid):
            self.sharing.publish(None)
        tree = self.server.git("ls-tree", "-r", "--name-only", "workgraph-share/source", cwd=self.server.remote)
        self.assertIn("reviewer.txt", tree)

    def test_base_advancing_while_pr_is_open_is_merged_without_unrelated_pr_changes(self):
        self.note()
        self.setup()
        self.sharing.publish(None)
        (self.server.seed / "README.md").write_text("Base advanced independently\n")
        self.server.git("add", ".", cwd=self.server.seed)
        self.server.git("commit", "-m", "Update repository README", cwd=self.server.seed)
        self.server.git("push", "origin", "main", cwd=self.server.seed)
        self.note(body="Second shared revision.")
        self.sharing.publish(None)
        diff = self.server.git("diff", "--name-only", "main...workgraph-share/source", cwd=self.server.remote)
        self.assertNotIn("README.md", diff)
        self.assertEqual(len(self.server.prs), 1)

    def test_untrusted_bundle_changes_fail_before_any_receiver_writes(self):
        self.note()
        self.setup()
        self.setup("receive")
        self.sharing.publish("publish")
        self.server.merge()
        bundle = self.server.seed / "bundles/source"
        with self.sharing.lock("receive"):
            pass
        pristine = {p.relative_to(bundle): p.read_bytes() for p in bundle.rglob("*") if p.is_file()}
        for kind in ("checksum", "secret", "traversal", "unlisted", "symlink", "public"):
            with self.subTest(kind=kind):
                shutil.rmtree(bundle)
                for rel, data in pristine.items():
                    path = bundle / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                note = bundle / "rules/units.md"
                manifest = json.loads((bundle / "manifest.json").read_text())
                if kind == "checksum":
                    note.write_text(note.read_text() + "Tampered text\n")
                elif kind == "secret":
                    note.write_text(note.read_text() + "Contact: fictional@example.invalid\n")
                    manifest["notes"][0]["sha256"] = wg.sha(note.read_bytes())
                elif kind == "traversal":
                    manifest["notes"][0]["path"] = "../outside.md"
                elif kind == "unlisted":
                    (bundle / "unexpected.txt").write_text("Extra file")
                elif kind == "symlink":
                    note.unlink()
                    note.symlink_to("../../README.md")
                else:
                    manifest["scope"] = "public"
                (bundle / "manifest.json").write_text(json.dumps(manifest))
                self.server.git("add", "-A", cwd=self.server.seed)
                self.server.git("commit", "-m", "Fictional malicious bundle: " + kind, cwd=self.server.seed)
                self.server.git("push", "origin", "main", cwd=self.server.seed)
                before = self.snapshot()
                with self.assertRaises(wg.Invalid):
                    self.sharing.pull("receive")
                self.assertEqual(self.snapshot(), before)
                self.assertFalse((self.receiver / "rules/units.md").exists())

    def test_pull_write_failure_rolls_back_notes_and_state(self):
        self.note()
        self.setup()
        self.setup("receive")
        self.sharing.publish("publish")
        self.server.merge()
        self.sharing.pull("receive")
        before = (self.receiver / "rules/units.md").read_bytes()
        state_before = self.snapshot()
        self.note(body="New upstream value.")
        self.note("rules/new.md")
        self.sharing.publish("publish")
        self.server.merge()
        real = wg.atomic_file
        failed = False
        def fail_once(path, content, replace=False):
            nonlocal failed
            if path.name == "receive.json" and not failed:
                failed = True
                raise OSError("Simulated disk failure")
            return real(path, content, replace)
        with patch.object(wg, "atomic_file", fail_once):
            with self.assertRaises(OSError):
                self.sharing.pull("receive")
        self.assertEqual((self.receiver / "rules/units.md").read_bytes(), before)
        self.assertFalse((self.receiver / "rules/new.md").exists())
        self.assertEqual(self.snapshot(), state_before)

    def test_profiles_are_immutable_and_receiver_requires_separate_empty_project(self):
        self.note()
        self.setup()
        before = self.snapshot()
        with self.assertRaises(wg.Invalid):
            self.setup(source_id="other")
        with self.assertRaises(wg.Invalid):
            self.setup("receive", memory_dir=self.memory)
        self.assertEqual(self.snapshot(), before)
        with self.assertRaises(wg.Invalid):
            self.setup(profile="../../unsafe")
        with self.assertRaises(wg.Invalid):
            self.setup(profile="duplicate")

    def test_unrelated_remote_branch_change_is_rejected(self):
        self.note()
        self.setup()
        self.sharing.publish(None)
        self.server.git("fetch", "origin", cwd=self.server.seed)
        self.server.git("checkout", "-b", "workgraph-share/source", "origin/workgraph-share/source", cwd=self.server.seed)
        (self.server.seed / "other.txt").write_text("Unrelated remote edit")
        self.server.git("add", ".", cwd=self.server.seed)
        self.server.git("commit", "-m", "Other change", cwd=self.server.seed)
        self.server.git("push", "origin", "workgraph-share/source", cwd=self.server.seed)
        with self.assertRaises(wg.Invalid):
            self.sharing.publish(None)

    def test_installer_preserves_other_agents_and_installed_cli_runs(self):
        original = "Existing personal instructions.\n<!-- github-project-director:begin -->\nOther block\n<!-- github-project-director:end -->\n"
        (self.codex / "AGENTS.md").write_text(original)
        configure.configure(self.codex)
        installed = self.codex / "basic-memory-workgraph/workgraph_github.py"
        result = subprocess.run([sys.executable, str(installed), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("publish", result.stdout)
        self.assertTrue((self.codex / "AGENTS.md").read_text().startswith(original))
        first = self.snapshot()
        configure.configure(self.codex)
        self.assertEqual(self.snapshot(), first)
        result = subprocess.run(["bash", str(SOURCE / "remove_workgraph_hooks.sh")],
            env={**os.environ, "CODEX_HOME": str(self.codex)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(configure.SHARING_BEGIN, (self.codex / "AGENTS.md").read_text())
        self.assertTrue((self.codex / "AGENTS.md").read_text().startswith(original))

    def test_caller_git_environment_does_not_redirect_temporary_checkout(self):
        self.note()
        self.setup()
        original = self.server.git("show-ref", cwd=self.server.remote)
        with patch.dict(os.environ, {"GIT_DIR": str(self.server.remote), "GIT_WORK_TREE": str(self.memory),
                                    "GIT_INDEX_FILE": str(self.root / "external-index")}):
            self.sharing.publish(None, True)
        self.assertEqual(self.server.git("show-ref", cwd=self.server.remote), original)
        self.assertFalse((self.root / "external-index").exists())

    def test_remote_attributes_cannot_run_a_locally_configured_filter(self):
        self.note()
        self.setup()
        self.setup("receive")
        self.sharing.publish("publish")
        self.server.merge()
        (self.server.seed / ".gitattributes").write_text("*.md filter=trap\n")
        self.server.git("add", ".gitattributes", cwd=self.server.seed)
        self.server.git("commit", "-m", "Select a local filter", cwd=self.server.seed)
        self.server.git("push", "origin", "main", cwd=self.server.seed)
        home = self.root / "isolated-home"
        home.mkdir()
        marker = self.root / "filter-executed"
        (home / ".gitconfig").write_text('[filter "trap"]\n\tsmudge = touch ' + str(marker) + '; cat\n')
        with patch.dict(os.environ, {"HOME": str(home)}):
            self.sharing.pull("receive")
        self.assertFalse(marker.exists())

    def test_malformed_agents_block_stops_configuration_before_any_changes(self):
        for text in (configure.SHARING_END + configure.SHARING_BEGIN, configure.SHARING_BEGIN,
                     configure.SHARING_BEGIN * 2 + configure.SHARING_END * 2):
            with self.subTest(text=text):
                (self.codex / "AGENTS.md").write_text(text)
                before = self.snapshot()
                with self.assertRaises(ValueError):
                    configure.configure(self.codex)
                self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
