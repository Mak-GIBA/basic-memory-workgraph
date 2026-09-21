import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parent.parent
POLICY = (REPO / "memory-policy.md").read_text().strip()


class WorkgraphTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.codex = self.home / "custom codex ' $()"
        self.codex.mkdir()
        self.env = {key: value for key, value in os.environ.items()
                    if key not in ("BM_AUTO_MODE", "MEMORY_PROJECT", "MEMORY_DIR")}
        self.env.update(HOME=str(self.home), CODEX_HOME=str(self.codex))

    def write_json(self, relative, value):
        path = self.codex / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def read_json(self, relative):
        return json.loads((self.codex / relative).read_text())

    def install(self, **overrides):
        return subprocess.run(
            ["bash", str(REPO / "install_basic_memory_workgraph.sh"), "--configure-only"],
            env={**self.env, **overrides}, capture_output=True, text=True,
        )

    def hook(self, action, event, raw=False):
        result = subprocess.run(
            [sys.executable, str(self.codex / "hooks/basic_memory_workgraph.py"), action],
            input=event if raw else json.dumps(event), capture_output=True, text=True,
            env=self.env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def state_files(self):
        return list((self.codex / "basic-memory-workgraph/state").glob("*.json"))

    def test_configure_only_preserves_settings_notes_and_other_hooks(self):
        self.write_json("basic-memory.json", {"other": 42, "basicMemory": {
            "primaryProject": "chosen", "captureEvents": False, "custom": [1],
            "checkpointOnCompact": True, "rememberFolder": "manual",
        }})
        self.write_json("basic-memory-workgraph/config.json", {"mode": "off", "other": 3})
        sibling = {"type": "command", "command": "python3 other_hook.py"}
        self.write_json("hooks.json", {"custom": "keep", "hooks": {
            "Stop": [{"matcher": "keep", "hooks": [sibling, {
                "type": "command", "command": "python3 basic_memory_workgraph_save.py",
            }]}], "OtherEvent": [{"hooks": [sibling]}],
        }})
        notes = self.home / "knowledge/chosen"
        notes.mkdir(parents=True)
        note = notes / "existing.md"
        note.write_text("Existing note\n")
        original = note.stat().st_mtime_ns, note.read_bytes()
        result = self.install(MEMORY_DIR=str(notes))
        self.assertEqual(result.returncode, 0, result.stderr)
        config = self.read_json("basic-memory.json")
        self.assertEqual(config["other"], 42)
        bm = config["basicMemory"]
        self.assertEqual(bm["primaryProject"], "chosen")
        self.assertFalse(bm["checkpointOnCompact"])
        self.assertFalse(bm["captureEvents"])
        self.assertEqual(bm["custom"], [1])
        self.assertEqual(bm["rememberFolder"], "manual")
        self.assertEqual(bm["placementConventions"], POLICY)
        self.assertEqual(self.read_json("basic-memory-workgraph/config.json"), {"mode": "off", "other": 3})
        hooks = self.read_json("hooks.json")
        self.assertEqual(hooks["custom"], "keep")
        self.assertEqual(hooks["hooks"]["Stop"][0], {"matcher": "keep", "hooks": [sibling]})
        self.assertEqual(hooks["hooks"]["OtherEvent"], [{"hooks": [sibling]}])
        self.assertEqual((note.stat().st_mtime_ns, note.read_bytes()), original)
        self.assertEqual(list(notes.iterdir()), [note])
        self.assertTrue(list(self.codex.glob("basic-memory.json.bak.*")))

    def test_idempotent_and_explicit_overrides(self):
        self.assertEqual(self.install().returncode, 0)
        before = {p.relative_to(self.codex): p.read_bytes() for p in self.codex.rglob("*") if p.is_file()}
        self.assertEqual(self.install().returncode, 0)
        after = {p.relative_to(self.codex): p.read_bytes() for p in self.codex.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(self.install(MEMORY_PROJECT="explicit", BM_AUTO_MODE="always").returncode, 0)
        self.assertEqual(self.read_json("basic-memory.json")["basicMemory"]["primaryProject"], "explicit")
        self.assertEqual(self.read_json("basic-memory-workgraph/config.json")["mode"], "always")

    def test_invalid_config_never_overwrites_existing_files(self):
        for relative, contents in (
            ("basic-memory.json", "{"), ("basic-memory.json", '[]'),
            ("hooks.json", '{"hooks": {"Stop": [null]}}'),
            ("basic-memory-workgraph/config.json", '{"mode": "typo"}'),
        ):
            with self.subTest(relative=relative, contents=contents):
                path = self.codex / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents)
                before = {p: p.read_bytes() for p in self.codex.rglob("*") if p.is_file()}
                self.assertNotEqual(self.install().returncode, 0)
                after = {p: p.read_bytes() for p in self.codex.rglob("*") if p.is_file()}
                self.assertEqual(before, after)
                path.unlink()

    def test_invalid_mode_fails_before_install(self):
        self.assertNotEqual(self.install(BM_AUTO_MODE="sometimes").returncode, 0)
        self.assertEqual(list(self.codex.iterdir()), [])

    def test_configure_only_never_invokes_package_or_plugin_commands(self):
        binaries = self.home / "bin"
        binaries.mkdir()
        for command in ("codex", "uv", "uvx", "curl", "bm"):
            path = binaries / command
            path.write_text('#!/bin/sh\ntouch "$HOME/unexpected-command"\nexit 91\n')
            path.chmod(0o755)
        result = self.install(PATH=str(binaries) + os.pathsep + os.environ["PATH"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.home / "unexpected-command").exists())

    def test_full_installer_uses_same_policy_with_mocked_dependencies(self):
        binaries = self.home / "bin"
        binaries.mkdir()
        for command in ("codex", "uv", "uvx", "curl", "bm"):
            path = binaries / command
            path.write_text('#!/bin/sh\nexit 0\n')
            path.chmod(0o755)
        result = subprocess.run(
            ["bash", str(REPO / "install_basic_memory_workgraph.sh")],
            env={**self.env, "PATH": str(binaries) + os.pathsep + os.environ["PATH"]},
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read_json("basic-memory.json")["basicMemory"]["placementConventions"], POLICY)
        self.assertFalse(self.read_json("basic-memory.json")["basicMemory"]["checkpointOnCompact"])
        self.assertEqual(len(list((self.home / "knowledge/codex-memory/schemas").glob("*.md"))), 7)

    def test_short_preference_gets_policy_and_one_evaluation(self):
        self.assertEqual(self.install().returncode, 0)
        event = {"session_id": "session", "turn_id": "short", "prompt": "今後日本語で"}
        recall = self.hook("recall", event)["hookSpecificOutput"]["additionalContext"]
        self.assertTrue(recall.startswith(POLICY))
        self.assertEqual(json.loads(self.state_files()[0].read_text()), {"candidate": True})
        stop = self.hook("save", {**event, "last_assistant_message": "承知しました。"})
        self.assertEqual(stop["decision"], "block")
        self.assertIn(POLICY, stop["reason"])
        self.assertEqual(self.state_files(), [])
        self.assertEqual(self.hook("save", {**event, "stop_hook_active": True}), {})

    def test_length_and_one_off_edits_do_not_trigger(self):
        self.assertEqual(self.install().returncode, 0)
        for prompt in ("説明してください。" * 200, "このボタンを修正して。もっと青く。"):
            with self.subTest(prompt=prompt[:30]):
                event = {"turn_id": "long", "prompt": prompt}
                self.hook("recall", event)
                self.assertEqual(self.hook("save", {**event, "last_assistant_message": "完了しました。" * 500}), {})

    def test_answer_can_supply_a_lesson_signal(self):
        self.assertEqual(self.install().returncode, 0)
        for answer in ("根本原因を確認しました。", "The root cause was reproduced."):
            self.assertEqual(self.hook("save", {"last_assistant_message": answer})["decision"], "block")

    def test_always_and_off_modes(self):
        self.assertEqual(self.install(BM_AUTO_MODE="always").returncode, 0)
        self.assertEqual(self.hook("save", {})["decision"], "block")
        self.assertEqual(self.hook("save", {"stop_hook_active": True}), {})
        self.assertEqual(self.install(BM_AUTO_MODE="off").returncode, 0)
        recall = self.hook("recall", {"turn_id": "off", "prompt": "覚えて"})
        self.assertIn("Automatic persistence is off", recall["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.hook("save", {"turn_id": "off", "last_assistant_message": "lesson"}), {})

    def test_corrupt_or_missing_runtime_policy_skips_automatic_writes(self):
        self.assertEqual(self.install().returncode, 0)
        for relative, content in (("config.json", "[]"), ("config.json", '{"mode":"bad"}'), ("memory-policy.md", "")):
            path = self.codex / "basic-memory-workgraph" / relative
            original = path.read_text()
            path.write_text(content)
            self.assertEqual(self.hook("save", {"last_assistant_message": "lesson"}), {})
            self.assertIn("Skip automatic memory writes", self.hook("recall", {})["hookSpecificOutput"]["additionalContext"])
            path.write_text(original)
        (self.codex / "basic-memory-workgraph/memory-policy.md").unlink()
        self.assertEqual(self.hook("save", {"last_assistant_message": "lesson"}), {})

    def test_malformed_events(self):
        self.assertEqual(self.install().returncode, 0)
        for raw in ("{", "null", "[]", '"text"'):
            for action in ("recall", "save"):
                self.assertEqual(self.hook(action, raw, raw=True), {})

    def test_state_is_isolated_and_ids_cannot_escape_directory(self):
        self.assertEqual(self.install().returncode, 0)
        event = {"turn_id": "../../escape", "prompt": "今後日本語で"}
        self.hook("recall", {**event, "session_id": "one"})
        self.hook("recall", {**event, "session_id": "two", "prompt": "今回だけ青に"})
        self.assertEqual(len(self.state_files()), 2)
        for path in self.state_files():
            self.assertEqual(len(path.stem), len(hashlib.sha256().hexdigest()))
        self.assertEqual(self.hook("save", {**event, "session_id": "two"}), {})
        self.assertEqual(self.hook("save", {**event, "session_id": "one"})["decision"], "block")

    def test_registered_command_handles_special_characters_in_path(self):
        self.assertEqual(self.install().returncode, 0)
        command = self.read_json("hooks.json")["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
        self.assertEqual(shlex.split(command)[1], str(self.codex / "hooks/basic_memory_workgraph.py"))
        result = subprocess.run(command, shell=True, input='{"prompt":"hi"}', text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(POLICY, json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"])

    def test_legacy_commands_use_new_policy_in_existing_sessions(self):
        for action in ("recall", "save"):
            path = self.codex / "hooks" / f"basic_memory_workgraph_{action}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("raise RuntimeError('old hook')\n")
        self.assertEqual(self.install(BM_AUTO_MODE="always").returncode, 0)
        for action in ("recall", "save"):
            result = subprocess.run(
                [sys.executable, str(self.codex / "hooks" / f"basic_memory_workgraph_{action}.py")],
                input="{}", text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(POLICY, json.dumps(json.loads(result.stdout), ensure_ascii=False).replace("\\n", "\n"))
        self.assertTrue(list((self.codex / "hooks").glob("*.bak.*")))

    def test_uninstall_preserves_sibling_hooks_and_basic_memory_config(self):
        self.assertEqual(self.install().returncode, 0)
        hooks = self.read_json("hooks.json")
        sibling = {"type": "command", "command": "other-command"}
        hooks["hooks"]["Stop"][0]["hooks"].append(sibling)
        self.write_json("hooks.json", hooks)
        before = (self.codex / "basic-memory.json").read_bytes()
        result = subprocess.run(["bash", str(REPO / "remove_workgraph_hooks.sh")], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read_json("hooks.json")["hooks"]["Stop"], [{"hooks": [sibling]}])
        self.assertFalse((self.codex / "hooks/basic_memory_workgraph.py").exists())
        self.assertFalse((self.codex / "basic-memory-workgraph").exists())
        self.assertEqual((self.codex / "basic-memory.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
