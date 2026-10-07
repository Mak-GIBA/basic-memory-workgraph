import contextlib
import importlib.util
import io
import json
import errno
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/codex-ux-stack"
spec = importlib.util.spec_from_file_location("ux_installer", SOURCE / "install_ux_stack.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
DOWNLOAD_SOURCE = mod.Installer.download_source

CODEX = r'''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
a=sys.argv[1:];root=Path(os.environ["CODEX_HOME"]);path=root/"mock.json"
s=json.loads(path.read_text()) if path.exists() else {"installed":[],"servers":[],"calls":[]}
if "--help" in a:print("--json --output-schema --output-last-message --sandbox");sys.exit(0)
if "sandbox" in a:sys.exit(0)
mutated=False
if a[:2]==["plugin","list"]:print(json.dumps({"installed":s["installed"],"available":[]}))
elif a[:2]==["plugin","add"]:
 if os.getenv("UX_MOCK_FAIL_PLUGIN")=="1":sys.exit(9)
 ref=a[2];name,market=ref.split("@")
 s["installed"]=[p for p in s["installed"] if p["pluginId"]!=ref]
 s["installed"].append({"name":name,"pluginId":ref,"marketplaceName":market,"enabled":True,"installed":True,"version":"fixture-1"})
 mutated=True;print("{}")
elif a[:2]==["plugin","remove"]:
 s["installed"]=[p for p in s["installed"] if p["pluginId"]!=a[2]];mutated=True;print("{}")
elif a[:2]==["mcp","list"]:print(json.dumps(s["servers"]))
elif a[:2]==["mcp","get"]:
 p=next((p for p in s["servers"] if p["name"]==a[2]),None)
 if p is None:sys.exit(1)
 print(json.dumps(p))
elif a[:2]==["mcp","add"]:
 name=a[2];i=a.index("--");cmd=a[i+1:]
 s["servers"]=[p for p in s["servers"] if p["name"]!=name]
 s["servers"].append({"name":name,"enabled":True,"transport":{"type":"stdio","command":cmd[0],"args":cmd[1:]}})
 mutated=True;print("{}")
elif a[:2]==["mcp","remove"]:
 s["servers"]=[p for p in s["servers"] if p["name"]!=a[2]];mutated=True;print("{}")
else:sys.exit(2)
if mutated:
 s["calls"].append(a);root.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(s))
'''
NODE = r'''#!/usr/bin/env python3
import json,sys
if "-p" in sys.argv:print("20.20.0" if sys.argv[-1]=="process.versions.node" else "/fixture/chrome")
elif "--smoke" in sys.argv:print(json.dumps({"ready":True,"png_bytes":100,"version":"1.63.0"}))
'''
NPM = r'''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
if os.environ.get("UX_MOCK_FAIL_NPM")=="1":sys.exit(6)
a=sys.argv[1:];p=Path(a[a.index("--prefix")+1])
for name in ["playwright","@playwright/mcp"]:
 d=p/"node_modules"/name;d.mkdir(parents=True,exist_ok=True)
 (d/"package.json").write_text(json.dumps({"version":"1.63.0" if name=="playwright" else "0.0.83"}));(d/"cli.js").write_text("")
'''


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        self.home=self.base/"home with spaces";self.home.mkdir()
        self.bin=self.base/"mock-bin";self.bin.mkdir()
        for name,text in [("codex",CODEX),("node",NODE),("npm",NPM)]:
            p=self.bin/name;p.write_text(text);p.chmod(0o755)
        self.env=patch.dict(os.environ,{"HOME":str(self.home),
            "CODEX_HOME":str(self.home/".codex"),
            "PATH":str(self.bin)+os.pathsep+os.environ["PATH"],
            "UX_MOCK_FAIL_NPM":"","UX_MOCK_FAIL_PLUGIN":""})
        self.env.start()
        self.download=patch.object(mod.Installer,"download_source",self.source_files)
        self.download.start()

    def tearDown(self):
        self.download.stop();self.env.stop();self.tmp.cleanup()

    @staticmethod
    def source_files(installer,spec):
        name=spec["directory"].split("/")[-1]
        result={spec["directory"]+"/SKILL.md":("---\nname: "+name+"\ndescription: Example skill\n---\n").encode(),
                "LICENSE":b"Example license"}
        if name=="ux-critique":
            result["kb/example.md"]=b"Example reference"
        return result

    def invoke(self,*argv):
        with contextlib.redirect_stdout(io.StringIO()):
            return mod.main(list(argv))

    def manifest(self):
        return json.loads((self.home/".codex/ux-stack/manifest.json").read_text())

    def mock_state(self):
        return json.loads((self.home/".codex/mock.json").read_text())

    def status(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = mod.main(["--status", *args])
        return code, json.loads(output.getvalue())

    def test_dry_run_writes_nothing_and_does_not_fetch(self):
        before=set(self.home.rglob("*"))
        with patch.object(mod.Installer,"download_source",side_effect=AssertionError("downloaded")):
            self.assertEqual(self.invoke("--dry-run","--deep"),0)
        self.assertEqual(before,set(self.home.rglob("*")))

    def test_install_idempotent_and_launcher_calls_bash_from_any_cwd(self):
        self.assertEqual(self.invoke("--deep"),0)
        manifest=self.manifest()
        self.assertIn("ux-gan-harness",manifest["components"])
        self.assertEqual(self.invoke("--deep"),0)
        self.assertEqual(len(self.mock_state()["calls"]),3)
        self.assertTrue((self.home/".agents/skills/ux-critique/kb/example.md").exists())
        r=subprocess.run(["bash",str(self.home/".local/bin/ux-gan-harness"),"--version"],
                         cwd=self.base,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(r.stdout.strip(),"1.1.0")

    def test_standard_design_and_harness_use_same_references_without_optional_skills(self):
        self.assertEqual(self.invoke(),0)
        components = self.manifest()["components"]
        self.assertIn("ooui-design",components)
        self.assertNotIn("ux-critique",components)
        self.assertNotIn("yomiyasu",components)
        self.assertEqual({p["pluginId"] for p in self.mock_state()["installed"]},set(mod.PLUGINS))
        spec = json.loads((SOURCE/"sources.json").read_text())["design"]
        design = self.home/".agents/skills/ooui-design"
        bundled = self.home/".agents/skills/ux-gan-harness/references/design"
        for name in spec["references"]:
            expected = (SOURCE/"ooui-design/references"/name).read_bytes()
            self.assertEqual((design/"references"/name).read_bytes(),expected)
            self.assertEqual((bundled/name).read_bytes(),expected)
        self.assertEqual(json.loads((bundled/"index.json").read_text()),spec)
        code, status = self.status()
        self.assertEqual(code,0)
        self.assertTrue(status["ready"])
        self.assertFalse(status["recommendations"][0]["available"])
        self.assertFalse((self.home/".agents/skills/yomiyasu").exists())

    def test_design_user_edits_survive_force_and_uninstall(self):
        self.assertEqual(self.invoke(),0)
        path = self.home/".agents/skills/ooui-design/references/cognitive-load.md"
        edited = path.read_text()+"\nUser-specific guidance\n"
        path.write_text(edited)
        self.assertEqual(self.invoke("--force"),1)
        self.assertEqual(path.read_text(),edited)
        self.assertEqual(self.invoke("--uninstall"),1)
        self.assertEqual(path.read_text(),edited)

    def test_custom_root_preserves_existing_design_and_finds_recommended_yomiyasu(self):
        design = self.home/".agents/skills/ooui-design"
        design.mkdir(parents=True);(design/"SKILL.md").write_text("User OOUI skill")
        yomiyasu = self.home/".agents/skills/yomiyasu"
        yomiyasu.mkdir();(yomiyasu/"SKILL.md").write_text("User writing skill")
        custom = self.base/"custom skills"
        args = ("--skills-root",str(custom))
        self.assertEqual(self.invoke("--force",*args),0)
        self.assertNotIn("ooui-design",self.manifest()["components"])
        self.assertFalse((custom/"ooui-design").exists())
        self.assertEqual((design/"SKILL.md").read_text(),"User OOUI skill")
        code, status = self.status(*args)
        self.assertEqual(code,1)  # Unmanaged skill has none of the required references.
        self.assertTrue(status["recommendations"][0]["available"])
        self.assertEqual(self.invoke("--uninstall",*args),0)
        self.assertTrue(design.exists())
        self.assertTrue(yomiyasu.exists())

    def test_legacy_harness_requires_force_to_add_its_own_guidance(self):
        self.assertEqual(self.invoke(),0)
        harness = self.home/".agents/skills/ux-gan-harness"
        shutil.rmtree(harness/"references/design")
        shutil.rmtree(self.home/".agents/skills/ooui-design")
        manifest = self.manifest()
        del manifest["components"]["ooui-design"]
        manifest["version"] = "1.0.0"
        manifest["components"]["ux-gan-harness"].update(version="1.0.0",sha256=mod.tree_hash(harness))
        mod.write_json(self.home/".codex/ux-stack/manifest.json",manifest)
        old_hash = mod.tree_hash(harness)
        self.assertEqual(self.invoke(),0)
        self.assertTrue((self.home/".agents/skills/ooui-design/SKILL.md").is_file())
        self.assertEqual(mod.tree_hash(harness),old_hash)
        self.assertEqual(self.status()[0],1)
        self.assertEqual(self.invoke("--force"),0)
        self.assertEqual(self.status()[0],0)
        self.assertEqual(self.manifest()["components"]["ux-gan-harness"]["version"],"1.1.0")
        backups = self.home/".codex/ux-stack/backups"
        self.assertTrue(any(mod.tree_hash(p)==old_hash for p in backups.glob("ux-gan-harness-*")))

    def test_status_reports_missing_empty_and_invalid_utf8_references(self):
        self.assertEqual(self.invoke(),0)
        for skill, subdir in (("ooui-design","references"),("ux-gan-harness","references/design")):
            path = self.home/".agents/skills"/skill/subdir/"cognitive-load.md"
            original = path.read_bytes()
            for replacement in (None,b" \n",b"\xff"):
                with self.subTest(skill=skill,replacement=replacement):
                    if replacement is None:path.unlink()
                    else:path.write_bytes(replacement)
                    code, status = self.status()
                    self.assertEqual(code,1)
                    check = next(c for c in status["checks"] if c["name"]==skill+"-cognitive-load.md")
                    self.assertFalse(check["ok"])
                    path.write_bytes(original)
        index = self.home/".agents/skills/ux-gan-harness/references/design/index.json"
        index.write_text("invalid JSON")
        self.assertEqual(self.status()[0],1)

    def test_installed_harness_uses_own_bundle_without_sibling_design_skill(self):
        self.assertEqual(self.invoke(),0)
        harness = self.home/".agents/skills/ux-gan-harness"
        module_spec = importlib.util.spec_from_file_location("installed_ux_harness",harness/"scripts/harness.py")
        installed = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(installed)
        before = installed.design_guidance()
        shutil.rmtree(self.home/".agents/skills/ooui-design")
        self.assertEqual(installed.design_guidance(),before)
        self.assertEqual(before["version"],"1.1.0")
        for ref in before["references"]:
            self.assertTrue(Path(ref["path"]).is_relative_to(harness))
            self.assertEqual(ref["sha256"],mod.sha(Path(ref["path"])))
        # A sibling core skill must not mask a broken installed harness bundle.
        shutil.copytree(SOURCE/"ooui-design",self.home/".agents/skills/ooui-design")
        (harness/"references/design/review-policy.md").unlink()
        with self.assertRaises(installed.Blocked):installed.design_guidance()

    def test_force_keeps_custom_mcp_options(self):
        self.assertEqual(self.invoke(),0)
        path=self.home/".codex/mock.json";state=json.loads(path.read_text())
        state["servers"][0]["transport"]["args"]=["--custom-browser-url","http://localhost:9222"]
        path.write_text(json.dumps(state))
        self.assertEqual(self.invoke("--force"),0)
        self.assertEqual(self.mock_state()["servers"][0]["transport"]["args"],
                         ["--custom-browser-url","http://localhost:9222"])
        self.assertNotIn("remove",[a[1] for a in self.mock_state()["calls"]])

    def test_force_does_not_reenable_an_intentionally_disabled_plugin(self):
        self.assertEqual(self.invoke(),0)
        path=self.home/".codex/mock.json";state=json.loads(path.read_text())
        state["installed"][0]["enabled"]=False
        path.write_text(json.dumps(state))
        self.assertEqual(self.invoke("--force"),1)
        self.assertFalse(self.mock_state()["installed"][0]["enabled"])

    def test_force_preserves_edited_skill_and_reports_failure(self):
        self.assertEqual(self.invoke(),0)
        p=self.home/".agents/skills/ux-gan-harness/SKILL.md"
        p.write_text("User edits")
        self.assertEqual(self.invoke("--force"),1)
        self.assertEqual(p.read_text(),"User edits")

    def test_existing_legacy_skill_not_duplicated_or_removed(self):
        p=self.home/".codex/skills/web-design-guidelines"
        p.mkdir(parents=True);(p/"SKILL.md").write_text("legacy content")
        self.assertEqual(self.invoke("--force"),0)
        self.assertFalse((self.home/".agents/skills/web-design-guidelines").exists())
        self.assertEqual((p/"SKILL.md").read_text(),"legacy content")
        self.assertNotIn("web-design-guidelines",self.manifest()["components"])

    def test_partial_failure_never_registers_missing_runtime(self):
        os.environ["UX_MOCK_FAIL_NPM"]="1"
        self.assertEqual(self.invoke(),1)
        self.assertFalse((self.home/".local/bin/ux-gan-harness").exists())
        self.assertTrue((self.home/".agents/skills/ooui-design").exists())
        self.assertFalse(self.mock_state()["servers"])
        self.assertNotIn("browser-runtime",self.manifest()["components"])
        os.environ["UX_MOCK_FAIL_NPM"]=""
        self.assertEqual(self.invoke(),0)

    def test_staging_failure_keeps_old_runtime(self):
        self.assertEqual(self.invoke(),0)
        old=self.manifest()["components"]["browser-runtime"]["sha256"]
        os.environ["UX_MOCK_FAIL_NPM"]="1"
        self.assertEqual(self.invoke("--force"),1)
        self.assertEqual(mod.tree_hash(self.home/".codex/ux-stack/runtime"),old)

    def test_marketplace_identity_is_not_substring_match(self):
        root=self.home/".codex";root.mkdir()
        (root/"mock.json").write_text(json.dumps({"installed":[{"pluginId":"product-design@other",
            "name":"product-design","marketplaceName":"other","enabled":True}],"servers":[],"calls":[]}))
        self.assertEqual(self.invoke(),0)
        self.assertEqual(len(self.mock_state()["installed"]),3)

    def test_uninstall_owned_only_preserves_unmanaged_items(self):
        foreign=self.home/".agents/skills/web-design-guidelines";foreign.mkdir(parents=True)
        (foreign/"SKILL.md").write_text("user skill")
        self.assertEqual(self.invoke(),0)
        self.assertEqual(self.invoke("--uninstall"),0)
        self.assertTrue(foreign.exists())
        self.assertFalse((self.home/".agents/skills/ooui-design").exists())
        self.assertFalse((self.home/".local/bin/ux-gan-harness").exists())
        self.assertFalse(self.mock_state()["servers"])
        self.assertFalse(self.mock_state()["installed"])

    def test_status_and_doctor_do_not_mutate_installation(self):
        self.assertEqual(self.invoke(),0)
        before=(self.home/".codex/ux-stack/manifest.json").read_bytes()
        self.assertEqual(self.invoke("--status"),0)
        self.assertEqual(self.invoke("--doctor"),0)
        self.assertEqual((self.home/".codex/ux-stack/manifest.json").read_bytes(),before)

    def test_failed_replace_restores_old_owned_content(self):
        self.assertEqual(self.invoke(),0)
        args=mod.parse([])
        ins=mod.Installer(args)
        dest=self.home/".agents/skills/ux-gan-harness"
        old=mod.tree_hash(dest)
        stage=self.base/"stage";stage.mkdir();(stage/"new").write_text("new")
        with patch.object(ins,"save_component",side_effect=OSError("manifest failure")):
            with self.assertRaises(OSError):ins.replace_tree("ux-gan-harness",stage,dest)
        self.assertEqual(mod.tree_hash(dest),old)
        self.assertEqual(ins.manifest["components"],self.manifest()["components"])

    def test_pinned_source_without_license_is_recorded_without_inventing_one(self):
        files={"skills/web-design-guidelines/SKILL.md":b"---\nname: web-design-guidelines\n---\n"}
        with patch.object(mod.Installer,"download_source",return_value=files):
            self.assertEqual(self.invoke(),0)
        dest=self.home/".agents/skills/web-design-guidelines"
        self.assertFalse((dest/"LICENSE").exists())
        self.assertEqual(json.loads((dest/"UPSTREAM_SOURCE.json").read_text())["license_status"],"not_provided")

    def test_archive_ignores_unrelated_symlinks_but_rejects_selected_symlinks(self):
        ins=mod.Installer(mod.parse([]));spec=ins.sources["guidelines"]
        def archive(link_name):
            buf=io.BytesIO()
            with tarfile.open(fileobj=buf,mode="w:gz") as tar:
                contents=b"---\nname: web-design-guidelines\n---\n"
                item=tarfile.TarInfo("root/skills/web-design-guidelines/SKILL.md")
                item.size=len(contents);tar.addfile(item,io.BytesIO(contents))
                item=tarfile.TarInfo(link_name);item.type=tarfile.SYMTYPE;item.linkname="/outside"
                tar.addfile(item)
            return io.BytesIO(buf.getvalue())
        with patch.object(mod.urllib.request,"urlopen",return_value=archive("root/CLAUDE.md")):
            self.assertIn("skills/web-design-guidelines/SKILL.md",DOWNLOAD_SOURCE(ins,spec))
        with patch.object(mod.urllib.request,"urlopen",return_value=archive("root/skills/web-design-guidelines/link")):
            with self.assertRaises(mod.InstallError):DOWNLOAD_SOURCE(ins,spec)

    def test_force_replacement_does_not_rename_skills_across_filesystems(self):
        self.assertEqual(self.invoke(),0)
        original=mod.os.replace
        skills=self.home/".agents/skills";state_root=self.home/".codex/ux-stack"
        def checked(src,dst):
            if Path(src).parent==skills and Path(dst).is_relative_to(state_root):
                raise OSError(errno.EXDEV,"Cross-device link")
            return original(src,dst)
        with patch.object(mod.os,"replace",side_effect=checked):
            self.assertEqual(self.invoke("--force"),0)
        self.assertFalse(list(skills.glob(".ux-old-*")))
        self.assertTrue(list((state_root/"backups").glob("ux-gan-harness-*")))

    def test_uninstall_retains_runtime_for_edited_mcp(self):
        self.assertEqual(self.invoke(),0)
        path=self.home/".codex/mock.json";state=json.loads(path.read_text())
        state["servers"][0]["transport"]["args"].append("--user-option")
        path.write_text(json.dumps(state))
        self.assertEqual(self.invoke("--uninstall"),1)
        self.assertTrue((self.home/".codex/ux-stack/runtime").exists())
        self.assertTrue(self.mock_state()["servers"])

    def test_single_file_bundle_matches_sources_and_works_away_from_repo(self):
        installer=self.base/"installer.sh"
        installer.write_bytes((ROOT/"install_codex_ux_stack.sh").read_bytes())
        dest=self.base/"extracted"
        r=subprocess.run(["bash",str(installer),"--extract",str(dest)],
                         cwd=self.base,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        expected = {Path("install_ux_stack.py"),Path("sources.json")}
        expected.update(p.relative_to(SOURCE) for folder in ("skill","browser","ooui-design")
                        for p in (SOURCE/folder).rglob("*")
                        if p.is_file() and "__pycache__" not in p.parts and "node_modules" not in p.parts)
        actual = {p.relative_to(dest) for p in dest.rglob("*") if p.is_file()}
        self.assertEqual(expected,actual)
        for rel in expected:
            self.assertEqual((SOURCE/rel).read_bytes(),(dest/rel).read_bytes())
        r=subprocess.run(["bash",str(installer),"--help"],cwd=self.base,capture_output=True,text=True)
        self.assertEqual(r.returncode,0)
        self.assertIn("--dry-run",r.stdout)


if __name__=="__main__":
    unittest.main()
