import base64
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/design-research"


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


installer = module("design_research_installer", SOURCE / "install_design_research.py")
builder = module("design_research_builder", SOURCE / "build_installer.py")


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dr-install-test-")
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.script = self.root / "install_design_research.sh"
        self.script.write_text(builder.render())
        self.payload, _ = builder.bundle()
        self.decoded = {name: base64.b64decode(meta["data_b64"])
                        for name, meta in self.payload["files"].items()}
        self.env = {**os.environ, "HOME": str(self.home), "CODEX_HOME": str(self.home / ".codex"),
                    "PYTHONDONTWRITEBYTECODE": "1"}

    def tearDown(self):
        self.temp.cleanup()

    def run_installer(self, *args):
        return subprocess.run(["bash", str(self.script), *args], env=self.env,
                              capture_output=True, text=True, timeout=25)

    def output(self, *args):
        result = self.run_installer(*args, "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_single_file_install_in_fresh_current_skill_directory(self):
        result = self.output()
        target = self.home / ".agents/skills/design-research"
        self.assertEqual(result["target"], str(target))
        self.assertTrue((target / "scripts/gan-harness.sh").is_file())
        self.assertTrue(os.access(target / "scripts/gan-harness.sh", os.X_OK))
        self.assertFalse((self.home / ".codex/config.toml").exists())
        status = self.output("--status")
        self.assertEqual(status["state"], "installed")
        self.assertFalse(status["modified"])

    def test_dry_run_does_not_create_destination_or_config(self):
        result = self.output("--dry-run")
        self.assertTrue(result["dry_run"])
        self.assertFalse((self.home / ".agents").exists())
        self.assertFalse((self.home / ".codex").exists())

    def test_project_scope_and_explicit_scope(self):
        project = self.root / "project"
        result = self.output("--project", str(project))
        self.assertEqual(result["target"], str(project / ".agents/skills/design-research"))
        result = self.output("--skills-dir", str(self.root / "custom"))
        self.assertEqual(result["target"], str(self.root / "custom/design-research"))

    def test_legacy_managed_installation_is_reused_without_duplicate(self):
        legacy = self.home / ".codex/skills"
        installer.perform(legacy, self.payload, self.decoded)
        manifest = legacy / "design-research/.design-research-install.json"
        data = json.loads(manifest.read_text())
        data["version"] = "1.1.0"
        manifest.write_text(json.dumps(data))
        capabilities = subprocess.CompletedProcess([], 0,
            "--json --output-schema --output-last-message --sandbox --ephemeral", "")
        with patch.object(installer.shutil, "which", return_value="/example/codex"), \
                patch.object(installer.subprocess, "run", return_value=capabilities):
            old_diagnostic = installer.doctor(legacy)
        self.assertTrue(old_diagnostic["installed_integrity"])
        self.assertTrue(old_diagnostic["harness_environment_ready"])
        self.assertFalse(old_diagnostic["installed_harness_ready"])
        self.assertFalse(old_diagnostic["ready"])
        result = self.output()
        self.assertEqual(result["action"], "skip")
        result = self.output("--update")
        self.assertEqual(result["target"], str(legacy / "design-research"))
        self.assertFalse((self.home / ".agents/skills/design-research").exists())
        self.assertTrue(Path(result["backup"]).is_dir())
        with patch.object(installer.shutil, "which", return_value="/example/codex"), \
                patch.object(installer.subprocess, "run", return_value=capabilities):
            self.assertTrue(installer.doctor(legacy)["ready"])

    def test_multiple_placements_require_explicit_choice(self):
        for root in [self.home / ".codex/skills", self.home / ".agents/skills"]:
            installer.perform(root, self.payload, self.decoded)
        result = self.run_installer("--status", "--json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Multiple", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.output("--status", "--skills-dir", str(self.home / ".agents/skills"))

    def test_reexecution_keeps_unchanged_files(self):
        self.output()
        target = self.home / ".agents/skills/design-research/SKILL.md"
        stamp = target.stat().st_mtime_ns
        self.assertEqual(self.output()["action"], "skip")
        self.assertEqual(target.stat().st_mtime_ns, stamp)

    def test_unmanaged_path_is_protected_even_force(self):
        target = self.home / ".agents/skills/design-research"
        target.mkdir(parents=True)
        (target / "personal.txt").write_text("keep me")
        result = self.run_installer("--force")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unmanaged", result.stderr)
        self.assertEqual((target / "personal.txt").read_text(), "keep me")

    def test_edits_require_force_and_are_backed_up(self):
        self.output()
        target = self.home / ".agents/skills/design-research"
        (target / "personal.txt").write_text("local addition")
        (target / "SKILL.md").write_text("local edit")
        failed = self.run_installer("--update")
        self.assertNotEqual(failed.returncode, 0)
        result = self.output("--update", "--force")
        backup = Path(result["backup"])
        self.assertEqual((backup / "SKILL.md").read_text(), "local edit")
        self.assertEqual((backup / "personal.txt").read_text(), "local addition")
        self.assertFalse((target / "personal.txt").exists())

    def test_uninstall_moves_owned_content_into_durable_backup(self):
        installed = self.output()
        result = self.output("--uninstall")
        self.assertFalse(Path(installed["target"]).exists())
        self.assertTrue((Path(result["backup"]) / "SKILL.md").is_file())
        self.assertEqual(self.output("--uninstall")["action"], "skip")

    def test_failed_stage_swap_restores_original(self):
        root = self.root / "skills"
        installer.perform(root, self.payload, self.decoded)
        target = root / "design-research"
        original = installer.tree_hashes(target)
        replace = os.replace
        def fail_swap(source, destination):
            if Path(source).name.startswith(".design-research-stage-"):
                raise OSError("simulated swap failure")
            return replace(source, destination)
        with patch.object(installer.os, "replace", side_effect=fail_swap):
            with self.assertRaises(OSError):
                installer.perform(root, self.payload, self.decoded, update=True)
        self.assertEqual(installer.tree_hashes(target), original)
        self.assertFalse(list(root.glob(".design-research-stage-*")))

    def test_rollback_renames_do_not_cross_backup_filesystem(self):
        root = self.root / "skills"
        installer.perform(root, self.payload, self.decoded)
        backup = self.root / "separate-backup-filesystem" / "archive"
        replace = os.replace
        def forbid_cross_device(source, destination):
            if "separate-backup-filesystem" in str(source) or "separate-backup-filesystem" in str(destination):
                raise OSError("EXDEV")
            return replace(source, destination)
        with patch.object(installer, "backup_location", return_value=backup), \
                patch.object(installer.os, "replace", side_effect=forbid_cross_device):
            result = installer.perform(root, self.payload, self.decoded, update=True)
        self.assertEqual(result["action"], "update")
        self.assertTrue((backup / "SKILL.md").is_file())

    def test_symlink_destination_is_refused(self):
        root = self.root / "real"
        root.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(root, target_is_directory=True)
        result = self.run_installer("--skills-dir", str(alias))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((root / "design-research").exists())

    def test_payload_corruption_is_detected_before_install(self):
        text = self.script.read_text()
        head, payload = text.split("\n__DESIGN_RESEARCH_PAYLOAD__\n", 1)
        self.script.write_text(head + "\n__DESIGN_RESEARCH_PAYLOAD__\n" +
                              ("A" if payload[0] != "A" else "B") + payload[1:])
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checksum", result.stderr)
        self.assertFalse((self.home / ".agents").exists())

    def test_extract_and_legacy_scholarly_commands_work_without_codex(self):
        destination = self.root / "extract"
        self.output("--extract", str(destination))
        result = subprocess.run([sys.executable, "-B", str(destination / "scripts/research.py"), "providers"],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(json.loads(result.stdout)["no_required_mcp"])
        result = subprocess.run(["bash", str(destination / "scripts/gan-harness.sh"), "--help"],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("research", result.stdout)
        failed = self.run_installer("--extract", str(destination))
        self.assertNotEqual(failed.returncode, 0)

    def test_lock_prevents_concurrent_install(self):
        root = self.root / "skills"
        root.mkdir()
        with installer.install_lock(root):
            with self.assertRaises(installer.InstallError):
                installer.perform(root, self.payload, self.decoded)
        self.assertFalse((root / "design-research").exists())

    def test_distribution_is_deterministic(self):
        self.assertEqual(builder.render(), builder.render())
        for name, meta in self.payload["files"].items():
            self.assertEqual(base64.b64decode(meta["data_b64"]), (SOURCE / "skill" / name).read_bytes())

    def test_internal_self_test_uses_temporary_installation(self):
        result = self.output("--self-test")
        self.assertEqual(result["self_test"], "passed")
        self.assertFalse((self.home / ".agents").exists())


if __name__ == "__main__":
    unittest.main()
