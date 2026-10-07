"""Fake model decisions, real local checks: orchestration is not a model-quality eval."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "tools/design-research/skill/scripts"
sys.path.insert(0, str(SCRIPTS))
import evidence
import runtime
spec = importlib.util.spec_from_file_location("design_research_harness", SCRIPTS / "harness.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)

BAD_API = """def create(name, request_id, rows):
    row = {'id': len(rows) + 1, 'name': name, 'request_id': request_id}
    rows.append(row)
    return 201, row
"""
GOOD_API = """def create(name, request_id, rows):
    if not isinstance(name, str) or not name.strip():
        return 400, {'error': 'name is required'}
    for row in rows:
        if row['request_id'] == request_id:
            return 200, row
    row = {'id': len(rows) + 1, 'name': name, 'request_id': request_id}
    rows.append(row)
    return 201, row
"""
API_CHECK = r"""
import json, threading, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from api import create
rows = []
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        status, result = create(data.get('name'), data.get('request_id'), rows)
        body = json.dumps(result).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(body)
server = HTTPServer(('127.0.0.1', 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
def send(name, key):
    req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}', method='POST',
                                 data=json.dumps({'name': name, 'request_id': key}).encode())
    try: response = urllib.request.urlopen(req)
    except urllib.error.HTTPError as exc: response = exc
    with response: return {'status': response.status, 'body': json.load(response)}
try:
    invalid = send('', 'invalid')
    first = send('sample', 'same-request')
    duplicate = send('sample', 'same-request')
    result = {'invalid': invalid, 'first': first, 'duplicate': duplicate, 'saved_count': len(rows)}
    print(json.dumps(result))
    assert invalid['status'] == 400, 'invalid input must not be saved'
    assert first['body']['id'] == duplicate['body']['id'], 'duplicate request must return same row'
    assert len(rows) == 1, 'exactly one saved row'
finally:
    server.shutdown()
    server.server_close()
"""
POC = """import json,time
values = list(range(500))
queries = [0,99,499,501] * 25
started = time.perf_counter()
baseline = [item in values for item in queries]
baseline_seconds = time.perf_counter() - started
started = time.perf_counter()
index = set(values)
candidate = [item in index for item in queries]
candidate_seconds = time.perf_counter() - started
assert baseline == candidate
metrics = {'same_results': True, 'input_count': len(queries),
           'baseline_seconds': baseline_seconds, 'candidate_seconds': candidate_seconds}
with open('metrics.json', 'w') as file:
    json.dump(metrics, file)
print(json.dumps(metrics))
"""

FAKE = r"""#!PYTHON
import json,os,re,sys
from pathlib import Path
args = sys.argv[1:]
if 'exec' in args and '--help' in args:
    print('--json --output-schema --output-last-message --sandbox --ephemeral')
    sys.exit(0)
if 'sandbox' in args:
    if '--help' in args:
        print('Usage: codex sandbox [OPTIONS] -- <COMMAND>')
        sys.exit(0)
    if os.environ.get('DR_FAKE_SANDBOX_FAIL'):
        print('sandbox unavailable', file=sys.stderr); sys.exit(1)
    index = args.index('--')
    os.execvp(args[index+1],args[index+1:])
prompt = args[-1]
role = re.search(r'\nROLE: ([^\n]+)',prompt).group(1)
data = json.loads(prompt.split('\nINPUT:\n',1)[1])
fixture = json.loads(Path(os.environ['DR_FAKE_DATA']).read_text())
scenario = os.environ.get('DR_FAKE_SCENARIO','normal')
project = Path(data['config']['project'])
workspace = project / 'docs/design-research' / data['config']['slug']
research = data['config']['mode'] == 'research'
if role == 'planner':
    result = {'status':'ready','reason':'bounded fixture','goal':'controlled correctness check',
              'domain':'research' if research else 'backend','baseline':'existing/simple implementation',
              'constraints':['fixed inputs and local test environment'],
              'criteria':[{'id':'C1','title':'correct results','kind':'runtime',
                           'required':True,'acceptance':'invalid input rejected; no duplicate save or unequal results'}],
              'test_commands':[] if research else [{'command':'python3 check.py','check_ids':['C1'],
                                                     'artifact_paths':[]}],
              'complexity_baseline':'one Python implementation','queries':[]}
