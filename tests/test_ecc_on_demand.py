"""ECC manager safety and routing checks using isolated config/cache fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / "tools/ecc-on-demand/ecc_on_demand.py"
spec = importlib.util.spec_from_file_location("ecc_on_demand", SOURCE)
ecc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ecc)

CONFIG = '''# keep this comment
model = "existing-model"
[mcp_servers.chrome-devtools]
command = "existing-browser-command"
[plugins."codex@basic-memory"]
enabled = true
[plugins."ecc@ecc"] # native plugin
enabled = true # keep this comment too
other_setting = "preserve"
'''


class FakeCodex:
    def __init__(self, home, skills_root, originals):
        self.home, self.skills_root, self.originals = home, skills_root, originals
        self.binary = "codex"
        self.failure = False
        self.calls = []

    def skills(self, cwd, enable_ecc=False):
        self.calls.append(enable_ecc)
        config = self.home / "config.toml"
        enabled = ecc.config_value(config.read_text()) if config.exists() else None
        skills = []
        if enable_ecc or enabled:
            skills.extend(self.originals)
        for name in ecc.ENTRIES:
            path = self.skills_root / name / "SKILL.md"
            if path.is_file():
                skills.append({"name": name, "path": str(path), "enabled": True})
        skills.append({"name": "yomiyasu", "path": "/unmanaged/yomiyasu/SKILL.md", "enabled": True})
        skills.append({"name": "github-project-director", "path": "/unmanaged/director/SKILL.md", "enabled": True})
        return {"cwd": str(cwd), "skills": skills, "errors": []}

    def update(self):
        path = self.home / "config.toml"
        path.write_text(ecc.edit_enabled(path.read_text(), True)
                        + '\n[updated_native_metadata]\nretained = true\n')
        if self.failure:
            raise ecc.ManagementError("fixture native update failed after re-enable")


class ManagerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ecc-on-demand-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "space and 'quote"
        self.home = self.root / ".codex"
        self.home.mkdir(parents=True)
        self.skills_root = self.root / ".agents/skills"
        self.config = self.home / "config.toml"
        self.config.write_text(CONFIG)
        self.plugin = self.home / "plugins/cache/ecc/ecc/9.0.0"
        manifest = self.plugin / ".codex-plugin/plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"name": "ecc", "version": "9.0.0"}))
        self.originals = []
        names = list(filter(None, ecc.ENTRIES.values())) + ["api-design", "database-migrations", "python-testing"]
        for name in names:
            path = self.plugin / "skills" / name / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text(f"---\nname: {name}\ndescription: {name}\n---\nOriginal body\n")
            self.originals.append({"name": "ecc:" + name, "description": name,
                                   "path": str(path), "enabled": True, "pluginId": "ecc@ecc"})
        self.codex = FakeCodex(self.home, self.skills_root, self.originals)
        self.manager = ecc.Manager(self.home, self.skills_root, self.codex, self.root)

    def test_mcp_defaults_restore_preserves_user_connections(self):
        self.config.write_text(CONFIG + '\n[mcp_servers.context7]\nenabled = false\ncommand = "user-docs"\n')
        original_servers = ecc.tomllib.loads(self.config.read_text())["mcp_servers"]
        report = self.manager.apply()
        self.assertEqual(report["mcps"]["context7"], "existing_disabled")
        parsed = ecc.tomllib.loads(self.config.read_text())["mcp_servers"]
        self.assertEqual(parsed["chrome-devtools"], original_servers["chrome-devtools"])
        self.assertEqual(parsed["context7"], original_servers["context7"])
        self.assertNotIn("parallel-search", parsed)
        self.assertNotIn("sequential-thinking", parsed)
        self.assertIn("--headless", parsed["playwright"]["args"])
        self.assertNotIn("github", parsed)
        self.manager.restore()
        self.assertEqual(ecc.tomllib.loads(self.config.read_text())["mcp_servers"], original_servers)

    def test_mcp_user_changes_prevent_apply_and_restore_without_mutation(self):
        self.manager.apply()
        self.config.write_text(self.config.read_text() + '\n[mcp_servers.context7.env]\nCONTEXT7_API_KEY = "user-value"\n')
        before = self.config.read_bytes()
        with self.assertRaisesRegex(ecc.ManagementError, "Managed MCP changed"):
            self.manager.apply()
        with self.assertRaisesRegex(ecc.ManagementError, "Managed MCP changed"):
            self.manager.restore()
        self.assertEqual(before, self.config.read_bytes())
        self.assertTrue(self.manager.state_path.is_file())

    def test_mcp_legacy_alias_and_upgrade_from_old_state(self):
        self.config.write_text(CONFIG + '\n[mcp_servers.context7-mcp]\ncommand = "legacy-docs"\n')
        self.manager.apply()
        self.assertNotIn("context7", ecc.tomllib.loads(self.config.read_text())["mcp_servers"])
        # Existing installations before MCP support have no mcps field.
        state = self.manager.state()
        text = self.config.read_text()
        for record in state.pop("mcps").values():
            text = text.replace(record["block"], "")
        self.config.write_text(text)
        self.manager.state_path.write_text(json.dumps(state))
        self.manager.apply()
        self.assertIn("playwright", self.manager.state()["mcps"])

    def test_mcp_selection_persists_and_none_keeps_prior_connections(self):
        self.manager.apply(mcps="research,cloudflare")
        state = self.manager.state()
        self.assertEqual(state["selected_mcps"], ["context7", "parallel-search", "cloudflare-docs"])
        self.assertNotIn("playwright", state["mcps"])
        before = self.config.read_bytes()
        self.assertEqual(self.manager.apply()["changed_files"], 0)
        self.manager.apply(mcps="none")
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(self.manager.state()["selected_mcps"], [])
        self.assertEqual(self.manager.apply()["changed_files"], 0)
        self.manager.restore()
        self.assertEqual(self.config.read_text(), CONFIG)

    def test_legacy_owned_mcp_survives_new_defaults_and_can_be_restored(self):
        self.manager.apply(mcps=tuple(ecc.MCP_SERVERS))
        state = self.manager.state()
        state.pop("selected_mcps")
        # A previous installer used a different unpinned server command.
        old = state["mcps"]["sequential-thinking"]
        old_block = old["block"]
        old["block"] = old_block.replace("@2026.8.31", "")
        old["config"]["args"][1] = old["config"]["args"][1].removesuffix("@2026.8.31")
        self.config.write_text(self.config.read_text().replace(old_block, old["block"]))
        self.manager.state_path.write_text(json.dumps(state))
        result = self.manager.apply()
        self.assertEqual(result["selected_mcps"], list(ecc.RECOMMENDED_MCPS))
        self.assertEqual(result["mcps"]["sequential-thinking"], "managed_retained")
        self.assertEqual(self.manager.doctor()["status"], "ready")
        self.manager.restore()
        self.assertEqual(self.config.read_text(), CONFIG)

    def test_mcp_presets_use_verified_flags_and_do_not_add_token_optimizer(self):
        # Remove the existing user-owned browser so a new managed one is tested.
        self.config.write_text('[plugins."ecc@ecc"]\nenabled = true\n')
        self.manager.apply(mcps="browser,cloudflare,sequential-thinking,browser")
        servers = ecc.tomllib.loads(self.config.read_text())["mcp_servers"]
        self.assertEqual(len(servers), 5)
        self.assertIn("--isolated", servers["playwright"]["args"])
        self.assertIn("--no-usage-statistics", servers["chrome-devtools"]["args"])
        self.assertIn("--no-performance-crux", servers["chrome-devtools"]["args"])
        self.assertEqual(servers["cloudflare-docs"]["url"], "https://docs.mcp.cloudflare.com/mcp")
        self.assertEqual(servers["sequential-thinking"]["env"]["DISABLE_THOUGHT_LOGGING"], "true")
        self.assertNotIn("token-optimizer", servers)

    def test_invalid_mcp_selection_stops_before_configuration_changes(self):
        for value in ["typo", "none,context7", "context7,", "token-optimizer"]:
            with self.subTest(value=value):
                with self.assertRaises(ecc.ManagementError):
                    self.manager.apply(mcps=value)
                self.assertEqual(self.config.read_text(), CONFIG)
                self.assertFalse(self.manager.state_path.exists())

    def test_apply_is_idempotent_preserves_other_settings_and_keeps_originals(self):
        originals = {Path(s["path"]): Path(s["path"]).read_bytes() for s in self.originals}
        self.manager.apply()
        self.assertFalse(ecc.config_value(self.config.read_text()))
        state = self.manager.state()
        before = {Path(path): (Path(path).read_bytes(), Path(path).stat().st_mtime_ns)
                  for path in state["files"]}
        self.assertEqual(Path(state["backup"]).read_text(), CONFIG)
        self.assertEqual(Path(state["backup"]).stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.manager.apply()["changed_files"], 0)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})
        self.assertEqual(originals, {p: p.read_bytes() for p in originals})
        parsed = ecc.tomllib.loads(self.config.read_text())
        self.assertTrue(parsed["plugins"]["codex@basic-memory"]["enabled"])
        self.assertEqual(parsed["mcp_servers"]["chrome-devtools"]["command"], "existing-browser-command")
        self.assertIn('# keep this comment', self.config.read_text())
        self.assertIn('# keep this comment too', self.config.read_text())
        self.assertEqual(self.manager.doctor()["status"], "ready")

    def test_restore_preserves_settings_added_after_apply_and_is_repeatable(self):
        self.manager.apply()
        self.config.write_text(self.config.read_text() + '\n[future_setting]\nkeep = "later"\n')
        self.manager.restore()
        self.assertTrue(ecc.config_value(self.config.read_text()))
        self.assertEqual(ecc.tomllib.loads(self.config.read_text())["future_setting"]["keep"], "later")
        for name in ecc.ENTRIES:
            self.assertFalse((self.skills_root / name).exists())
        self.assertEqual(self.manager.restore()["status"], "already_restored")

    def test_originally_absent_enabled_is_removed_on_restore(self):
        self.config.write_text('model = "keep"\n[plugins."codex@basic-memory"]\nenabled = true\n')
        self.manager.apply()
        self.manager.restore()
        self.assertIsNone(ecc.config_value(self.config.read_text()))
        self.assertEqual(ecc.tomllib.loads(self.config.read_text())["model"], "keep")

    def test_conflicting_unmanaged_skill_aborts_before_config_change(self):
        existing = self.skills_root / "ecc-errors"
        existing.mkdir(parents=True)
        (existing / "SKILL.md").write_text("User owned")
        with self.assertRaisesRegex(ecc.ManagementError, "unmanaged"):
            self.manager.apply()
        self.assertEqual(self.config.read_text(), CONFIG)
        self.assertFalse(self.manager.state_path.exists())

    def test_modified_managed_file_is_preserved_by_apply_and_restore(self):
        self.manager.apply()
        file = self.skills_root / "ecc-python/SKILL.md"
        file.write_text("User changed this")
        before = self.config.read_bytes()
        for action in (self.manager.apply, self.manager.restore):
            with self.assertRaisesRegex(ecc.ManagementError, "changed"):
                action()
        self.assertEqual(file.read_text(), "User changed this")
        self.assertEqual(self.config.read_bytes(), before)

    def test_extra_empty_directory_blocks_restore_before_setting_change(self):
        self.manager.apply()
        (self.skills_root / "ecc-errors/user-resources").mkdir()
        with self.assertRaisesRegex(ecc.ManagementError, "Unexpected files"):
            self.manager.restore()
        self.assertFalse(ecc.config_value(self.config.read_text()))

    def test_apply_rolls_back_written_files_if_config_write_fails(self):
        real_write = ecc.atomic_write

        def fail_config(path, data, mode=0o600):
            if path == self.config:
                raise OSError("fixture config write error")
            return real_write(path, data, mode)

        with mock.patch.object(ecc, "atomic_write", side_effect=fail_config):
            with self.assertRaises(OSError):
                self.manager.apply()
        self.assertEqual(self.config.read_text(), CONFIG)
        self.assertFalse(self.manager.state_path.exists())
        self.assertFalse(self.manager.installed_script.exists())
        self.assertFalse(any(self.skills_root.rglob("SKILL.md")))
        self.manager.apply()
        self.assertEqual(self.manager.doctor()["status"], "ready")

    def test_restore_rolls_back_partial_unlink_failure_and_can_retry(self):
        self.manager.apply()
        before = self.config.read_bytes()
        files = {Path(path): Path(path).read_bytes() for path in self.manager.state()["files"]}
        failure_path = self.skills_root / "ecc-errors/SKILL.md"
        original_unlink = Path.unlink

        def fail_once(path, *args, **kwargs):
            if path == failure_path:
                raise PermissionError("fixture unlink failed")
            return original_unlink(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", fail_once):
            with self.assertRaises(PermissionError):
                self.manager.restore()
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(files, {path: path.read_bytes() for path in files})
        self.assertEqual(self.manager.doctor()["status"], "ready")
        self.manager.restore()
        self.assertTrue(ecc.config_value(self.config.read_text()))

    def test_update_success_and_partial_failure_both_leave_ecc_disabled(self):
        self.manager.apply()
        for fail in (False, True):
            self.codex.failure = fail
            if fail:
                self.config.write_text(self.config.read_text().split('\n[updated_native_metadata]')[0])
            report = self.manager.update()
            self.assertFalse(ecc.config_value(self.config.read_text()))
            self.assertEqual(report["native_update"], "failed" if fail else "completed")
            self.assertEqual(ecc.tomllib.loads(self.config.read_text())["updated_native_metadata"], {"retained": True})
            self.assertEqual(report["status"], "needs_attention" if fail else "ready")

    def test_native_update_commands_and_failure_keep_setting_disabled(self):
        self.manager.apply()
        binary = self.root / "fake-native-codex"
        binary.write_text('''#!/usr/bin/env python3
import os,sys,pathlib,json
root=pathlib.Path(os.environ['CODEX_HOME'])
with (root/'native-calls.jsonl').open('a') as stream: stream.write(json.dumps(sys.argv[1:])+'\\n')
config=root/'config.toml'
config.write_text(config.read_text().replace('enabled = false # keep','enabled = true # keep'))
if sys.argv[1:3]==['plugin','add'] and os.environ.get('FAIL_NATIVE_ADD'):
 print('fixture native add failure',file=sys.stderr);sys.exit(7)
print('{}')
''')
        binary.chmod(0o755)
        native = ecc.Codex(str(binary), self.home)
        native.skills = self.codex.skills
        self.manager.codex = native
        for failure in (False, True):
            if failure:
                native.env['FAIL_NATIVE_ADD'] = '1'
            report = self.manager.update()
            self.assertFalse(ecc.config_value(self.config.read_text()))
            self.assertEqual(report['native_update'], 'failed' if failure else 'completed')
        calls = [json.loads(line) for line in (self.home/'native-calls.jsonl').read_text().splitlines()]
        self.assertEqual(calls, [['plugin','marketplace','upgrade','ecc','--json'],
                                 ['plugin','add','ecc@ecc','--json']] * 2)

    def test_installed_entrypoint_command_handles_spaces_and_custom_home(self):
        self.manager.apply()
        binary = self.root / "fake-entry-codex"
        fixture = self.root / "catalog.json"
        fixture.write_text(json.dumps({"data": [{"cwd": str(self.root), "skills": self.originals, "errors": []}]}))
        binary.write_text('''#!/usr/bin/env python3
import json,sys,pathlib,os
expected=pathlib.Path(__file__).parent/'.codex'
assert os.environ['CODEX_HOME']==str(expected)
for line in sys.stdin:
 event=json.loads(line)
 if 'id' not in event: continue
 result={} if event['method']=='initialize' else json.loads(pathlib.Path(__file__).with_name('catalog.json').read_text())
 print(json.dumps({'id':event['id'],'result':result}),flush=True)
''')
        binary.chmod(0o755)
        text = (self.skills_root / "ecc-python/SKILL.md").read_text()
        command = text.split('`')[1]
        # Use the actual installed skill command; only substitute the Codex
        # executable to avoid starting native infrastructure in this test.
        args = ecc.shlex.split(command)
        args[args.index('--codex') + 1] = str(binary)
        result = subprocess.run(args, cwd=self.root, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['plugin_root'], str(self.plugin))

    def test_doctor_detects_native_reenable_and_missing_original(self):
        self.manager.apply()
        self.config.write_text(ecc.edit_enabled(self.config.read_text(), True))
        report = self.manager.doctor()
        self.assertEqual(report["status"], "needs_attention")
        self.assertGreater(report["active_native_ecc_skills"], 0)
        self.manager.apply()
        Path(self.originals[0]["path"]).unlink()
        report = self.manager.doctor()
        self.assertEqual(report["status"], "needs_attention")
        self.assertTrue(any("missing" in issue for issue in report["issues"]))

    def test_runtime_catalog_ignores_newer_unregistered_cache(self):
        decoy = self.home / "plugins/cache/ecc/ecc/99.0.0/skills/python-patterns/SKILL.md"
        decoy.parent.mkdir(parents=True)
        decoy.write_text("Must never select by version sorting")
        result = ecc.catalog(self.codex, self.root)
        python = next(s for s in result if s["name"] == "python-patterns")
        self.assertEqual(python["version"], "9.0.0")
        self.assertEqual(Path(python["plugin_root"]), self.plugin)
        self.assertTrue(Path(python["skill_dir"]).is_dir())

    def test_routing_python_api_database_and_explicit_skill(self):
        skills = ecc.catalog(self.codex, self.root)
        (self.root / "pyproject.toml").write_text('[project]\nname="fixture"\n')
        for query, expected in [("Python テスト", "python-testing"),
                                ("API 設計", "api-design"),
                                ("DB マイグレーション", "database-migrations"),
                                ("ecc:python-patterns", "python-patterns")]:
            with self.subTest(query=query):
                results = ecc.search_catalog(skills, query, self.root)
                self.assertEqual(results[0]["name"], expected)
                self.assertLessEqual(len(results), 5)
        self.assertEqual(ecc.search_catalog(skills, "unrelated-nonsense", self.root), [])

    def test_inline_plugin_config_is_rejected_without_writing(self):
        text = 'plugins = { "ecc@ecc" = { enabled = true } }\n'
        self.config.write_text(text)
        with self.assertRaisesRegex(ecc.ManagementError, "unsupported"):
            self.manager.apply()
        self.assertEqual(self.config.read_text(), text)
        self.assertFalse(self.manager.state_path.exists())


class ProtocolTest(unittest.TestCase):
    def test_catalog_rpc_reads_large_frames_and_never_starts_a_thread(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "fake-codex"
            log = root / "calls.jsonl"
            binary.write_text('''#!/usr/bin/env python3
import json,sys,pathlib
log=pathlib.Path(__file__).with_name('calls.jsonl')
with log.open('a') as stream: stream.write(json.dumps(sys.argv[1:])+'\\n')
for line in sys.stdin:
 event=json.loads(line)
 with log.open('a') as stream: stream.write(json.dumps(event)+'\\n')
 if 'id' not in event: continue
 if event['method']=='initialize': result={}
 elif event['method']=='skills/list':
  print(json.dumps({'method':'notification','params':{'large':'x'*100000}}),flush=True)
  result={'data':[{'cwd':event['params']['cwds'][0],'skills':[],'errors':[]}]}
 else: raise RuntimeError('Unexpected model or thread operation')
 print(json.dumps({'id':event['id'],'result':result}),flush=True)
''')
            binary.chmod(0o755)
            config = root / "config.toml"
            config.write_text(CONFIG)
            codex = ecc.Codex(str(binary), root, timeout=5)
            self.assertEqual(codex.skills(root, enable_ecc=True)["skills"], [])
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(calls[0], ['-c', 'plugins.ecc@ecc.enabled=true', 'app-server', '--stdio'])
            self.assertEqual([c["method"] for c in calls[1:]], ['initialize', 'initialized', 'skills/list'])
            self.assertEqual(config.read_text(), CONFIG)


if __name__ == "__main__":
    unittest.main()
