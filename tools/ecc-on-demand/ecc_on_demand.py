#!/usr/bin/env python3
"""Keep native ECC installed, exposing four small on-demand skill entrypoints.

Python 3.11+, standard library only. Native Codex owns ECC's cache and updates.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shlex
import subprocess
import sys
import tempfile
import time
import tomllib

OWNER = "basic-memory-workgraph/ecc-on-demand"
PLUGIN = "ecc@ecc"
ENTRIES = {
    "ecc-python": "python-patterns",
    "ecc-errors": "error-handling",
    "ecc-security": "security-review",
    "ecc-library": None,
}
MANAGER_DIR = "ecc-on-demand"
MCP_SERVERS = {
    "context7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp@4.3.0"], "startup_timeout_sec": 60},
    "parallel-search": {"url": "https://search.parallel.ai/mcp", "startup_timeout_sec": 60},
    "playwright": {"command": "npx", "args": ["-y", "@playwright/mcp@0.0.83", "--headless", "--isolated"], "startup_timeout_sec": 60},
    "chrome-devtools": {"command": "npx", "args": ["-y", "chrome-devtools-mcp@1.10.1", "--headless", "--isolated", "--no-usage-statistics", "--no-performance-crux"], "startup_timeout_sec": 60},
    # Retain legacy names for ownership validation/restoration and explicit use.
    "sequential-thinking": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-sequential-thinking@2026.8.31"], "env": {"DISABLE_THOUGHT_LOGGING": "true"}, "startup_timeout_sec": 60},
    "cloudflare-docs": {"url": "https://docs.mcp.cloudflare.com/mcp", "startup_timeout_sec": 60},
}
RECOMMENDED_MCPS = ("context7", "playwright")
MCP_PRESETS = {
    "recommended": RECOMMENDED_MCPS,
    "research": ("context7", "parallel-search"),
    "browser": ("playwright", "chrome-devtools"),
    "cloudflare": ("context7", "cloudflare-docs"),
    "none": (),
}


def mcp_selection(value) -> tuple[str, ...]:
    """Validate selections before any native command or configuration mutation."""
    names = value.split(",") if isinstance(value, str) else value
    if not isinstance(names, (list, tuple)) or any(not isinstance(n, str) or not n.strip() for n in names):
        raise ManagementError("MCP selection must contain names/presets separated by commas")
    names = [n.strip() for n in names]
    if "none" in names and len(names) != 1:
        raise ManagementError("MCP preset none cannot be combined with other selections")
    result = []
    for name in names:
        if name in MCP_PRESETS:
            result.extend(MCP_PRESETS[name])
        elif name in MCP_SERVERS:
            result.append(name)
        else:
            raise ManagementError(f"Unknown MCP selection: {name}; available: {', '.join(MCP_PRESETS)}; {', '.join(MCP_SERVERS)}")
    return tuple(dict.fromkeys(result))


def check_mcps(text: str, owned: dict) -> None:
    servers = tomllib.loads(text).get("mcp_servers", {})
    for name, record in owned.items():
        if (name not in MCP_SERVERS or text.count(record["block"]) != 1
                or servers.get(name) != record["config"]):
            raise ManagementError(f"Managed MCP changed; preserving it: {name}")


def add_mcps(text: str, owned: dict, selected=RECOMMENDED_MCPS) -> tuple[str, dict, dict]:
    """Append missing servers; preserve existing commands, credentials and opt-outs."""
    check_mcps(text, owned)
    servers = tomllib.loads(text).get("mcp_servers", {})
    selected = mcp_selection(selected)
    records = dict(owned)
    report = {name: "managed_retained" for name in owned if name not in selected}
    for name in selected:
        config = MCP_SERVERS[name]
        # Older Context7 names must not create a second connection.
        alias = "context7-mcp" if name == "context7" else name
        if name in servers or alias in servers:
            existing = servers.get(name, servers.get(alias))
            report[name] = "managed" if name in owned else "existing_disabled" if existing.get("enabled") is False else "existing_preserved"
            continue
        block = f'\n# {OWNER}:mcp:{name}:begin\n[mcp_servers.{name}]\n'
        for key, value in config.items():
            literal = ('{ ' + ', '.join(f'{json.dumps(k)} = {json.dumps(v)}' for k, v in value.items()) + ' }'
                       if isinstance(value, dict) else json.dumps(value))
            block += f'{key} = {literal}\n'
        block += f'# {OWNER}:mcp:{name}:end\n'
        text += block
        records[name] = {"block": block, "config": config}
        report[name] = "added"
    check_mcps(text, records)
    return text, records, report


class ManagementError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".ecc-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def config_value(text: str) -> bool | None:
    value = tomllib.loads(text).get("plugins", {}).get(PLUGIN, {}).get("enabled")
    if value is not None and not isinstance(value, bool):
        raise ManagementError("ECC enabled must be a TOML boolean")
    return value


def table_path(header: str) -> tuple[str, ...] | None:
    """Use TOML itself to decode quoted table names; never split on dots."""
    if not header.lstrip().startswith("[") or header.lstrip().startswith("[["):
        return None
    try:
        tree = tomllib.loads(header + "\n__ecc_table_probe__ = true\n")
    except tomllib.TOMLDecodeError:
        return None
    parts = []
    while isinstance(tree, dict) and "__ecc_table_probe__" not in tree:
        if len(tree) != 1:
            return None
        key, tree = next(iter(tree.items()))
        parts.append(key)
    return tuple(parts)


def edit_enabled(text: str, value: bool | None) -> str:
    """Change one canonical plugin table without reserializing other settings.

    Inline/dotted plugin declarations are deliberately rejected before mutation.
    This avoids ambiguous edits or silently damaging unrelated TOML.
    """
    parsed = tomllib.loads(text)
    lines = text.splitlines(keepends=True)
    start = end = None
    for index, line in enumerate(lines):
        if re.match(r"^\s*\[", line):
            if start is not None:
                end = index
                break
            if table_path(line.rstrip("\r\n")) == ("plugins", PLUGIN):
                start = index
    if start is None:
        if PLUGIN in parsed.get("plugins", {}):
            raise ManagementError('Use a [plugins."ecc@ecc"] table; inline/dotted declarations are unsupported')
        if value is None:
            return text
        suffix = "" if not text or text.endswith("\n") else "\n"
        return text + suffix + f'\n[plugins."{PLUGIN}"]\nenabled = {str(value).lower()}\n'
    end = len(lines) if end is None else end
    key = re.compile(r'^(\s*(?:enabled|"enabled"|\'enabled\')\s*=\s*)(true|false)(\s*(?:#.*)?)(\r?\n)?$')
    for index in range(start + 1, end):
        match = key.match(lines[index])
        if match:
            if value is None:
                del lines[index]
            else:
                lines[index] = match[1] + str(value).lower() + match[3] + (match[4] or "")
            break
    else:
        if parsed.get("plugins", {}).get(PLUGIN, {}).get("enabled") is not None:
            raise ManagementError("Cannot safely locate ECC enabled assignment")
        if value is not None:
            if not lines[start].endswith("\n"):
                lines[start] += "\n"
            lines.insert(start + 1, f"enabled = {str(value).lower()}\n")
    result = "".join(lines)
    if config_value(result) != value:
        raise ManagementError("ECC configuration edit failed validation")
    before = parsed.get("plugins", {}).get(PLUGIN, {}).copy()
    after = tomllib.loads(result).get("plugins", {}).get(PLUGIN, {}).copy()
    before.pop("enabled", None)
    after.pop("enabled", None)
    parsed.get("plugins", {}).pop(PLUGIN, None)
    remaining = tomllib.loads(result)
    remaining.get("plugins", {}).pop(PLUGIN, None)
    # A newly created parent table may be empty after removing this plugin.
    if not parsed.get("plugins"):
        parsed.pop("plugins", None)
    if not remaining.get("plugins"):
        remaining.pop("plugins", None)
    if parsed != remaining or before != after:
        raise ManagementError("ECC configuration edit changed unrelated settings")
    return result


class Codex:
    def __init__(self, binary: str, home: Path, timeout: float = 30):
        self.binary, self.timeout = binary, timeout
        self.env = {**os.environ, "CODEX_HOME": str(home)}

    def skills(self, cwd: Path, enable_ecc: bool = False) -> dict:
        command = [self.binary]
        if enable_ecc:
            # CLI override keys are unquoted; quoted dotted CLI keys don't work.
            command += ["-c", "plugins.ecc@ecc.enabled=true"]
        command += ["app-server", "--stdio"]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, env=self.env, bufsize=0)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        buffer = b""

        def send(message):
            process.stdin.write((json.dumps(message) + "\n").encode())
            process.stdin.flush()

        def response(request_id):
            nonlocal buffer
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    try:
                        message = json.loads(line)
                    except ValueError:
                        continue
                    if message.get("id") == request_id:
                        if "error" in message:
                            raise ManagementError(f"Codex RPC failed: {message['error']}")
                        return message["result"]
                if selector.select(min(0.2, max(0, deadline - time.monotonic()))):
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        raise ManagementError("Codex app-server exited before responding")
                    buffer += chunk
            raise ManagementError("Codex app-server skills/list timed out")

        try:
            send({"id": 1, "method": "initialize", "params": {
                "clientInfo": {"name": "ecc-on-demand", "version": "1.0.0"},
                "capabilities": {"experimentalApi": True}}})
            response(1)
            send({"method": "initialized"})
            send({"id": 2, "method": "skills/list", "params": {
                "cwds": [str(cwd)], "forceReload": True}})
            rows = response(2).get("data", [])
            if len(rows) != 1:
                raise ManagementError("Unexpected Codex skills/list response")
            return rows[0]
        finally:
            selector.close()
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdin.close()
            process.stdout.close()

    def update(self) -> None:
        for arguments in (["plugin", "marketplace", "upgrade", "ecc", "--json"],
                          ["plugin", "add", PLUGIN, "--json"]):
            # Only the native lifecycle writes original plugin/cache files.
            result = subprocess.run([self.binary, *arguments], env=self.env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, timeout=180)
            if result.returncode:
                raise ManagementError(f"Native ECC update failed ({result.returncode}): {result.stderr.strip()}")


def catalog(codex: Codex, cwd: Path) -> list[dict]:
    row = codex.skills(cwd, enable_ecc=True)
    skills = []
    for skill in row.get("skills", []):
        if skill.get("pluginId") != PLUGIN:
            continue
        path = Path(skill["path"]).resolve()
        root = next((parent for parent in path.parents
                     if (parent / ".codex-plugin/plugin.json").is_file()), None)
        if not path.is_file() or root is None:
            raise ManagementError(f"ECC original is missing or has no native manifest: {path}")
        manifest = json.loads((root / ".codex-plugin/plugin.json").read_text())
        if manifest.get("name") != "ecc":
            raise ManagementError(f"Unexpected plugin manifest: {root}")
        skills.append({"name": skill["name"].removeprefix("ecc:"),
                       "description": skill.get("description", ""),
                       "path": str(path), "skill_dir": str(path.parent),
                       "plugin_root": str(root), "version": manifest.get("version"),
                       "plugin_id": PLUGIN})
    if not skills:
        raise ManagementError(f"Native ECC catalog unavailable; skills/list errors: {row.get('errors', [])}")
    required = {name for name in ENTRIES.values() if name}
    missing = required - {skill["name"] for skill in skills}
    if missing:
        raise ManagementError(f"ECC originals missing: {', '.join(sorted(missing))}")
    return skills


SEARCH_TERMS = {
    "python": ["python", "パイソン"],
    "testing": ["test", "tests", "testing", "テスト", "pytest", "vitest"],
    "api": ["api", "エンドポイント", "rest"],
    "database": ["db", "database", "データベース"],
    "migrations": ["migration", "migrations", "移行", "マイグレーション"],
    "docker": ["docker", "コンテナ", "compose"],
    "security": ["security", "セキュリティ", "認証", "秘密情報"],
    "error": ["error", "errors", "エラー", "例外", "再試行"],
    "e2e": ["e2e", "playwright", "ブラウザーテスト"],
}


def search_catalog(skills: list[dict], query: str, cwd: Path, limit: int = 5) -> list[dict]:
    normalized = query.casefold()
    explicit = [s for s in skills if s["name"] == normalized.removeprefix("ecc:")]
    if explicit:
        return explicit
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    for term, aliases in SEARCH_TERMS.items():
        if any((alias in normalized if not alias.isascii() else alias in tokens) for alias in aliases):
            tokens.add(term)
            tokens.difference_update(alias for alias in aliases if alias.isascii() and alias != term)
    stack = set()
    if any((cwd / file).is_file() for file in ("pyproject.toml", "requirements.txt", "setup.py")):
        stack.add("python")
    if (cwd / "tsconfig.json").is_file():
        stack.add("typescript")
    if (cwd / "package.json").is_file():
        stack.add("javascript")
    results = []
    languages = {"python", "typescript", "javascript", "golang", "rust", "ruby",
                 "java", "kotlin", "swift", "csharp", "fsharp", "php", "dart", "perl"}
    for skill in skills:
        name_tokens = set(re.findall(r"[a-z0-9]+", skill["name"].casefold()))
        if tokens & languages and name_tokens & languages and not tokens & name_tokens & languages:
            continue
        description_tokens = set(re.findall(r"[a-z0-9]+", skill["description"].casefold()))
        score = 8 * len(tokens & name_tokens) + len(tokens & description_tokens)
        if score:
            score += 2 * len(stack & name_tokens)
            results.append({**skill, "score": score})
    return sorted(results, key=lambda s: (-s["score"], s["name"]))[:limit]


class Manager:
    def __init__(self, home: Path, skills_root: Path, codex: Codex, cwd: Path):
        self.home, self.skills_root, self.codex, self.cwd = home, skills_root, codex, cwd
        self.directory = home / MANAGER_DIR
        self.config = (home / "config.toml").resolve()
        self.state_path = self.directory / "state.json"
        self.installed_script = self.directory / "ecc_on_demand.py"

    @contextmanager
    def lock(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / ".lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def state(self) -> dict | None:
        if not self.state_path.exists():
            return None
        state = json.loads(self.state_path.read_text())
        if state.get("owner") != OWNER or state.get("version") != 1:
            raise ManagementError("Unknown ECC manager state; refusing to modify it")
        if state["config_path"] != str(self.config) or state["skills_root"] != str(self.skills_root):
            raise ManagementError("ECC manager state belongs to different config/skill paths")
        allowed = {str(self.installed_script)} | {
            str(self.skills_root / name / relative)
            for name in ENTRIES for relative in ("SKILL.md", "agents/openai.yaml")}
        if set(state["files"]) != allowed:
            raise ManagementError("Unexpected managed file paths in state")
        return state

    def check_files(self, state: dict) -> None:
        for filename, expected in state["files"].items():
            path = Path(filename)
            if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != expected:
                raise ManagementError(f"Managed file missing or changed; preserving it: {path}")

    def payload(self) -> dict[Path, bytes]:
        source = Path(__file__).resolve()
        template_root = source.parent / "skills"
        if not template_root.is_dir():
            # Installed manager already owns its entrypoints; it can re-apply
            # configuration. Upgrading wrapper templates uses the repo copy.
            state = self.state()
            if state is None:
                raise ManagementError("Run apply from the repository copy first")
            self.check_files(state)
            return {Path(path): Path(path).read_bytes() for path in state["files"]}
        files = {self.installed_script: source.read_bytes()}
        for name in ENTRIES:
            for relative in ("SKILL.md", "agents/openai.yaml"):
                text = (template_root / name / relative).read_text()
                command = (shlex.quote(str(self.installed_script))
                           + " --codex-home " + shlex.quote(str(self.home))
                           + " --codex " + shlex.quote(self.codex.binary))
                text = text.replace("{{MANAGER}}", command)
                files[self.skills_root / name / relative] = text.encode()
        return files

    def preflight(self) -> dict | None:
        """Check local ownership/configuration without starting Codex or writing."""
        state = self.state()
        self.payload()
        if state:
            self.check_files(state)
        else:
            for name in ENTRIES:
                path = self.skills_root / name
                if path.exists() or path.is_symlink():
                    raise ManagementError(f"Existing unmanaged skill; refusing to overwrite: {path}")
            if self.installed_script.exists() or self.installed_script.is_symlink():
                raise ManagementError("Existing unmanaged ECC manager script")
        text = self.config.read_text() if self.config.exists() else ""
        edit_enabled(text, False)
        check_mcps(text, state.get("mcps", {}) if state else {})
        return state

    def selected_mcps(self, requested=None) -> tuple[str, ...]:
        if requested is None:
            requested = (self.state() or {}).get("selected_mcps", RECOMMENDED_MCPS)
        return mcp_selection(requested)

    def apply(self, baseline: dict | None = None, *, _locked: bool = False, mcps=None) -> dict:
        selected = self.selected_mcps(mcps)
        originals = catalog(self.codex, self.cwd)
        with nullcontext() if _locked else self.lock():
            state = self.preflight()
            files = self.payload()
            original = self.config.read_bytes() if self.config.exists() else b""
            changed_text = edit_enabled(original.decode(), False)
            selected = self.selected_mcps(mcps)
            changed_text, records, mcp_report = add_mcps(changed_text, state.get("mcps", {}) if state else {}, selected)
            changed = changed_text.encode()
            state = state or {"owner": OWNER, "version": 1,
                              "config_path": str(self.config), "skills_root": str(self.skills_root),
                              "previous_enabled": baseline["previous_enabled"] if baseline else config_value(original.decode()),
                              "backup": baseline["backup"] if baseline else str(self.directory / f"config.before-ecc-on-demand.{time.time_ns()}.toml")}
            new_state = {**state, "codex_binary": self.codex.binary,
                         "mcps": records, "selected_mcps": list(selected),
                         "files": {str(path): digest(data) for path, data in files.items()}}
            writes = dict(files)
            if not self.state_path.exists():
                writes[Path(state["backup"])] = Path(baseline["backup"]).read_bytes() if baseline else original
            writes[self.config] = changed
            writes[self.state_path] = (json.dumps(new_state, indent=2) + "\n").encode()
            snapshots = {path: (path.read_bytes(), path.stat().st_mode & 0o777)
                         if path.exists() else None for path in writes}
            new_directories = set()
            for path in writes:
                parent = path.parent
                while not parent.exists():
                    new_directories.add(parent)
                    parent = parent.parent
            touched = []
            try:
                for path, data in writes.items():
                    if path.exists() and path.read_bytes() == data:
                        continue
                    atomic_write(path, data, snapshots[path][1] if snapshots[path] else 0o600)
                    touched.append(path)
            except BaseException:
                for path in reversed(touched):
                    snapshot = snapshots[path]
                    if snapshot:
                        atomic_write(path, *snapshot)
                    else:
                        path.unlink(missing_ok=True)
                for directory in sorted(new_directories, key=lambda p: len(p.parts), reverse=True):
                    if directory.exists():
                        directory.rmdir()
                raise
        return {"status": "applied", "original_skills": len(originals),
                "mcps": mcp_report, "selected_mcps": list(selected),
                "mcp_selection_scope": "add_missing_only; existing connections and opt-outs preserved",
                "entrypoints": list(ENTRIES), "backup": state["backup"],
                "changed_files": len(touched), "new_session_required": True}

    def doctor(self) -> dict:
        issues = []
        state = self.state()
        if state is None:
            issues.append("ECC on-demand has not been applied")
        else:
            try:
                self.check_files(state)
            except ManagementError as error:
                issues.append(str(error))
        config = self.config.read_text() if self.config.exists() else ""
        try:
            check_mcps(config, state.get("mcps", {}) if state else {})
        except ManagementError as error:
            issues.append(str(error))
        servers = tomllib.loads(config).get("mcp_servers", {})
        mcp_report = {name: "configured" if servers.get(name, {}).get("enabled", True) and name in servers
                      else "disabled" if name in servers else "not_configured" for name in MCP_SERVERS}
        if "context7" not in servers and "context7-mcp" in servers:
            mcp_report["context7"] = "configured_legacy_alias" if servers["context7-mcp"].get("enabled", True) else "disabled"
        if config_value(config) is not False:
            issues.append("ECC native plugin is enabled or lacks an explicit false setting; run apply")
        row = self.codex.skills(self.cwd)
        active = [s for s in row.get("skills", []) if s.get("enabled", True)]
        active_ecc = [s for s in active if s.get("pluginId") == PLUGIN]
        if active_ecc:
            issues.append(f"ECC native skills still active: {len(active_ecc)}")
        for name in ENTRIES:
            expected = str(self.skills_root / name / "SKILL.md")
            if not any(s["name"] == name and s["path"] == expected for s in active):
                issues.append(f"On-demand entrypoint unavailable: {name}")
        if row.get("errors"):
            issues.append(f"skills/list errors: {row['errors']}")
        originals = []
        try:
            originals = catalog(self.codex, self.cwd)
        except ManagementError as error:
            issues.append(str(error))
        return {"status": "ready" if not issues else "needs_attention", "issues": issues,
                "mcps": mcp_report, "mcp_verification": "configuration_only; startup and credentials not tested",
                "selected_mcps": list(self.selected_mcps()), "recommended_mcps": list(RECOMMENDED_MCPS),
                "active_skills": len(active), "active_native_ecc_skills": len(active_ecc),
                "available_original_skills": len(originals),
                "original_versions": sorted({s["version"] for s in originals if s["version"]}),
                "yomiyasu_available": any(s["name"] == "yomiyasu" for s in active),
                "github_project_director_available": any(s["name"] == "github-project-director" for s in active),
                "catalog_errors": row.get("errors", []), "new_session_required": True}

    def update(self) -> dict:
        with self.lock():
            state = self.state()
            if state is None:
                raise ManagementError("Run apply before update")
            self.check_files(state)
            failure = None
            try:
                self.codex.update()
            except (ManagementError, subprocess.TimeoutExpired, OSError) as error:
                failure = str(error)
            finally:
                # Native plugin add can enable ECC even after a partial failure.
                text = self.config.read_text()
                updated = edit_enabled(text, False).encode()
                if updated != text.encode():
                    atomic_write(self.config, updated, self.config.stat().st_mode & 0o777)
        report = self.doctor()
        report["native_update"] = "failed" if failure else "completed"
        if failure:
            report["status"] = "needs_attention"
            report["issues"].append(failure)
        return report

    def restore(self) -> dict:
        with self.lock():
            state = self.state()
            if state is None:
                return {"status": "already_restored"}
            self.check_files(state)
            for name in ENTRIES:
                root = self.skills_root / name
                expected = {root / "SKILL.md", root / "agents", root / "agents/openai.yaml"}
                extras = [p for p in root.rglob("*") if p not in expected]
                if extras:
                    raise ManagementError(f"Unexpected files in managed skill; preserving them: {extras}")
            text = self.config.read_text()
            check_mcps(text, state.get("mcps", {}))
            if config_value(text) is not False:
                raise ManagementError("ECC setting changed after apply; run apply before restore")
            check_mcps(text, state.get("mcps", {}))
            restored = edit_enabled(text, state["previous_enabled"]).encode()
            for record in state.get("mcps", {}).values():
                restored = restored.replace(record["block"].encode(), b"", 1)
            paths = [self.config, self.state_path, *(Path(name) for name in state["files"])]
            snapshots = {path: (path.read_bytes(), path.stat().st_mode & 0o777) for path in paths}
            try:
                for filename in state["files"]:
                    Path(filename).unlink()
                for name in ENTRIES:
                    (self.skills_root / name / "agents").rmdir()
                    (self.skills_root / name).rmdir()
                atomic_write(self.config, restored, snapshots[self.config][1])
                self.state_path.unlink()
            except BaseException:
                # Recover the complete installed state even if one unlink fails
                # after other entrypoints have already been removed.
                for path, (data, mode) in snapshots.items():
                    if not path.exists() or path.read_bytes() != data:
                        atomic_write(path, data, mode)
                raise
        return {"status": "restored", "ecc_enabled": state["previous_enabled"],
                "backup_retained": state["backup"], "new_session_required": True}


def main(argv=None) -> int:
    installed_defaults = {}
    adjacent_state = Path(__file__).resolve().parent / "state.json"
    if adjacent_state.is_file():
        try:
            candidate = json.loads(adjacent_state.read_text())
            if candidate.get("owner") == OWNER:
                installed_defaults = candidate
        except (ValueError, OSError):
            pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path,
                        default=Path(os.environ.get("CODEX_HOME", str(adjacent_state.parent.parent)
                                     if installed_defaults else str(Path.home() / ".codex"))))
    parser.add_argument("--skills-root", type=Path,
                        default=Path(installed_defaults.get("skills_root", Path.home() / ".agents/skills")))
    parser.add_argument("--codex", default=installed_defaults.get("codex_binary", "codex"))
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("apply", "doctor", "update", "restore", "search", "resolve"):
        sub = subcommands.add_parser(name)
        sub.add_argument("--json", action="store_true")
        if name == "apply":
            sub.add_argument("--mcps", help="追加するMCPのプリセット/名前をカンマ区切りで選択。未指定は前回の選択、初回はrecommended")
        if name == "search":
            sub.add_argument("query")
            sub.add_argument("--limit", type=int, choices=range(1, 6), default=5)
        if name == "resolve":
            sub.add_argument("name")
    args = parser.parse_args(argv)
    try:
        home = args.codex_home.expanduser().resolve()
        skills_root = args.skills_root.expanduser().resolve()
        cwd = args.cwd.expanduser().resolve()
        codex = Codex(args.codex, home)
        manager = Manager(home, skills_root, codex, cwd)
        if args.command in ("search", "resolve"):
            skills = catalog(codex, cwd)
            if args.command == "search":
                result = {"matches": search_catalog(skills, args.query, cwd, args.limit)}
            else:
                matches = [s for s in skills if s["name"] == args.name.removeprefix("ecc:")]
                if len(matches) != 1:
                    raise ManagementError(f"ECC skill not found or ambiguous: {args.name}; use search")
                result = matches[0]
        elif args.command == "apply":
            result = manager.apply(mcps=args.mcps)
        else:
            result = getattr(manager, args.command)()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "resolve":
            print(result["path"])
        elif args.command == "search":
            for skill in result["matches"]:
                print(f"{skill['name']}\t{skill['description']}\n  {skill['path']}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("status") == "needs_attention" else 0
    except (ManagementError, OSError, ValueError, KeyError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