elif role == 'producer':
    result = {'status':'proposed','reason':'equal inputs, compare two methods',
              'dossier_json':'','files':[{'path':'comparison.py','content':fixture['poc']}],
              'experiments':[{'id':'E1','command':'python3 comparison.py','check_ids':['C1'],
                              'input_files':[],'artifact_paths':['metrics.json'],'timeout_seconds':20}],'sources':[]}
elif role == 'fixer':
    if scenario != 'complexity':
        (project/'api.py').write_text(fixture['good_api'])
    if scenario == 'interrupt_fix':
        print('interrupted model',file=sys.stderr); sys.exit(3)
    if scenario == 'undeclared':
        (project/'extra.py').write_text('unrequested = True\n')
    result = {'status':'changed','reason':'reject invalid values and deduplicate request IDs',
              'fixed_issue_ids':[row['id'] for row in data['selected_issues']],
              'changed_files':[] if scenario == 'complexity' else ['api.py'],'complexity_changes':[]}
else:
    if scenario == 'review_fail':
        print('temporary reviewer failure',file=sys.stderr); sys.exit(3)
    records = [row for row in data['evidence'].values()
               if row['kind'] in ['test','experiment'] and row['iteration'] == data['iteration']]
    ids = [row['id'] for row in records]
    good = bool(records) and all(row['exit_code'] == 0 for row in records)
    if scenario == 'source_change':
        (project/'unexpected.txt').write_text('outside fix phase')
    if scenario == 'tamper':
        receipt = json.loads((workspace/records[0]['path']).read_text())
        (workspace/receipt['outputs']['stdout']['path']).write_text('fake success')
    if scenario == 'false_pass':
        good = True
    issues = []
    if not good or data.get('review'):
        previous = (data.get('review') or {}).get('issues',[])
        keys = [row['id'] for row in previous] or ['ISSUE-01']
        for key in keys:
            issues.append({'id':key,'title':'invalid input and duplicate storage','severity':'High',
                           'status':'resolved' if good else 'open','target':'POST create',
                           'action':'send empty name, then repeat same request ID',
                           'expected':'400 then one saved row','actual':'checked raw HTTP responses',
                           'why':'users lose confidence in saved data','improvement':'validate and deduplicate',
                           'root_cause':'write validation','check_ids':['C1'],'evidence_ids':ids})
    if scenario == 'drop' and data.get('review'):
        issues = []
    if scenario == 'complexity':
        issues = [{'id':'ISSUE-C','title':'unnecessary service','severity':'Medium','status':'open',
                   'target':'architecture','action':'evaluate deployed components',
                   'expected':'one local component','actual':'unneeded additional component',
                   'why':'maintenance overhead','improvement':'retain simple baseline',
                   'root_cause':'complexity','check_ids':['C1'],'evidence_ids':ids}]
    dossier = ''
    sources = []
    if research:
        record = records[-1]
        ledger = fixture['ledger']
        ledger['sources'][0]['local_path'] = record['path']
        ledger['experiments'][0]['artifacts'] = [record['path']]
        dossier = json.dumps(ledger)
        sources = [{'id':'S1','title':'Controlled local comparison','url':'','path':record['path'],
                    'locator':'receipt outputs / stdout / same_results','read_level':'relevant_sections'}]
        if scenario == 'fake_artifact':
            ledger['experiments'][0]['artifacts'] = ['missing.json']
            dossier = json.dumps(ledger)
        if scenario == 'accepted':
            ledger['decision'].update(status='accepted',accepted_by='invented',accepted_at='2026-10-04')
            dossier = json.dumps(ledger)
    result = {'status':'reviewed','reason':'real results inspected','issues':issues,
              'checks':[{'check_id':'C1','result':'pass' if good else 'fail',
                         'reason':'raw HTTP/PoC output and process exit inspected','evidence_ids':ids}],
              'code_evidence':[], 'dossier_json':dossier,'sources':sources,
              'reference_implementations':[], 'complexity_ok':scenario != 'complexity',
              'complexity_reason':'minimal validation and no extra services' if scenario != 'complexity'
                                  else 'additional service has no benefit over baseline'}
