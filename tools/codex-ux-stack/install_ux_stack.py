#!/usr/bin/env python3
"""Codex UX Stack installer; all Codex/npm mutations go through explicit argv."""
from __future__ import annotations
import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent
VERSION = "1.1.0"
PLUGINS = ["product-design@openai-curated-remote", "build-web-apps@openai-curated-remote"]


class InstallError(Exception):
    pass


def source_key_is_critique(spec):
    return spec["directory"] == "skills/ux-critique"


def say(kind, message):
    print(f"[UX-SETUP] {kind}: {message}", flush=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(path):
    path = Path(path)
    if path.is_symlink():
        return hashlib.sha256(("link:" + os.readlink(path)).encode()).hexdigest()
    if not path.exists():
        return None
    if path.is_file():
        return sha(path)
    h = hashlib.sha256()
    for p in sorted(path.rglob("*")):
        if "__pycache__" in p.parts or p.suffix in (".pyc", ".pyo"):
            continue
        rel = str(p.relative_to(path)).encode()
        if p.is_symlink():
            h.update(rel + b"\0link:" + os.readlink(p).encode())
        elif p.is_file():
            h.update(rel + b"\0" + sha(p).encode() + b":" + str(p.stat().st_mode & 0o777).encode())
    return h.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w") as f:
            os.chmod(tmp, 0o600)
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


class Installer:
    def __init__(self, args):
        self.args = args
        self.codex_home = Path(args.codex_home or os.getenv("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve()
        self.skills_root = Path(args.skills_root or Path.home() / ".agents/skills").expanduser().absolute()
        self.bin_dir = Path(args.bin_dir or Path.home() / ".local/bin").expanduser().absolute()
        self.state_root = self.codex_home / "ux-stack"
        self.manifest_path = self.state_root / "manifest.json"
        self.env = dict(os.environ, CODEX_HOME=str(self.codex_home))
        self.manifest = json.loads(self.manifest_path.read_text()) if self.manifest_path.exists() else {
            "version": VERSION, "components": {}, "operations": []}
        self.failed = False
        self.sources = json.loads((ROOT / "sources.json").read_text())
        self.runtime = self.state_root / "runtime"

    def run(self, argv, timeout=300):
        try:
            r = subprocess.run(argv, env=self.env, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise InstallError(f"{argv[0]} failed: {e}") from e
        if r.returncode:
            # Codex config/error dumps can contain user secrets; do not print raw stderr.
            raise InstallError(f"{argv[0]} exited {r.returncode}; inspect that tool directly for details.")
        return r

    def cli_json(self, argv):
        r = self.run(argv, 45)
        try:
            return json.loads(r.stdout)
        except ValueError as e:
            raise InstallError(f"{argv[0]} did not return valid JSON") from e

    def preflight(self):
        for exe in ("codex", "node", "npm"):
            if not shutil.which(exe):
                raise InstallError(f"{exe} is required")
        node = self.run(["node", "-p", "process.versions.node"]).stdout.strip()
        if int(node.split(".")[0]) < 20:
            raise InstallError("Node.js 20+ is required; installed: " + node)
        help_text = self.run(["codex", "exec", "--help"]).stdout
        if not all(flag in help_text for flag in ("--json", "--output-schema", "--sandbox", "--output-last-message")):
            raise InstallError("Codex CLI does not support structured harness execution")
        self.run(["codex", "plugin", "--help"])
        self.run(["codex", "mcp", "--help"])

    def record(self, name, status, **extra):
        event = {"name": name, "status": status, "at": dt.datetime.now(dt.timezone.utc).isoformat(), **extra}
        self.manifest["operations"].append(event)
        self.manifest["operations"] = self.manifest["operations"][-100:]
        self.manifest["version"] = VERSION
        if not self.args.dry_run and not self.args.doctor and not self.args.status:
            write_json(self.manifest_path, self.manifest)
        say(status.upper(), name + (": " + extra["message"] if "message" in extra else ""))

    def owned(self, name):
        return self.manifest["components"].get(name)

    def save_component(self, name, info):
        self.manifest["components"][name] = info
        write_json(self.manifest_path, self.manifest)

    def locate_skill(self, name):
        candidates = [self.skills_root / name, self.codex_home / "skills" / name,
                      Path.home() / ".codex/skills" / name, Path.home() / ".agents/skills" / name]
        return next((p for p in candidates if p.exists() or p.is_symlink()), candidates[0])

    def needs_tree(self, name, dest):
        if not dest.exists() and not dest.is_symlink():
            return True
        owned = self.owned(name)
        if not owned or str(dest) != owned.get("path"):
            self.record(name, "skip", message="Existing unmanaged item preserved (also with --force)")
            return False
        if tree_hash(dest) != owned.get("sha256"):
            raise InstallError(f"{name}: manually edited item preserved; review/move it before reinstalling")
        if not self.args.force:
            self.record(name, "skip", message="Owned item unchanged")
            return False
        return True

    def replace_tree(self, name, stage, dest):
        """Move verified stage into place; keep old owned content as a recovery backup."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        staged_hash = tree_hash(stage)
        previous = self.manifest["components"].get(name)
        backup = previous_live = None
        if dest.exists() or dest.is_symlink():
            if not previous or previous.get("path") != str(dest) or tree_hash(dest) != previous.get("sha256"):
                raise InstallError("Destination changed before replacement; preserved: " + str(dest))
            backup = self.state_root / "backups" / (name + "-" + uuid.uuid4().hex[:10])
            backup.parent.mkdir(parents=True, exist_ok=True)
            if dest.is_dir():
                shutil.copytree(dest, backup, symlinks=True)
            else:
                shutil.copy2(dest, backup, follow_symlinks=False)
            if tree_hash(dest) != previous["sha256"] or tree_hash(backup) != previous["sha256"]:
                raise InstallError("Destination changed during backup; preserved: " + str(dest))
            # Keep the rollback rename on the destination filesystem, even with a
            # custom skills root on another mount. The recovery backup is durable.
            previous_live = dest.with_name(".ux-old-" + name + "-" + uuid.uuid4().hex[:10])
            os.replace(dest, previous_live)
        try:
            os.replace(stage, dest)
            self.save_component(name, {"path": str(dest), "sha256": staged_hash,
                                       "backup": str(backup) if backup else None, "version": VERSION})
        except BaseException:
            if previous is None:
                self.manifest["components"].pop(name, None)
            else:
                self.manifest["components"][name] = previous
            if dest.exists():
                shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
            if previous_live is not None and previous_live.exists():
                os.replace(previous_live, dest)
            raise
        if previous_live is not None:
            shutil.rmtree(previous_live) if previous_live.is_dir() else previous_live.unlink()
        self.record(name, "installed")

    def plugin_list(self):
        raw = self.cli_json(["codex", "plugin", "list", "--json"])
        items = raw.get("installed") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            raise InstallError("Unexpected plugin list format")
        return items

    def install_plugin(self, ref):
        name, market = ref.split("@")
        match = next((p for p in self.plugin_list()
                      if p.get("name") == name and
                      (p.get("marketplaceName") or p.get("marketplace_name")) == market and
                      p.get("installed", True)), None)
        if match and not match.get("enabled", True):
            raise InstallError(ref + ": installed but disabled; enable it intentionally in Codex")
        if match and (not self.args.force or not self.owned(ref)):
            self.record(ref, "skip", message="Existing plugin preserved")
            return
        if self.args.dry_run:
            self.record(ref, "planned", message="Native Codex add; never remove first")
            return
        # Native add supports updating/reapplying; there is no remove-then-add window.
        self.run(["codex", "plugin", "add", ref, "--json"])
        match = next((p for p in self.plugin_list()
                      if p.get("pluginId") == ref or
                      p.get("name") == name and p.get("marketplaceName") == market), None)
        if not match or not match.get("enabled", True):
            raise InstallError("Plugin post-install verification failed: " + ref)
        self.save_component(ref, {"plugin_ref": ref, "observed_version": match.get("version"),
                                  "version_policy": "Codex marketplace managed"})
        self.record(ref, "installed")

    def download_source(self, spec):
        url = f"https://codeload.github.com/{spec['repository']}/tar.gz/{spec['commit']}"
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read(50_000_001)
        if len(data) > 50_000_000:
            raise InstallError("Source archive exceeds size limit")
        files = {}
        total = 0
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for m in archive.getmembers():
                parts = Path(m.name).parts
                if ".." in parts or m.name.startswith("/"):
                    raise InstallError("Unsafe source archive member")
                rel = "/".join(parts[1:])
                selected = (rel.startswith(spec["directory"] + "/") or
                            "/" not in rel and (rel.startswith("LICENSE") or rel == "THIRD_PARTY_NOTICES.md") or
                            source_key_is_critique(spec) and rel.startswith("kb/"))
                if not selected:
                    continue
                if m.issym() or m.islnk() or m.isdev():
                    raise InstallError("Unsafe selected source archive member")
                if not m.isfile():
                    continue
                total += m.size
                if total > 150_000_000:
                    raise InstallError("Expanded source archive exceeds size limit")
                if len(parts) >= 2:
                    files["/".join(parts[1:])] = archive.extractfile(m).read()
        return files

    def install_remote_skill(self, name, source_key):
        dest = self.locate_skill(name)
        if not self.needs_tree(name, dest):
            return
        spec = self.sources[source_key]
        if self.args.dry_run:
            self.record(name, "planned", message=f"{spec['repository']}@{spec['commit']} -> {dest}")
            return
        files = self.download_source(spec)
        prefix = spec["directory"] + "/"
        if prefix + "SKILL.md" not in files:
            raise InstallError("Pinned source lacks SKILL.md")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".ux-stage-", dir=dest.parent) as tmp:
            stage = Path(tmp) / name
            stage.mkdir()
            for rel, content in files.items():
                target = None
                if rel.startswith(prefix):
                    target = rel[len(prefix):]
                elif Path(rel).parent == Path(".") and (
                        Path(rel).name.startswith("LICENSE") or rel == "THIRD_PARTY_NOTICES.md"):
                    target = Path(rel).name
                elif name == "ux-critique" and rel.startswith("kb/"):
                    target = rel
                if target:
                    p = stage / target
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(content)
            licenses = sorted(p.name for p in stage.iterdir() if p.name.startswith("LICENSE"))
            # Record absent upstream licenses rather than inventing one.
            (stage / "UPSTREAM_SOURCE.json").write_text(json.dumps({
                **spec, "license_files": licenses,
                "license_status": "provided" if licenses else "not_provided"
            }, indent=2) + "\n")
            if f"name: {name}" not in (stage / "SKILL.md").read_text():
                raise InstallError("Unexpected skill name in pinned source")
            self.replace_tree(name, stage, dest)
            self.manifest["components"][name]["source"] = spec
            write_json(self.manifest_path, self.manifest)

    def install_runtime(self):
        if not self.needs_tree("browser-runtime", self.runtime):
            return
        if self.args.dry_run:
            self.record("browser-runtime", "planned", message="npm ci with embedded lockfile; Chromium download")
            return
        with tempfile.TemporaryDirectory(prefix=".ux-runtime-", dir=self.state_root) as tmp:
            stage = Path(tmp) / "runtime"
            shutil.copytree(ROOT / "browser", stage)
            self.run(["npm", "ci", "--prefix", str(stage), "--ignore-scripts", "--no-audit", "--no-fund"], 600)
            versions = json.loads((stage / "package.json").read_text())["dependencies"]
            for package, expected in versions.items():
                package_json = stage / "node_modules" / package / "package.json"
                if not package_json.is_file() or json.loads(package_json.read_text()).get("version") != expected:
                    raise InstallError("Pinned browser runtime verification failed: " + package)
            if not self.args.no_browser_download:
                self.run(["node", str(stage / "node_modules/playwright/cli.js"), "install", "chromium"], 600)
            self.replace_tree("browser-runtime", stage, self.runtime)

    def design_source(self):
        spec = self.sources["design"]
        root = ROOT / spec["directory"]
        for name in spec["references"]:
            path = root / "references" / name
            if not path.is_file() or not path.read_text(encoding="utf-8").strip():
                raise InstallError("Missing/empty design reference: " + name)
        if not (root / "SKILL.md").is_file():
            raise InstallError("Bundled ooui-design lacks SKILL.md")
        return root, spec

    def install_design(self):
        dest = self.locate_skill("ooui-design")
        if not self.needs_tree("ooui-design", dest):
            return
        source, _ = self.design_source()
        if self.args.dry_run:
            self.record("ooui-design", "planned", message="Bundled OOUI skill and cognitive-load references -> " + str(dest))
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".ux-design-", dir=dest.parent) as tmp:
            stage = Path(tmp) / "ooui-design"
            shutil.copytree(source, stage, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
            self.replace_tree("ooui-design", stage, dest)

    def install_harness(self):
        dest = self.locate_skill("ux-gan-harness")
        if self.needs_tree("ux-gan-harness", dest):
            if self.args.dry_run:
                self.record("ux-gan-harness", "planned", message=str(dest))
            else:
                design, spec = self.design_source()
                dest.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix=".ux-harness-", dir=dest.parent) as tmp:
                    stage = Path(tmp) / "ux-gan-harness"
                    shutil.copytree(ROOT / "skill", stage,
                                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
                    references = stage / "references/design"
                    references.mkdir(parents=True)
                    for name in spec["references"]:
                        shutil.copy2(design / "references" / name, references / name)
                    (references / "index.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
                    (stage / "runtime.json").write_text(json.dumps({"runtime": str(self.runtime)}) + "\n")
                    for p in (stage / "scripts").iterdir():
                        p.chmod(0o755)
                    self.replace_tree("ux-gan-harness", stage, dest)
        script = dest / "scripts/gan-harness.sh"
        launcher = self.bin_dir / "ux-gan-harness"
        if not self.needs_tree("launcher", launcher):
            return
        if self.args.dry_run:
            self.record("launcher", "planned", message=f"{launcher} -> {script}")
            return
        if not script.is_file():
            raise InstallError("Existing harness has no Bash entry point; preserved it")
        launcher.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".ux-launcher-", dir=launcher.parent) as tmp:
            stage = Path(tmp) / "launcher"
            # Wrapper preserves BASH_SOURCE behavior (a direct symlink would not).
            quoted = "'" + str(script).replace("'", "'\"'\"'") + "'"
            stage.write_text("#!/usr/bin/env bash\nset -euo pipefail\nexec bash " + quoted + ' "$@"\n')
            stage.chmod(0o755)
            self.replace_tree("launcher", stage, launcher)

    def mcp_list(self):
        raw = self.cli_json(["codex", "mcp", "list", "--json"])
        items = raw.get("servers") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            raise InstallError("Unexpected MCP list format")
        return items

    def mcp_fingerprint(self, config):
        return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()

    def install_mcp(self):
        name = "playwright"
        existing = next((s for s in self.mcp_list() if s.get("name") == name), None)
        owned = self.owned("playwright-mcp")
        if existing:
            current = self.cli_json(["codex", "mcp", "get", name, "--json"])
            if not self.args.force or not owned or owned.get("sha256") != self.mcp_fingerprint(current):
                self.record("playwright-mcp", "skip", message="Existing MCP options preserved")
                return
        if self.args.dry_run:
            self.record("playwright-mcp", "planned", message="Register pinned local Node entry point")
            return
        executable = self.run(["node", "-p",
            "require(process.argv[1]).chromium.executablePath()",
            str(self.runtime / "node_modules/playwright")]).stdout.strip()
        if not executable:
            raise InstallError("Could not resolve pinned Chromium executable")
        self.run(["codex", "mcp", "add", name, "--", "node",
                  str(self.runtime / "node_modules/@playwright/mcp/cli.js"), "--headless", "--isolated",
                  "--executable-path", executable, "--caps", "vision", "--viewport-size", "1440,900"])
        current = self.cli_json(["codex", "mcp", "get", name, "--json"])
        self.save_component("playwright-mcp", {"sha256": self.mcp_fingerprint(current), "name": name})
        self.record("playwright-mcp", "installed")

    def inspect(self, launch=False):
        results = []
        for name, owned in self.manifest["components"].items():
            if "path" in owned:
                ok = tree_hash(Path(owned["path"])) == owned.get("sha256")
                results.append({"name": name, "ok": ok, "path": owned["path"]})
        for ref in PLUGINS:
            name, market = ref.split("@")
            ok = any(p.get("name") == name and p.get("marketplaceName") == market
                     and p.get("enabled", True) for p in self.plugin_list())
            results.append({"name": ref, "ok": ok})
        mcp = any(p.get("name") == "playwright" and p.get("enabled", True) for p in self.mcp_list())
        results.append({"name": "playwright-mcp", "ok": mcp})
        for name in ("web-design-guidelines", "ooui-design", "ux-gan-harness"):
            results.append({"name": name + "-skill",
                            "ok": (self.locate_skill(name) / "SKILL.md").is_file()})
        for skill, subdir in (("ooui-design", "references"), ("ux-gan-harness", "references/design")):
            root = self.locate_skill(skill) / subdir
            for name in self.sources["design"]["references"]:
                path = root / name
                try:
                    readable = path.is_file() and bool(path.read_text(encoding="utf-8").strip())
                except (OSError, UnicodeError):
                    readable = False
                results.append({"name": skill + "-" + name, "ok": readable})
        index = self.locate_skill("ux-gan-harness") / "references/design/index.json"
        try:
            compatible = json.loads(index.read_text()) == self.sources["design"]
        except (OSError, ValueError):
            compatible = False
        results.append({"name": "harness-design-index", "ok": compatible})
        harness = self.locate_skill("ux-gan-harness") / "scripts/gan-harness.sh"
        results.append({"name": "harness-entry", "ok": harness.is_file()})
        if launch and harness.is_file():
            r = subprocess.run(["bash", str(harness), "doctor"], env=self.env, capture_output=True, text=True, timeout=60)
            item = {"name": "harness-doctor", "ok": r.returncode == 0}
            with contextlib.suppress(ValueError):
                item["details"] = json.loads(r.stdout)
            results.append(item)
        yomiyasu = (self.locate_skill("yomiyasu") / "SKILL.md").is_file()
        recommendation = {"name": "yomiyasu", "available": yomiyasu,
                          "message": "日本語UI文言の確認に利用を推奨します。" if yomiyasu else
                          "日本語UIにはyomiyasuの利用を推奨します。別配布のinstall_codex_yomiyasu.sh --applyで導入できます。"}
        print(json.dumps({"version": VERSION, "ready": all(r["ok"] for r in results),
                          "checks": results, "recommendations": [recommendation]}, ensure_ascii=False, indent=2))
        return 0 if all(r["ok"] for r in results) else 1

    def uninstall(self):
        preserve_runtime = False
        components = list(self.manifest["components"].items())
        components.sort(key=lambda item: 0 if item[0] == "playwright-mcp" else
                        2 if item[0] == "browser-runtime" else 1)
        for name, owned in components:
            try:
                if name == "browser-runtime" and preserve_runtime:
                    raise InstallError("Runtime retained for a preserved/edited dependent item")
                if "path" in owned:
                    dest = Path(owned["path"])
                    if dest.exists() or dest.is_symlink():
                        if tree_hash(dest) != owned["sha256"]:
                            raise InstallError("Edited item preserved")
                        if self.args.dry_run:
                            self.record(name, "planned", message="Remove owned unchanged item")
                            continue
                        if dest.is_symlink() or dest.is_file():
                            dest.unlink()
                        else:
                            shutil.rmtree(dest)
                elif "plugin_ref" in owned:
                    if self.args.dry_run:
                        self.record(name, "planned", message="Remove plugin installed by this installer")
                        continue
                    self.run(["codex", "plugin", "remove", owned["plugin_ref"], "--json"])
                elif name == "playwright-mcp":
                    exists = any(s.get("name") == owned["name"] for s in self.mcp_list())
                    if exists:
                        cfg = self.cli_json(["codex", "mcp", "get", owned["name"], "--json"])
                        if self.mcp_fingerprint(cfg) != owned["sha256"]:
                            raise InstallError("Custom MCP configuration preserved")
                        if self.args.dry_run:
                            self.record(name, "planned", message="Remove owned MCP")
                            continue
                        self.run(["codex", "mcp", "remove", owned["name"]])
                del self.manifest["components"][name]
                self.record(name, "removed")
            except InstallError as e:
                self.failed = True
                if name in ("playwright-mcp", "ux-gan-harness", "launcher"):
                    preserve_runtime = True
                self.record(name, "failed", message=str(e))
        return 1 if self.failed else 0

    def apply(self):
        tasks = [(ref, lambda ref=ref: self.install_plugin(ref)) for ref in PLUGINS]
        tasks += [("ooui-design", self.install_design),
                  ("web-design-guidelines", lambda: self.install_remote_skill("web-design-guidelines", "guidelines")),
                  ("browser-runtime", self.install_runtime), ("ux-gan-harness", self.install_harness),
                  ("playwright-mcp", self.install_mcp)]
        if self.args.deep:
            tasks.append(("ux-critique", lambda: self.install_remote_skill("ux-critique", "critique")))
        runtime_failed = False
        for name, task in tasks:
            if name in ("ux-gan-harness", "playwright-mcp") and runtime_failed:
                self.record(name, "failed", message="Browser runtime failed; not registering broken paths")
                continue
            try:
                task()
            except (InstallError, OSError, ValueError, tarfile.TarError) as e:
                self.failed = True
                runtime_failed = runtime_failed or name == "browser-runtime"
                self.record(name, "failed", message=str(e))
        if self.failed:
            say("INCOMPLETE", "Some components failed; existing content is preserved. Re-run after resolving the cause.")
            return 1
        say("PLANNED" if self.args.dry_run else "COMPLETE",
            "No changes made" if self.args.dry_run else
            "Installation operations completed. Use --doctor to check actual browser readiness.")
        if not self.args.dry_run:
            say("USE", "$ooui-design で対象・画面・操作を設計し、既存のデザイン・実装スキルへ渡してください。")
            say("REVIEW", "$ux-gan-harness で実画面と操作を再確認できます。実在するgan-harness.shを実行してください。")
            say("COPY", "日本語UIの文言にはyomiyasuの利用を推奨します。未導入なら別配布のinstall_codex_yomiyasu.sh --applyを利用できます。")
            say("CLI", str(self.bin_dir / "ux-gan-harness") + " doctor")
            if str(self.bin_dir) not in os.environ.get("PATH", "").split(os.pathsep):
                say("PATH", "The launcher is outside PATH; use its absolute path or add the bin directory.")
        return 0


def parse(argv=None):
    p = argparse.ArgumentParser(description="Codex UX Stack: OOUI design, cognitive-load references and screenshot-first GAN harness")
    p.add_argument("--deep", action="store_true", help="Also install pinned ux-critique")
    p.add_argument("--force", action="store_true", help="Reapply owned unchanged items; preserve custom/unmanaged items")
    p.add_argument("--dry-run", action="store_true", help="Show changes without installation/downloads")
    modes = p.add_mutually_exclusive_group()
    modes.add_argument("--doctor", action="store_true", help="Inspect installed items and launch Chromium on a blank page")
    modes.add_argument("--status", action="store_true", help="Inspect installed items without launching a browser")
    modes.add_argument("--uninstall", action="store_true", help="Remove only owned unchanged items")
    modes.add_argument("--extract", type=Path, help="Extract embedded sources without installing")
    p.add_argument("--codex-home")
    p.add_argument("--skills-root")
    p.add_argument("--bin-dir")
    p.add_argument("--no-browser-download", action="store_true", help="Skip Chromium download; readiness remains separately verified")
    return p.parse_args(argv)


def main(argv=None):
    if sys.version_info < (3, 10):
        raise InstallError("Python 3.10+ is required")
    args = parse(argv)
    if args.extract:
        dest = args.extract.absolute()
        if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
            raise InstallError("--extract requires an unused or empty directory")
        if dest.is_symlink():
            raise InstallError("Refusing a symlink extraction directory")
        shutil.copytree(ROOT, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        say("EXTRACTED", str(dest))
        return 0
    installer = Installer(args)
    installer.preflight()
    if args.doctor or args.status:
        return installer.inspect(launch=args.doctor)
    if args.dry_run:
        return installer.uninstall() if args.uninstall else installer.apply()
    installer.state_root.mkdir(parents=True, exist_ok=True)
    with (installer.state_root / ".install.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise InstallError("Another UX Stack installer is running") from e
        if installer.manifest_path.exists():
            installer.manifest = json.loads(installer.manifest_path.read_text())
        return installer.uninstall() if args.uninstall else installer.apply()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (InstallError, OSError, ValueError, subprocess.TimeoutExpired) as e:
        say("ERROR", str(e))
        sys.exit(1)
