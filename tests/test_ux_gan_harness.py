import contextlib
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "tools/codex-ux-stack/skill/scripts"
spec = importlib.util.spec_from_file_location("ux_harness", SCRIPTS / "harness.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def png(width=1440, height=900):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag+data)&0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress((b"\0" + b"\xff\xff\xff"*width)*height)) + chunk(b"IEND", b""))


FAKE_CODEX = r'''#!/usr/bin/env python3
import os,sys,json,hashlib,struct,zlib
from pathlib import Path
args=sys.argv[1:]
if args[:2]==["exec","--help"]:
 print("--json --output-schema --output-last-message --sandbox");sys.exit(0)
if args[:2]==["plugin","list"]:
 print('{"installed":[]}');sys.exit(0)
if args[:2]==["mcp","list"]:
 print('[]');sys.exit(0)
if "sandbox" in args:sys.exit(0)
prompt=args[-1]; data=json.loads(prompt.split("\nINPUT:\n",1)[1])
role=prompt.split("\nROLE: ",1)[1].splitlines()[0]
output=Path(args[args.index("--output-last-message")+1])
(output.parent/"fixture-argv.json").write_text(json.dumps(args))
directory=Path(data["screenshots_directory"]);directory.mkdir(parents=True,exist_ok=True)
project=Path(data["project"]);case=os.getenv("UX_FAKE_CASE","")
iteration=int(output.parent.name.split("-")[0])
evidence=[]
def png(w,h):
 def chunk(t,d):return struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
 return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",w,h,8,2,0,0,0))+chunk(b"IDAT",zlib.compress((b"\0"+b"\xff\xff\xff"*w)*h))+chunk(b"IEND",b"")
def frame(id,w=1440,hh=900,source="live",url=None):
 p=directory/(id+".png");p.write_bytes(png(w,hh))
 url=url or data["url"]
 meta={"kind":"frame","id":id,"path":str(p),"url":url,"source":source,"viewport":{"width":w,"height":hh},"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"captured_at":"2026-10-04T00:00:00Z"}
 with (directory/"browser-receipts.jsonl").open("a") as f:f.write(json.dumps(meta)+"\n")
 e={"id":id,"path":str(p),"screen_id":"top","flow_id":"create","description":"saved screen","target":"main button","url":url,"source":source,"viewport":{"width":w,"height":hh}}
 evidence.append(e);return id
common={"reason":"","browser_backend":data["browser_backend"],"fallback_reason":data["fallback_reason"],"evidence":evidence}
if case=="invalid_json":
 output.write_text("not json");sys.exit(0)
if role=="planner":
 for id,w,hh in [("d",1440,900),("t",768,1024),("m",390,844)]:frame(id,w,hh)
 result={**common,"status":"ready","first_impression":{k:"Initial visual observation" for k in ["purpose","next_action","primary_cta","unknown_terms","hesitations"]},
 "screens":[{"id":"top","name":"投稿作成","url":data["url"]}],
 "flows":[{"id":"create","name":"投稿を保存","steps":["開く","入力","保存"],"required":True,"states":["normal"]}],"test_commands":["python3 -c 'assert True'"]}
elif role=="references":
 apps=[]
 for n in range(3):
  url=f"https://reference{n}.example/"
  id=frame("ref"+str(n),source="official_reference",url=url)
  apps.append({"name":"Example "+str(n),"url":url,"checked_at":"2026-10-04","observation_kind":"official_screenshot","evidence_ids":[id],"patterns":[{"pattern":"clear save label","why":"predictable","application":"replace Go","avoid":"do not add panels"}],"limitations":"mocked reference"})
 result={**common,"status":"ready","apps":apps}
 if case=="references_unavailable":
  for app in apps:app.update(observation_kind="unavailable",evidence_ids=[],patterns=[])
  result.update(status="partial",reason="参考画像にアクセスできません",evidence=[])
elif role=="fixer":
 if case=="pending_review":
  (Path(os.environ["UX_FAKE_BIN"])/"fail_next").write_text("1")
 p=project/"app.html";p.write_text(p.read_text().replace(">Go<",">投稿を保存<"))
 if case=="unexpected":(project/"unexpected.txt").write_text("unexpected")
 result={"status":"changed","reason":"","fixed_issue_ids":["Issue 01"],"changed_files":["app.html"],"changes":[{"issue_ids":["Issue 01"],"description":"clear label","simplicity_reason":"replaced existing label, no controls added"}],"tests":[]}
else:
 marker=Path(os.environ["UX_FAKE_BIN"])/"fail_next"
 if marker.exists():
  marker.unlink();sys.exit(1)
 coverage=[]
 for id,v,w,hh in [("d","desktop",1440,900),("t","tablet",768,1024),("m","mobile",390,844)]:
  before=frame(id+"b",w,hh);after=frame(id+"a",w,hh)
  coverage.append({"flow_id":"create","viewport":v,"state":"normal","perspective":"first_time","result":"passed","notes":"fixture flow","steps":[{"action":"click save","before_evidence_id":before,"after_evidence_id":after,"result":"saved"}]})
 for perspective in ["mistake","hurried","skips_explanation"]:
  coverage.append({**coverage[0],"perspective":perspective})
 resolved=iteration>0 and case!="plateau"
 issues=[{"id":"Issue 01","title":"保存ボタンの意味が分からない","severity":"High","screen_id":"top","flow_id":"create","root_cause":"ambiguous_save","action":"保存しようとした","problem":"Goでは結果を予測できない","confusion":"何が起きるか不安","why":"主要操作","improvement":"既存のラベルを投稿を保存に置換","evidence_ids":["db"],"status":"resolved" if resolved else "open","verified_after_ids":["da"] if resolved else []}]
 if case=="root_groups":
  for n,cause in [(2,"second_cause"),(3,"ambiguous_save"),(4,"third_cause"),(5,"fourth_cause")]:
   issues.append({**issues[0],"id":f"Issue {n:02d}","root_cause":cause})
 if case=="drop_issue" and iteration>0:issues=[]
 if case=="bad_coverage":coverage[0]["steps"][0]["after_evidence_id"]="missing"
 if case=="wrong_viewport":coverage[0]["viewport"]="mobile"
 result={**common,"status":"reviewed","issues":issues,"coverage":coverage,
 "screen_reviews":[{"screen_id":"top",**{k:"Observed visually" for k in ["purpose","information","cta","interaction","copy","visibility","consistency"]}}],
 "friction":[],"copy_issues":[{"current":"Go","problem":"曖昧","suggested":"投稿を保存"}] if not resolved else [],
 "consistency":[],"responsive":[],"simplicity":{"primary_action":"保存","step_count":2,"decision_points":1,"mobile_density":"low","regressed":case=="clutter" and iteration>0,"change_rationale":"same number of controls","evidence_ids":["ma"]},"second_pass_complete":True}
 if case=="source_during_review":(project/"app.html").write_text("unexpected reviewer edit")
if case=="missing_image":
 for e in evidence:Path(e["path"]).unlink()
output.write_text(json.dumps(result,ensure_ascii=False))
print(json.dumps({"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":10}}))
'''


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.project = self.base / "app with spaces"
        self.project.mkdir()
        (self.project / "app.html").write_text("<button>Go</button>")
        self.bin = self.base / "bin"
        self.bin.mkdir()
        (self.bin / "codex").write_text(FAKE_CODEX)
        (self.bin / "codex").chmod(0o755)
        self.env = patch.dict(os.environ, {"PATH": str(self.bin)+os.pathsep+os.environ["PATH"],
                                         "UX_FAKE_BIN":str(self.bin), "UX_FAKE_CASE":""})
        self.env.start()
        self.smoke = patch.object(h, "browser_smoke", return_value={"ready": True})
        self.smoke.start()
        self.ready = patch.object(h, "wait_ready")
        self.ready.start()
        self.http = patch.object(h.urllib.request, "urlopen", side_effect=OSError("offline test"))
        self.http.start()

    def tearDown(self):
        self.http.stop()
        self.ready.stop()
        self.smoke.stop()
        self.env.stop()
        self.tmp.cleanup()

    def invoke(self, mode="run", *extra):
        argv = [mode, "--project", str(self.project)]
        if mode != "resume":
            argv += ["--url", "http://localhost:3000", "--browser", "local-playwright",
                     "--phase-timeout", "20"]
        argv += list(extra)
        with contextlib.redirect_stdout(io.StringIO()):
            return h.main(argv)

    def state(self):
        folders = sorted((self.project / "artifacts/ux-gan").glob("*/state.json"))
        self.assertEqual(len(folders), 1)
        return json.loads(folders[0].read_text()), folders[0].parent

    def test_full_fix_loop_has_before_after_and_no_git_init(self):
        self.assertEqual(self.invoke(), 0)
        state, folder = self.state()
        self.assertEqual(state["status"], "passed")
        self.assertEqual(state["iteration"], 1)
        self.assertIn("投稿を保存", (self.project/"app.html").read_text())
        self.assertFalse((self.project/".git").exists())
        self.assertTrue((folder/"000-reviewer/evidence.json").exists())
        report=(self.project/"docs/ui-ux-fix-report.md").read_text()
        self.assertIn("変更前:", report)
        self.assertIn("変更後", report)
        self.assertGreaterEqual(report.count("!["), 2)
        self.assertTrue((self.project/"docs/ui-ux-reference-apps.md").is_file())

    def test_audit_preserves_source_and_archives_existing_report_images(self):
        docs=self.project/"docs"
        docs.mkdir()
        image=docs/"old.png"
        image.write_bytes(png())
        (docs/"ui-ux-review.md").write_text("Original\n[old](old.png)\n")
        before=h.fingerprint(self.project)
        self.assertEqual(self.invoke("audit"), 0)
        self.assertEqual(before,h.fingerprint(self.project))
        state,folder=self.state()
        self.assertEqual(state["status"],"reviewed")
        saved=Path(state["input_review"])
        self.assertIn("Original",saved.read_text())
        self.assertTrue(list((folder/"input/images").glob("*.png")))
        self.assertIn("Severity:** High",(docs/"ui-ux-review.md").read_text())

    def test_missing_images_never_pass(self):
        os.environ["UX_FAKE_CASE"]="missing_image"
        self.assertEqual(self.invoke(),1)
        self.assertEqual(self.state()[0]["status"],"blocked")

    def test_audit_still_reports_target_when_references_are_unavailable(self):
        os.environ["UX_FAKE_CASE"]="references_unavailable"
        self.assertEqual(self.invoke("audit"),0)
        state,_=self.state()
        self.assertEqual(state["references"]["status"],"partial")
        self.assertIn("未完了",state["reason"])
        self.assertTrue((self.project/"docs/ui-ux-review.md").is_file())

    def test_malformed_json_never_pass(self):
        os.environ["UX_FAKE_CASE"]="invalid_json"
        self.assertEqual(self.invoke(),1)
        self.assertEqual(self.state()[0]["status"],"blocked")

    def test_bad_operation_evidence_never_pass(self):
        os.environ["UX_FAKE_CASE"]="bad_coverage"
        self.assertEqual(self.invoke(),1)

    def test_dropped_issue_is_not_treated_as_resolution(self):
        os.environ["UX_FAKE_CASE"]="drop_issue"
        self.assertEqual(self.invoke(),1)
        self.assertIn("dropped",self.state()[0]["reason"])

    def test_iteration_limit_and_plateau_are_not_success(self):
        os.environ["UX_FAKE_CASE"]="plateau"
        self.assertEqual(self.invoke("run","--max-iterations","1"),2)
        self.assertEqual(self.state()[0]["status"],"incomplete")

    def test_two_unchanged_reviews_stop_at_plateau_before_iteration_limit(self):
        os.environ["UX_FAKE_CASE"]="plateau"
        self.assertEqual(self.invoke(),2)
        state,_=self.state()
        self.assertEqual((state["status"],state["iteration"]),("stalled",2))

    def test_batch_includes_all_findings_in_three_root_causes(self):
        os.environ["UX_FAKE_CASE"]="root_groups"
        self.assertEqual(self.invoke(),0)
        state,folder=self.state()
        self.assertEqual([i["id"] for i in state["selected_issues"]],
                         ["Issue 01","Issue 02","Issue 03","Issue 04"])
        prompt=(folder/"001-fixer/prompt.txt").read_text()
        argv=json.loads((folder/"001-fixer/fixture-argv.json").read_text())
        self.assertTrue(any("mcp_servers.ux_gan_browser.command" in a for a in argv))
        self.assertIn('"root_cause": "third_cause"',prompt)

    def test_viewport_claim_without_matching_image_is_rejected(self):
        os.environ["UX_FAKE_CASE"]="wrong_viewport"
        self.assertEqual(self.invoke(),1)
        self.assertIn("viewport",self.state()[0]["reason"])

    def test_missing_required_state_is_not_a_pass(self):
        self.assertEqual(self.invoke("audit"),0)
        state,_=self.state()
        state["plan"]["flows"][0]["states"].append("invalid_input")
        reasons=h.gate(state["audit"],state["plan"],state["references"],[{"passed":True}])
        self.assertTrue(any("invalid_input" in r for r in reasons))

    def test_failed_main_flow_perspective_cannot_hide_behind_another_pass(self):
        self.assertEqual(self.invoke(),0)
        state,_=self.state()
        state["audit"]["coverage"][-1]["result"]="failed"
        reasons=h.gate(state["audit"],state["plan"],state["references"],state["tests"])
        self.assertTrue(any("skips_explanation" in r for r in reasons))

    def test_issue_with_an_unrelated_screen_image_is_rejected(self):
        self.assertEqual(self.invoke("audit"),0)
        state,_=self.state()
        state["evidence"]["db"]["screen_id"]="another_screen"
        with self.assertRaises(h.Blocked):
            h.validate_audit(state["audit"],state["evidence"],state["plan"])

    def test_blank_ui_target_in_evidence_is_rejected(self):
        directory=self.base/"role";images=directory/"screenshots";images.mkdir(parents=True)
        image=images/"target.png";image.write_bytes(png())
        result={"evidence":[{"id":"frame","path":str(image),"description":"a page","target":" ",
                             "url":"http://localhost:3000","viewport":{"width":1440,"height":900}}]}
        with self.assertRaises(h.Blocked):
            h.validated_evidence(result,directory,"browser-plugin",self.project,"run")

    def test_sandbox_failure_blocks_before_any_model_phase(self):
        with patch.object(h,"sandbox_smoke",side_effect=h.Blocked("host sandbox unavailable")):
            self.assertEqual(self.invoke(),1)
        state,folder=self.state()
        self.assertEqual(state["status"],"blocked")
        self.assertFalse(list(folder.glob("*-planner")))

    def test_project_lock_refuses_a_second_run(self):
        path=self.project/"artifacts/ux-gan/.lock";path.parent.mkdir(parents=True)
        with path.open("a+") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(h.Blocked):self.invoke()

    def test_clutter_prevents_pass_even_after_high_issue_resolved(self):
        os.environ["UX_FAKE_CASE"]="clutter"
        self.assertEqual(self.invoke(),2)
        self.assertIn("simplicity",self.state()[0]["reason"])

    def test_required_test_failure_prevents_pass(self):
        self.assertEqual(self.invoke("run","--test-command","python3 -c 'raise SystemExit(7)'"),2)
        self.assertFalse(self.state()[0]["tests"][0]["passed"])

    def test_unexpected_fix_files_are_preserved_and_block(self):
        os.environ["UX_FAKE_CASE"]="unexpected"
        self.assertEqual(self.invoke(),1)
        self.assertTrue((self.project/"unexpected.txt").exists())
        self.assertIn("Unexpected source",self.state()[0]["reason"])
        self.assertTrue(self.state()[0]["fix_in_progress"])
        self.assertFalse((self.project/"docs/ui-ux-fix-report.md").exists())

    def test_reviewer_source_changes_block(self):
        os.environ["UX_FAKE_CASE"]="source_during_review"
        self.assertEqual(self.invoke(),1)
        self.assertIn("Source changed",self.state()[0]["reason"])

    def test_resume_finishes_pending_review_without_refixing(self):
        os.environ["UX_FAKE_CASE"]="pending_review"
        self.assertEqual(self.invoke(),1)
        state,_=self.state()
        self.assertTrue(state["pending_review"])
        os.environ["UX_FAKE_CASE"]=""
        self.assertEqual(self.invoke("resume",state["run_id"]),0)
        state,_=self.state()
        self.assertEqual(state["status"],"passed")
        self.assertEqual(state["iteration"],1)

    def test_resume_refuses_new_source_changes(self):
        os.environ["UX_FAKE_CASE"]="pending_review"
        self.assertEqual(self.invoke(),1)
        state,_=self.state()
        (self.project/"app.html").write_text("someone else's edit")
        self.assertEqual(self.invoke("resume",state["run_id"]),1)
        self.assertEqual((self.project/"app.html").read_text(),"someone else's edit")

    def test_finished_run_cannot_pass_resume_after_the_source_changes(self):
        self.assertEqual(self.invoke(),0)
        state,_=self.state()
        before=(self.project/"docs/ui-ux-review.md").read_bytes()
        (self.project/"app.html").write_text("new version")
        self.assertEqual(self.invoke("resume",state["run_id"]),1)
        self.assertEqual((self.project/"docs/ui-ux-review.md").read_bytes(),before)

    def test_cancelled_fix_keeps_partial_edits_and_requires_new_audit(self):
        original=h.run_role
        def cancel(role,*args):
            if role=="fixer":
                (self.project/"app.html").write_text("partial fix")
                raise h.Cancelled("test interruption")
            return original(role,*args)
        with patch.object(h,"run_role",side_effect=cancel):
            self.assertEqual(self.invoke(),130)
        state,_=self.state()
        self.assertEqual(state["status"],"cancelled")
        self.assertTrue(state["fix_in_progress"])
        self.assertEqual((self.project/"app.html").read_text(),"partial fix")
        self.assertFalse((self.project/"docs/ui-ux-fix-report.md").exists())
        self.assertEqual(self.invoke("resume",state["run_id"]),1)

    def test_owned_preview_stops_and_redacts_log_without_stopping_another_process(self):
        other=subprocess.Popen([sys.executable,"-c","import time;time.sleep(120)"],start_new_session=True)
        original=subprocess.Popen;owned=[]
        def launch(argv,*args,**kwargs):
            proc=original(argv,*args,**kwargs)
            if argv[:2]==["bash","-c"] and "time.sleep" in argv[-1]:owned.append(proc)
            return proc
        start="python3 -u -c 'import os,time;print(os.getenv(\"EXAMPLE_API_KEY\"));time.sleep(120)'"
        try:
            with patch.dict(os.environ,{"EXAMPLE_API_KEY":"secret-value-123"}):
                with patch.object(h.subprocess,"Popen",side_effect=launch):
                    self.assertEqual(self.invoke("audit","--start-command",start),0)
            self.assertEqual(len(owned),1)
            self.assertIsNotNone(owned[0].poll())
            self.assertIsNone(other.poll())
            _,folder=self.state()
            log=(folder/"preview.log").read_text()
            self.assertNotIn("secret-value-123",log)
            self.assertIn("[redacted]",log)
        finally:
            h.terminate(other)

    def test_recursive_execution_refused(self):
        with patch.dict(os.environ,{"UX_GAN_CHILD":"1"}):
            with self.assertRaises(h.Blocked):
                self.invoke()

    def test_secret_redaction_keeps_structure(self):
        with patch.dict(os.environ,{"EXAMPLE_API_KEY":"secret-value-123"}):
            v=h.scrub({"text":"token secret-value-123","image":{"type":"image","data":"abc"}})
        self.assertNotIn("secret-value",json.dumps(v))
        self.assertEqual(v["image"]["data"],"[image omitted; see evidence]")

    def test_png_corruption_is_rejected(self):
        p=self.base/"bad.png"
        p.write_bytes(png()[:-10])
        with self.assertRaises(h.Blocked):h.png_dimensions(p)

    def test_private_model_and_rules_are_not_bypassed(self):
        self.assertEqual(self.invoke("audit"),0)
        _,folder=self.state()
        inv=json.loads((folder/"000-reviewer/invocation.json").read_text())
        self.assertEqual(inv["sandbox"],"read-only")
        self.assertTrue(inv["attached_images"])
        self.assertNotIn("ignore-rules",(folder/"000-reviewer/prompt.txt").read_text())


if __name__=="__main__":
    unittest.main()
