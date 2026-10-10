#!/usr/bin/env python3
"""Install native ECC and configure its four on-demand entrypoints."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse

from ecc_on_demand import (OWNER, PLUGIN, ENTRIES, MCP_SERVERS, MCP_PRESETS, RECOMMENDED_MCPS, MCP_SELECTION_BASIS, Codex, Manager, ManagementError,
                           atomic_write, config_value, digest, edit_enabled)

SOURCE = "affaan-m/ECC"
JOURNAL = "bootstrap.json"


def official_source(source: dict) -> bool:
    if source.get("sourceType") != "git":
        return False
    value = str(source.get("source", "")).strip()
    if value.casefold() == SOURCE.casefold():
        return True
    if value.startswith("git@github.com:"):
        value = "https://github.com/" + value.split(":", 1)[1]
    url = urlparse(value)
    return (url.hostname == "github.com" and url.scheme in ("https", "ssh")
            and url.path.rstrip("/").removesuffix(".git").casefold() == "/affaan-m/ecc")


class Installer:
    def __init__(self, manager: Manager, mcps=None):
        self.manager = manager
        self.mcps = mcps
        self.codex = manager.codex
        self.journal_path = manager.directory / JOURNAL

    def native(self, *arguments: str) -> dict:
        command = [self.codex.binary, *arguments]
        try:
            result = subprocess.run(command, env=self.codex.env, text=True,
                                    capture_output=True, timeout=180)
        except subprocess.TimeoutExpired as error:
            raise ManagementError(f"Codex command timed out: {' '.join(arguments)}") from error
        if result.returncode:
            raise ManagementError(f"Codex {' '.join(arguments)} failed ({result.returncode}): {result.stderr.strip()}")
        try:
            value = json.loads(result.stdout)
        except ValueError as error:
            raise ManagementError(f"Codex {' '.join(arguments)} returned invalid JSON") from error
        if not isinstance(value, dict):
            raise ManagementError("Unexpected Codex JSON response")
        return value

    def marketplace(self, entries: list[dict]) -> dict | None:
        matches = [entry for entry in entries if entry.get("name") == "ecc"]
        if len(matches) > 1:
            raise ManagementError("Multiple ECC marketplaces; refusing to replace them")
        if matches and not official_source(matches[0].get("marketplaceSource", {})):
            raise ManagementError("Marketplace name ecc is occupied by another source; preserving it")
        return matches[0] if matches else None

    @staticmethod
    def plugin(entries: list[dict], *, required: bool = False) -> dict | None:
        matches = [entry for entry in entries if entry.get("pluginId") == PLUGIN]
        if len(matches) > 1:
            raise ManagementError("Ambiguous native ECC plugin catalog")
        if not matches:
            if required:
                raise ManagementError("ecc@ecc is absent from Codex's catalog; inspect codex plugin list --available --json")
            return None
        plugin = matches[0]
        if plugin.get("name") != "ecc" or plugin.get("marketplaceName") != "ecc":
            raise ManagementError("Unexpected ECC plugin name/marketplace")
        source = plugin.get("marketplaceSource")
        if source is not None and not official_source(source):
            raise ManagementError("Installed ECC reports an unexpected marketplace source")
        return plugin

    def baseline(self, installed: bool) -> dict:
        manager = self.manager
        if self.journal_path.is_file():
            journal = json.loads(self.journal_path.read_text())
            backup = Path(journal.get("backup", ""))
            if (journal.get("owner") != OWNER or journal.get("version") != 1
                    or journal.get("config_path") != str(manager.config)
                    or journal.get("skills_root") != str(manager.skills_root)
                    or backup.parent != manager.directory
                    or not backup.name.startswith("config.before-ecc-on-demand.")
                    or backup.is_symlink() or not backup.is_file()
                    or digest(backup.read_bytes()) != journal.get("backup_sha256")
                    or (journal.get("previous_enabled") is not None
                        and not isinstance(journal["previous_enabled"], bool))):
                raise ManagementError("Invalid ECC bootstrap recovery state; preserving it")
            return journal
        original = manager.config.read_bytes() if manager.config.exists() else b""
        backup = manager.directory / f"config.before-ecc-on-demand.{time.time_ns()}.toml"
        journal = {"owner": OWNER, "version": 1, "config_path": str(manager.config),
                   "skills_root": str(manager.skills_root), "backup": str(backup),
                   "backup_sha256": digest(original), "ecc_previously_installed": installed,
                   # Fresh ECC remains disabled on restore; its native cache is retained.
                   "previous_enabled": config_value(original.decode()) if installed else False}
        atomic_write(backup, original)
        atomic_write(self.journal_path, (json.dumps(journal, indent=2) + "\n").encode())
        return journal

    def disable(self) -> None:
        manager = self.manager
        text = manager.config.read_text() if manager.config.exists() else ""
        changed = edit_enabled(text, False).encode()
        if changed != text.encode():
            atomic_write(manager.config, changed,
                         manager.config.stat().st_mode & 0o777 if manager.config.exists() else 0o600)

    def preview(self, action: str) -> dict:
        # Do not start native Codex here: even catalog commands may fetch remote
        # metadata. This preview is based solely on local owned state/config.
        state = self.manager.preflight()
        if action == "update" and state is None:
            raise ManagementError("Run --apply before --update")
        if self.journal_path.exists() and state is None:
            # Validate the existing journal without creating one.
            self.baseline(installed=False)
        steps = {
            "install": ["Inspect native ECC marketplace and plugin inventory",
                        "Register affaan-m/ECC if absent; install ecc@ecc if absent",
                        "Disable native ECC and install/update four entrypoints",
                        "Add missing selected MCPs; preserve existing connections and disabled settings", "Run doctor"],
            "update": ["Refresh the ECC marketplace and native plugin", "Keep ECC disabled",
                       "Update managed CLI/entrypoints and add missing selected MCPs; run doctor"],
            "restore": ["Restore managed ECC setting and remove owned CLI/entrypoints and unchanged owned MCPs; keep native cache"],
        }
        return {"status": "planned", "action": action, "steps": steps[action],
                "codex_home": str(self.manager.home), "skills_root": str(self.manager.skills_root),
                "entrypoints": list(ENTRIES), "native_inventory": "not_queried_in_offline_preview",
                "recommended_mcps": list(RECOMMENDED_MCPS),
                "selected_mcps": list(self.manager.selected_mcps(self.mcps)),
                "mcp_presets": {name: list(names) for name, names in MCP_PRESETS.items()},
                "available_mcps": list(MCP_SERVERS),
                "mcp_selection_scope": "add_missing_only; existing connections and opt-outs preserved",
                "mcp_selection_basis": {name: MCP_SELECTION_BASIS[name] for name in self.manager.selected_mcps(self.mcps)},
                "mcp_assessment": "docs/codex-ecc/mcp-workflow-evaluation.md; task-specific utility, not proven general accuracy improvement",
                "managed_installation": state is not None}

    def install(self, *, update: bool = False) -> dict:
        manager = self.manager
        manager.preflight()
        manager.selected_mcps(self.mcps)
        failure = None
        applied = None
        with manager.lock():
            state = manager.preflight()
            if update and state is None:
                raise ManagementError("Run --apply before --update")
            market = self.marketplace(self.native("plugin", "marketplace", "list", "--json").get("marketplaces", []))
            existing = self.plugin(self.native("plugin", "list", "--json").get("installed", []))
            installed = existing is not None and existing.get("installed") is True
            baseline = None if state else self.baseline(installed)
            try:
                self.disable()
                if market is None:
                    self.native("plugin", "marketplace", "add", SOURCE, "--json")
                    market = self.marketplace(self.native("plugin", "marketplace", "list", "--json").get("marketplaces", []))
                    if market is None:
                        raise ManagementError("Codex did not register the official ECC marketplace")
                if update:
                    self.native("plugin", "marketplace", "upgrade", "ecc", "--json")
                if update or not installed:
                    available = self.native("plugin", "list", "--available", "--json")
                    plugin = self.plugin(available.get("available", []) + available.get("installed", []), required=True)
                    if plugin.get("installPolicy") not in ("AVAILABLE", "INSTALLED_BY_DEFAULT"):
                        raise ManagementError("ECC's catalog policy does not permit installation")
                    try:
                        self.native("plugin", "add", PLUGIN, "--json")
                    finally:
                        # Native add may enable ECC, including on partial failure.
                        self.disable()
                    verified = self.plugin(self.native("plugin", "list", "--json").get("installed", []), required=True)
                    if verified.get("installed") is not True:
                        raise ManagementError("Codex did not report ECC installed after plugin add")
                applied = manager.apply(baseline, _locked=True, mcps=self.mcps)
            except (ManagementError, OSError, ValueError, KeyError) as error:
                failure = str(error)
            finally:
                try:
                    self.disable()
                except (ManagementError, OSError, ValueError) as error:
                    failure = f"{failure + '; ' if failure else ''}Failed to disable ECC: {error}"
        if failure:
            try:
                disabled = config_value(manager.config.read_text()) is False
            except (OSError, ValueError):
                disabled = False
            return {"status": "error", "error": failure,
                    "backup": state["backup"] if state else baseline["backup"],
                    "recovery": "Fix the reported cause and rerun --apply (or --update --apply)",
                    "ecc_disabled": disabled}
        report = manager.doctor()
        report.update({"action": "updated" if update else "configured", "apply": applied})
        if report["status"] == "ready":
            self.journal_path.unlink(missing_ok=True)
        return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="実際に導入・更新・復元する")
    mode.add_argument("--dry-run", action="store_true", help="予定表示のみ（既定・通信なし）")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--doctor", action="store_true", help="導入と原本の取得を診断する")
    actions.add_argument("--update", action="store_true", help="ECCと管理資材を更新する")
    actions.add_argument("--restore", action="store_true", help="管理した設定と入口を復元する")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--mcps", help="追加するMCPのプリセット/名前をカンマ区切りで選択。初回はrecommended、再適用・更新は前回の選択")
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))))
    parser.add_argument("--skills-root", type=Path, default=Path.home() / ".agents/skills")
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    if args.doctor and args.apply:
        parser.error("--doctor is read-only and cannot be combined with --apply")
    if args.mcps is not None and (args.doctor or args.restore):
        parser.error("--mcps is only available for install/update, not doctor/restore")
    try:
        if not sys.platform.startswith("linux"):
            raise ManagementError("This installer supports Linux / WSL2")
        for name in (args.codex, "git"):
            if shutil.which(name) is None:
                raise ManagementError(f"Required command unavailable: {name}")
        if os.sep in args.codex:
            args.codex = os.path.abspath(args.codex)
        home, root, cwd = (path.expanduser().resolve() for path in (args.codex_home, args.skills_root, args.cwd))
        if not cwd.is_dir():
            raise ManagementError(f"Working directory is unavailable: {cwd}")
        manager = Manager(home, root, Codex(args.codex, home), cwd)
        installer = Installer(manager, mcps=args.mcps)
        if args.doctor:
            report = manager.doctor()
        elif not args.apply:
            report = installer.preview("restore" if args.restore else "update" if args.update else "install")
        elif args.restore:
            if manager.state() is None and installer.journal_path.exists():
                raise ManagementError("Incomplete ECC bootstrap; fix the reported cause and rerun --apply before restore")
            report = manager.restore()
            installer.journal_path.unlink(missing_ok=True)
        else:
            report = installer.install(update=args.update)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not args.json and report.get("new_session_required"):
            print("新しいCodexセッションで反映を確認してください。")
        return 1 if report.get("status") in ("error", "needs_attention") else 0
    except (ManagementError, OSError, ValueError, KeyError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
