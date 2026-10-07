"""Exercise batch dispatch in a separate checkout and HOME without downloads."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLERS = [
    ("workgraph", "install_basic_memory_workgraph.sh", []),
    ("ux-stack", "install_codex_ux_stack.sh", []),
    ("speckit", "install_speckit_upstream.sh", ["--apply"]),
    ("github-pm", "install_codex_github_pm.sh", []),
    ("design-research", "install_design_research.sh", []),
    ("ecc", "install_codex_ecc.sh", ["--apply"]),
    ("office", "install_codex_office.sh", ["--apply"]),
    ("yomiyasu", "install_codex_yomiyasu.sh", ["--apply"]),
    ("herdr", "install_herdr.sh", []),
]
HELPERS = [
    "tools/basic-memory-workgraph/configure_workgraph.py",
    "tools/basic-memory-workgraph/update_workgraph.py",
    "tools/basic-memory-workgraph/install_schemas.py",
    "tools/ecc-on-demand/install_ecc.py",
]
CHILD = r'''#!/usr/bin/env bash
"$BULK_TEST_PYTHON" - "$0" "$@" <<'PY'
import json, os, sys
from pathlib import Path
script = Path(sys.argv[1]).name
with Path(os.environ["BULK_TEST_LOG"]).open("a") as handle:
    handle.write(json.dumps({"script": script, "args": sys.argv[2:]}) + "\n")
failures = json.loads(os.environ["BULK_TEST_FAILURES"])
raise SystemExit(failures.get(script, 0))
PY
'''


class BatchInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="batch-installer-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / "repo with spaces"
        self.repo.mkdir()
        self.script = self.repo / "install_all.sh"
        shutil.copy2(ROOT / "install_all.sh", self.script)
        for _, filename, _ in INSTALLERS:
            (self.repo / filename).write_text(CHILD)
        for filename in HELPERS:
            path = self.repo / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Fixture helper\n")
        self.home = self.base / "home with spaces"
        self.home.mkdir()
        self.codex = self.home / "custom codex"
        self.cwd = self.base / "unrelated project"
        self.cwd.mkdir()
        self.log = self.base / "calls.jsonl"
        self.env = dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.codex),
                        BULK_TEST_PYTHON=sys.executable, BULK_TEST_LOG=str(self.log),
                        BULK_TEST_FAILURES="{}")

    def invoke(self, *args):
        return subprocess.run(["bash", str(self.script), *args], cwd=self.cwd,
                              env=self.env, text=True, capture_output=True, timeout=10)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def expected(self, *ids):
        return [{"script": script, "args": args} for tool, script, args in INSTALLERS if not ids or tool in ids]

    def test_default_preview_invokes_nothing_and_preserves_home(self):
        marker = self.codex / "basic-memory-workgraph"
        marker.mkdir(parents=True)
        config = marker / "config.json"
        config.write_text('{"auto": "off", "project": "existing-project"}\n')
        before = {p.relative_to(self.home): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PREVIEW", result.stdout)
        self.assertIn("--update", result.stdout)
        self.assertEqual(len([line for line in result.stdout.splitlines() if line.startswith("[codex-tools]")]), 10)
        self.assertEqual(self.calls(), [])
        self.assertEqual(before, {p.relative_to(self.home): p.read_bytes() for p in self.home.rglob("*") if p.is_file()})

    def test_explicit_preview_selects_without_invoking_apply_only_children(self):
        result = self.invoke("--dry-run", "--only", "yomiyasu,ux-stack")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertIn("ux-stack:", lines[0])
        self.assertIn("yomiyasu:", lines[1])
        self.assertIn("--apply", lines[1])
        self.assertEqual(len(lines), 3)
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.codex.exists())

    def test_apply_all_uses_each_installers_standard_install_mode(self):
        result = self.invoke("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), self.expected())
        self.assertIn("COMPLETE: 9", result.stdout)
        self.assertNotIn("--force", result.stdout)

    def test_repeated_selection_is_deduplicated_and_runs_from_any_directory(self):
        result = self.invoke("--only", "yomiyasu,office", "--only", "ux-stack,yomiyasu", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), self.expected("ux-stack", "office", "yomiyasu"))
        self.assertIn("COMPLETE: 3", result.stdout)

    def test_existing_workgraph_uses_update_and_keeps_its_settings(self):
        for custom_root in (True, False):
            with self.subTest(custom_root=custom_root):
                codex = self.codex if custom_root else self.home / ".codex"
                if not custom_root:
                    self.env.pop("CODEX_HOME")
                marker = codex / "basic-memory-workgraph"
                marker.mkdir(parents=True)
                config = marker / "config.json"
                original = b'{"project": "custom", "auto": "off", "memory_dir": "custom notes"}\n'
                config.write_bytes(original)
                self.log.unlink(missing_ok=True)
                result = self.invoke("--only", "workgraph", "--apply")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.calls(), [{"script": INSTALLERS[0][1], "args": ["--update"]}])
                self.assertEqual(config.read_bytes(), original)

    def test_dangling_workgraph_marker_does_not_trigger_a_fresh_install(self):
        self.codex.mkdir()
        (self.codex / "basic-memory-workgraph").symlink_to(self.base / "missing config")
        result = self.invoke("--only", "workgraph", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [{"script": INSTALLERS[0][1], "args": ["--update"]}])

    def test_invalid_arguments_fail_before_any_child_or_shell_expansion(self):
        injection = "$(touch " + str(self.base / "injected") + ")"
        invalid = [
            ["--only"], ["--only", ""], ["--only", "--apply"],
            ["--only", "missing"], ["--only", ",ux-stack"],
            ["--only", "ux-stack,"], ["--only", "ux-stack,,office"],
            ["--only", "ux-stack\nherdr"], ["--only", "ux-stack, office"],
            ["--only", injection], ["--apply", "--dry-run"],
            ["--dry-run", "--apply"], ["--list", "--apply"], ["--force"],
        ]
        for args in invalid:
            with self.subTest(args=args):
                result = self.invoke(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("ERROR", result.stderr)
                self.assertEqual(self.calls(), [])
        self.assertFalse((self.base / "injected").exists())

    def test_missing_late_installer_is_detected_before_any_installation(self):
        (self.repo / INSTALLERS[-1][1]).unlink()
        result = self.invoke("--apply")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(INSTALLERS[-1][1], result.stderr)
        self.assertEqual(self.calls(), [])

    def test_selected_helper_must_exist_before_any_installation(self):
        for filename in (HELPERS[1], HELPERS[-1]):
            with self.subTest(filename=filename):
                path = self.repo / filename
                path.unlink()
                result = self.invoke("--apply", "--only", "workgraph,ecc")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("リポジトリ一式", result.stderr)
                self.assertEqual(self.calls(), [])
                path.write_text("# Fixture helper\n")

    def test_unselected_tools_are_not_required(self):
        for _, filename, _ in INSTALLERS[:-1]:
            (self.repo / filename).unlink()
        shutil.rmtree(self.repo / "tools")
        result = self.invoke("--only", "herdr", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), self.expected("herdr"))

    def test_failures_are_reported_and_other_tools_still_run(self):
        self.env["BULK_TEST_FAILURES"] = json.dumps({INSTALLERS[0][1]: 2, INSTALLERS[6][1]: 7})
        result = self.invoke("--apply")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.calls(), self.expected())
        self.assertIn("workgraph: INCOMPLETE (exit 2)", result.stdout)
        self.assertIn("office: INCOMPLETE (exit 7)", result.stdout)
        self.assertIn("herdr: OK", result.stdout)
        self.assertIn("成功 7 / 未完了 2", result.stderr)
        self.assertNotIn("[codex-tools] COMPLETE", result.stdout)

    def test_interrupt_exit_stops_subsequent_installers(self):
        for code in (130, 143):
            with self.subTest(code=code):
                self.log.unlink(missing_ok=True)
                self.env["BULK_TEST_FAILURES"] = json.dumps({INSTALLERS[1][1]: code})
                result = self.invoke("--apply")
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(self.calls(), self.expected("workgraph", "ux-stack"))
                self.assertIn("workgraph: OK", result.stdout)
                self.assertIn("INTERRUPTED", result.stderr)

    def test_help_and_list_work_without_repository_payloads(self):
        for _, filename, _ in INSTALLERS:
            (self.repo / filename).unlink()
        shutil.rmtree(self.repo / "tools")
        result = self.invoke("--list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([line.split()[0] for line in result.stdout.splitlines()], [tool for tool, _, _ in INSTALLERS])
        help_result = self.invoke("--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("--only", help_result.stdout)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