output = Path(args[args.index('--output-last-message')+1])
output.write_text(json.dumps(result))
print(json.dumps({'type':'turn.completed','role':role}))
"""


def ledger():
    return {
        "schema_version": 1, "question": "Compare local membership methods", "scope": "Fixed synthetic inputs",
        "checked_as_of": "2026-10-04", "constraints": [{"id": "K1", "text": "Same results", "kind": "hard"}],
        "sources": [{"id": "S1", "title": "Controlled local comparison", "url": None,
                     "local_path": "placeholder.json", "source_type": "experiment",
                     "read_level": "relevant_sections", "peer_review_status": "not_applicable",
                     "peer_review_evidence": None, "retrieved_at": "2026-10-04", "published_at": None,
                     "version": "fixture", "study_id": "controlled-comparison", "correction_status": "not_applicable"}],
        "claims": [{"id": "CL1", "statement": "Both methods return identical results on fixed input",
                    "status": "observed", "confidence": "high", "context": "500 values and 100 queries",
                    "limitations": ["Synthetic local workload only"],
                    "evidence": [{"source_id": "S1", "relation": "supports", "locator": "stdout.same_results"}]}],
        "candidates": [{"id": key, "name": name, "baseline": key == "A", "summary": name,
                        "hard_constraints": [{"constraint_id": "K1", "result": "pass",
                                              "claim_ids": ["CL1"], "reason": "Equal controlled output"}]}
                       for key, name in [("A", "Linear membership"), ("B", "Set membership")]],
        "comparison": [{"criterion": "Correctness on fixed inputs", "candidate_id": key,
                        "finding": "Identical results", "basis": "measured", "claim_ids": ["CL1"]}
                       for key in ["A", "B"]],
        "experiments": [{"id": "E1", "hypothesis": "Indexing preserves membership results",
                         "candidate_ids": ["A", "B"], "controls": ["Same values and queries"],
                         "metrics": ["Equality", "Elapsed seconds"], "acceptance": "Identical outputs",
                         "status": "executed", "artifacts": ["placeholder.json"]}],
        "decision": {"status": "proposed", "candidate_id": "A",
                     "rationale": "Retain simpler baseline until representative workload justifies indexing",
                     "claim_ids": ["CL1"], "unresolved": [], "revisit_when": ["Representative workload changes"],
                     "accepted_by": None, "accepted_at": None},
    }


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dr-gan-test-")
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        (self.project / "api.py").write_text(BAD_API)
        (self.project / "check.py").write_text(textwrap.dedent(API_CHECK))
        (self.project / "notes.txt").write_text("existing user edit")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake = self.bin / "codex"
        fake.write_text(FAKE.replace("PYTHON", sys.executable, 1))
        fake.chmod(0o755)
        data = self.root / "fixture.json"
        data.write_text(json.dumps({"poc": POC, "good_api": GOOD_API, "ledger": ledger()}))
        self.env = {**os.environ, "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                    "HOME": str(self.root / "home"), "CODEX_HOME": str(self.root / "home/.codex"),
                    "DR_FAKE_DATA": str(data), "DR_FAKE_SCENARIO": "normal",
                    "PYTHONDONTWRITEBYTECODE": "1"}

    def tearDown(self):
        self.temp.cleanup()

    @property
    def workspace(self):
        return self.project / "docs/design-research/review"

    def run_harness(self, mode, *args, scenario="normal"):
        env = {**self.env, "DR_FAKE_SCENARIO": scenario}
        command = ["bash", str(SCRIPTS / "gan-harness.sh"), mode, "--project", str(self.project)]
        if mode not in {"doctor", "resume"}:
            command += ["--brief", "Controlled fixture evaluation", "--phase-timeout", "30"]
        command.extend(args)
        return subprocess.run(command, env=env, capture_output=True, text=True, timeout=35)

    def state(self):
        status = json.loads((self.workspace / "status.json").read_text())
        return json.loads((self.workspace / status["state_path"]).read_text())

    def test_audit_runs_real_http_checks_without_editing_source(self):
        result = self.run_harness("audit")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = self.state()
        self.assertEqual(state["status"], "reviewed")
        self.assertEqual(state["review"]["checks"][0]["result"], "fail")
        self.assertEqual((self.project / "api.py").read_text(), BAD_API)
        record = next(r for r in state["evidence"].values() if r["kind"] == "test")
        self.assertNotEqual(record["exit_code"], 0)
        receipt = json.loads((self.workspace / record["path"]).read_text())
        output = json.loads((self.workspace / receipt["outputs"]["stdout"]["path"]).read_text())
        self.assertEqual(output["invalid"]["status"], 201)
        self.assertEqual(output["saved_count"], 3)

    def test_run_fixes_then_independently_rechecks_http_storage(self):
        result = self.run_harness("run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = self.state()
        self.assertEqual(state["status"], "passed")
        self.assertEqual(state["iteration"], 2)
        self.assertEqual((self.project / "api.py").read_text(), GOOD_API)
        self.assertEqual((self.project / "notes.txt").read_text(), "existing user edit")
        records = [r for r in state["evidence"].values() if r["kind"] == "test"]
        self.assertEqual([r["exit_code"] for r in records], [1, 0])
        self.assertEqual(state["review"]["issues"][0]["status"], "resolved")
        self.assertIn("変更前の証拠", (self.workspace / "fix-report.md").read_text())
        self.assertIn("変更後の独立レビュー", (self.workspace / "fix-report.md").read_text())
        receipt = json.loads((self.workspace / records[-1]["path"]).read_text())
        output = json.loads((self.workspace / receipt["outputs"]["stdout"]["path"]).read_text())
        self.assertEqual(output["saved_count"], 1)
        self.assertEqual(output["invalid"]["status"], 400)

    def test_research_runs_real_poc_without_application_changes(self):
        result = self.run_harness("research")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        state = self.state()
        self.assertEqual(state["status"], "research_complete")
        self.assertEqual((self.project / "api.py").read_text(), BAD_API)
        self.assertFalse((self.project / "comparison.py").exists())
        row = next(r for r in state["evidence"].values() if r["kind"] == "experiment")
        receipt = json.loads((self.workspace / row["path"]).read_text())
        metrics = json.loads((self.workspace / receipt["outputs"]["stdout"]["path"]).read_text())
        self.assertTrue(metrics["same_results"])
        self.assertEqual(metrics["input_count"], 100)
        self.assertGreaterEqual(metrics["baseline_seconds"], 0)
        artifact = receipt["artifacts"][0]
        self.assertEqual(json.loads((self.workspace / artifact["path"]).read_text()), metrics)
        actual = json.loads((self.workspace / "evidence.json").read_text())
        self.assertTrue(evidence.verify_artifacts(actual, self.workspace, state["evidence"])["valid"])

    def test_false_runtime_pass_is_rejected(self):
        result = self.run_harness("audit", scenario="false_pass")
        self.assertEqual(result.returncode, 2)
        self.assertIn("current successful", self.state()["reason"])

    def test_passing_command_cannot_hide_another_failed_required_case(self):
        result = self.run_harness("audit", "--test-command", "true", scenario="false_pass")
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot be hidden", self.state()["reason"])

    def test_nonexistent_experiment_artifact_is_rejected(self):
        result = self.run_harness("research", scenario="fake_artifact")
        self.assertEqual(result.returncode, 2)
        self.assertIn("strict validation", self.state()["reason"])

    def test_automatic_human_acceptance_is_rejected(self):
        result = self.run_harness("research", scenario="accepted")
        self.assertEqual(result.returncode, 2)
        self.assertIn("human acceptance", self.state()["reason"])

    def test_issue_cannot_disappear_after_fix(self):
        result = self.run_harness("run", scenario="drop")
        self.assertEqual(result.returncode, 2)
        self.assertIn("dropped earlier issues", self.state()["reason"])

    def test_source_changed_during_review_requires_new_audit(self):
        result = self.run_harness("audit", scenario="source_change")
        self.assertEqual(result.returncode, 2)
        self.assertIn("outside a declared fix", self.state()["reason"])

    def test_stdout_tampering_is_rejected(self):
        result = self.run_harness("audit", scenario="tamper")
        self.assertEqual(result.returncode, 2)
        self.assertIn("output changed", self.state()["reason"])

    def test_interrupted_fix_diff_is_preserved_and_resume_refused(self):
        result = self.run_harness("run", scenario="interrupt_fix")
        self.assertEqual(result.returncode, 2)
        state = self.state()
        self.assertEqual(state["phase"], "fixing")
        self.assertEqual((self.project / "api.py").read_text(), GOOD_API)
        resumed = self.run_harness("resume", state["run_id"])
        self.assertEqual(resumed.returncode, 2)
        self.assertIn("Fix was interrupted", resumed.stdout)

    def test_undeclared_source_edit_is_not_silently_accepted(self):
        result = self.run_harness("run", scenario="undeclared")
        self.assertEqual(result.returncode, 2)
        self.assertIn("declared files", self.state()["reason"])
        self.assertTrue((self.project / "extra.py").exists())

    def test_resume_pending_review_does_not_repeat_poc(self):
        result = self.run_harness("research", scenario="review_fail")
        self.assertEqual(result.returncode, 2)
        state = self.state()
        self.assertEqual(state["phase"], "pending_review")
        count = len(state["executions"])
        resumed = self.run_harness("resume", state["run_id"])
        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        self.assertEqual(len(self.state()["executions"]), count)

    def test_finished_run_cannot_be_resumed_as_new_work(self):
        self.run_harness("audit")
        result = self.run_harness("resume", self.state()["run_id"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("finished", result.stdout)

    def test_resume_partial_checks_preserves_old_receipts(self):
        self.run_harness("audit", scenario="review_fail")
        state = self.state()
        old = {key: (self.workspace / row["path"]).read_bytes()
               for key, row in state["evidence"].items()}
        # Persist the state found when a run stops within its check phase.
        state["phase"] = "checks"
        state["status"] = "cancelled"
        path = self.workspace / "runs" / state["run_id"] / "state.json"
        path.write_text(json.dumps(state))
        resumed = self.run_harness("resume", state["run_id"])
        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        current = self.state()
        self.assertEqual(current["iteration"], 2)
        self.assertEqual(len(current["executions"]), 2)
        for key, data in old.items():
            self.assertEqual((self.workspace / current["evidence"][key]["path"]).read_bytes(), data)

    def test_max_iterations_does_not_report_pass(self):
        result = self.run_harness("run", "--max-iterations", "1")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.state()["status"], "limit_reached")
        self.assertEqual((self.project / "api.py").read_text(), BAD_API)

    def test_iteration_budget_cannot_silently_expand(self):
        result = self.run_harness("run", "--max-iterations", "6")
        self.assertEqual(result.returncode, 2)
        self.assertIn("1-5 iterations", result.stdout + result.stderr)
        self.assertFalse(self.workspace.exists())

    def test_research_cannot_ignore_an_explicit_failing_check(self):
        result = self.run_harness("research", "--test-command", "false", "--max-iterations", "1")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        state = self.state()
        self.assertEqual(len(state["executions"]), 2)
        self.assertTrue(any(row.get("command") == "false" and row.get("exit_code") != 0
                            for row in state["evidence"].values()))
        self.assertNotEqual(state["status"], "research_complete")

    def test_complexity_regression_stops_on_plateau(self):
        (self.project / "api.py").write_text(GOOD_API)
        result = self.run_harness("run", scenario="complexity")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self.state()["status"], "plateau")
        self.assertEqual(self.state()["iteration"], 3)

    def test_optional_supplied_review_is_archived_and_not_required(self):
        report = self.root / "ui-review.md"
        report.write_text("UI shows saved but API has duplicate records")
        result = self.run_harness("audit", "--review", str(report))
        self.assertEqual(result.returncode, 0)
        path = self.workspace / self.state()["input_review"]
        self.assertEqual(path.read_text(), report.read_text())

    def test_secrets_in_test_output_are_redacted_and_ambient_env_is_not_inherited(self):
        (self.project / "api.py").write_text(GOOD_API)
        (self.project / "check.py").write_text(
            "import os\nprint(os.environ['DR_SAMPLE_TOKEN'])\n"
            "assert 'AMBIENT_PRIVATE_TOKEN' not in os.environ\n")
        envfile = self.root / "test.env"
        envfile.write_text("DR_SAMPLE_TOKEN=fictional-private-value\n")
        self.env["AMBIENT_PRIVATE_TOKEN"] = "fictional-ambient-value"
        result = self.run_harness("audit", "--test-env-file", str(envfile))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for path in self.workspace.rglob("*"):
            if path.is_file():
                self.assertNotIn("fictional-private-value", path.read_text())
                self.assertNotIn("fictional-ambient-value", path.read_text())

    def test_previous_report_survives_early_setup_failure(self):
        self.workspace.mkdir(parents=True)
        previous = self.workspace / "review.md"
        previous.write_text("prior human review")
        self.env["DR_FAKE_SANDBOX_FAIL"] = "1"
        result = self.run_harness("audit")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(previous.read_text(), "prior human review")

    def test_report_evidence_links_resolve(self):
        self.run_harness("run")
        for name in ["review.md", "fix-report.md", "reference-implementations.md"]:
            text = (self.workspace / name).read_text()
            for target in re.findall(r"\]\(([^)]+)\)", text):
                if not target.startswith(("http:", "https:")):
                    self.assertTrue((self.workspace / target).is_file(), target)
        for report in self.workspace.glob("runs/*/reports/*.md"):
            for target in re.findall(r"\]\(([^)]+)\)", report.read_text()):
                if not target.startswith(("http:", "https:")):
                    self.assertTrue((report.parent / target).is_file(), str(report) + ": " + target)

    def test_reference_urls_are_optional_and_offline_access_is_disclosed(self):
        result = self.run_harness("audit", "--reference-url", "https://example.com/specification")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.state()["sources"]["REF1"]["status"], "unavailable")

    def test_project_lock_prevents_simultaneous_runs(self):
        import fcntl
        parent = self.project / "docs/design-research"
        parent.mkdir(parents=True)
        with (parent / ".gan.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_harness("audit")
        self.assertEqual(result.returncode, 2)
        self.assertIn("already running", result.stdout)

    def test_changed_test_environment_refuses_resume(self):
        envfile = self.root / "test.env"
        envfile.write_text("CASE=before\n")
        self.run_harness("research", "--test-env-file", str(envfile), scenario="review_fail")
        run_id = self.state()["run_id"]
        envfile.write_text("CASE=after\n")
        result = self.run_harness("resume", run_id)
        self.assertEqual(result.returncode, 2)
        self.assertIn("environment changed", result.stdout)

    def test_owned_preview_lifecycle_runs_in_disposable_project(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        (self.project / "check.py").write_text(
            "import os,urllib.request\n"
            "with urllib.request.urlopen(os.environ['DR_GAN_TEST_URL']) as response:\n"
            " assert response.status == 200\n")
        result = self.run_harness("audit", "--start-command",
                                  f"python3 -m http.server {port} --bind 127.0.0.1",
                                  "--url", f"http://127.0.0.1:{port}")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with socket.socket() as listener:
            self.assertNotEqual(listener.connect_ex(("127.0.0.1", port)), 0)

    def test_archived_ledger_can_be_strictly_validated_against_workspace(self):
        self.run_harness("research")
        archived = next(self.workspace.glob("runs/*/reports/evidence.json"))
        result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "research.py"), "validate",
                                 str(archived), "--check-artifacts", "--artifacts-root", str(self.workspace)],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_recursive_execution_is_refused(self):
        self.env["DR_GAN_CHILD"] = "1"
        result = self.run_harness("audit")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Recursive", result.stdout)

    def test_production_test_env_and_remote_app_url_are_rejected(self):
        envfile = self.root / "test.env"
        envfile.write_text("NODE_ENV=production\n")
        result = self.run_harness("audit", "--test-env-file", str(envfile))
        self.assertEqual(result.returncode, 2)
        self.assertIn("Production", result.stdout)
        self.assertIn("Production", self.state()["reason"])
        status = json.loads((self.workspace / "status.json").read_text())
        self.assertIn("Production", status["reason"])
        result = self.run_harness("audit", "--url", "https://example.com")
        self.assertEqual(result.returncode, 2)
        self.assertIn("local isolated", result.stdout)


class EvidenceUnitTests(unittest.TestCase):
    def test_strict_checker_rejects_missing_files_that_structure_accepts(self):
        data = ledger()
        self.assertTrue(evidence.validate_dossier(data)["valid"])
        with tempfile.TemporaryDirectory() as root:
            result = evidence.verify_artifacts(data, root)
        self.assertFalse(result["valid"])

    def test_strict_checker_rejects_path_escape_and_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "root"
            root.mkdir()
            target = Path(temp) / "external"
            target.write_text("actual file")
            (root / "link").symlink_to(target)
            for path in ["../external", "link"]:
                with self.assertRaises(runtime.Blocked):
                    evidence.existing_artifact(root, path)

    def test_owned_process_timeout_is_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            result = runtime.capture([sys.executable, "-c", "import time;time.sleep(3)"],
                                     cwd=temp, env=runtime.test_environment(temp),
                                     directory=Path(temp) / "logs", timeout=0.1, label="timeout")
            self.assertTrue(result["timed_out"])
            self.assertNotEqual(result["exit_code"], 0)

    def test_source_access_failure_is_not_no_matching_paper(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(evidence, "public_url", side_effect=runtime.Blocked("network unavailable")):
                row = evidence.source_receipt(
                    {"id": "S1", "title": "Actual source", "url": "https://example.com",
                     "locator": "section"}, Path(temp) / "source.json", True)
        self.assertEqual(row["status"], "unavailable")
        self.assertIn("network unavailable", row["reason"])

    def test_credential_urls_are_not_reference_sources(self):
        with self.assertRaises(runtime.Blocked):
            evidence.public_url("https://user:private@example.com")

    def test_test_env_is_literal_without_shell_expansion(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.env"
            path.write_text("LITERAL=$(touch /tmp/never-executed-dr-test)\n")
            self.assertEqual(runtime.load_test_env(path)["LITERAL"],
                             "$(touch /tmp/never-executed-dr-test)")


if __name__ == "__main__":
    unittest.main()
