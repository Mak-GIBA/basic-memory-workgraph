"""Miniature integration fixtures exercise anchors and transactions, not full main."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

P=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('light_upgrade',P/'apply_upgrade.py')
u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
prior=u.prior_module()
spec=importlib.util.spec_from_file_location('old_fixture',P/'previous_report_upgrade/tests/test_apply_upgrade.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
H=f.HARNESS.replace('    return BASE +', '    inputs["workspace"] = "fixture"\n    return BASE +',1)+'''
def execution(args):
    state={"expected_source": {}, "config":{}}
    if True:
        if True:
            state["original_source"] = state["expected_source"]
            try:
                inputs = "fixture"
                state["test_env_hash"] = ""
            finally:
                pass
    return state
'''
R=f.REPORT.replace("    if dossier:","    lines += ['## 調査・比較・検証', '']\n    if dossier:",1).replace('        report += ["", "## Claims', '        report += ["", "## Candidate Comparison", "", "fixture"]\n        report += ["", "## Claims',1)
TRACE='''from .layout import compact

def inspect(root,phase='draft'):
    findings=[];valid=[];config={'docs_dir':'docs/upstream'}
    errors=sum(x['severity']=='error' for x in findings)
    return errors
'''
WORKFLOW='''from pathlib import Path
ROOT=Path('.')

def flow(root,mode):
    text=''
    text+=(ROOT/'assets/prompts/common.md').read_text(encoding='utf-8')+'\\n'
    return text

def snapshot(root):
    c={}
    paths=set(documents(root,c))
    return paths
'''
COMMAND='''def render_skill(name,command,assets):
    body='fixture'
    return body
'''
WRAPPER='''#!/usr/bin/env bash
set -euo pipefail
DR_GAN_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON_BIN:-python3}" -B "$DR_GAN_SCRIPT_DIR/harness.py" "$@"
'''


def setup(repo):
    f.setup(repo)
    data={u.D/'skill/scripts/harness.py':H,u.D/'skill/scripts/report.py':R,
          u.D/'skill/scripts/gan-harness.sh':WRAPPER,
          u.D/'install_design_research.py':'VERSION = "2.0.1"\nREQUIRED = {"scripts/evidence.py", "scripts/report.py", "references/evidence-format.md"}\n',
          u.U/'workbench/trace.py':TRACE,u.U/'workbench/workflow.py':WORKFLOW,
          u.U/'workbench/command_skills.py':COMMAND,
          u.U/'tests/test_compact.py':'class CompactTests:\n    def rows(self):\n        rows=[]\n        return rows\n',
          u.U/'tests/test_workbench.py':"class TraceTests:\n    def test_complete_fixture_ready(self):\n        self.write_records(demo_records());self.assertEqual(inspect(self.root,'ready')['verdict'],'STRUCTURE_OK')\n",
          u.U/'workbench/__init__.py':"VERSION = '2.0.1'\n",
          u.U/'build_single.py':"VERSION = '2.0.1'\n",
          u.U/'assets/skill/SKILL.md':'# Skill fixture\n',u.U/'assets/prompts/common.md':'# Common\n',
          u.U/'assets/templates/design.md':'# Original design\n',
          u.U/'assets/templates/requirements.md':'# Requirements\n<!-- upstream:section content -->\nText\n<!-- /upstream:section -->\n',
          u.U/'assets/templates/verification.md':'# Verify\n<!-- upstream:section content -->\nText\n<!-- /upstream:section -->\n',
          Path('install_speckit_upstream.sh'):'original upstream distribution\n'}
    for rel,body in data.items():
        path=repo/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body)
    (repo/'tests').mkdir(exist_ok=True);(repo/'docs').mkdir(exist_ok=True)
    return data


class PatchTests(unittest.TestCase):
    def test_harness_hook_compile(self):
        out=u.patch_harness(prior.patch_harness(H));compile(out,'harness.py','exec')
        for token in ('--requirements','--reader-friendly','reassessment_context','snapshot_requirements',
                      'require_contract(dossier','readable_instructions(role','"requested_mode"'):
            self.assertIn(token,out)
    def test_old_modes_not_forced(self):
        out=u.patch_harness(prior.patch_harness(H))
        self.assertIn('getattr(args, "reader_friendly", False)',out)
        self.assertIn('if mode == "research":',out)
    def test_report_hook_both_layouts(self):
        out=u.patch_report(prior.patch_report(R));compile(out,'report.py','exec')
        self.assertEqual(out.count('reader_sections(state)'),2)
        self.assertIn('chapter_for_state',out)
    def test_changed_anchor_rejected(self):
        with self.assertRaises(ValueError):u.patch_harness('def nothing(): pass\n')
    def test_duplicate_anchor_rejected(self):
        with self.assertRaises(ValueError):u.once('aaa','a','b')
    def test_function_scope_not_global(self):
        s='def a():\n    return 1\n\ndef b():\n    return 1\n'
        out=u.function_patch(s,'a','return 1','return 2')
        self.assertIn('def b():\n    return 1',out)
    def test_full_miniature_plan(self):
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t);setup(repo);changes=u.plan(repo,verify_base=False)
            self.assertIn(u.U/'workbench/design_quality.py',changes)
            self.assertIn(u.D/'skill/scripts/reassessment.py',changes)
            self.assertIn(b'inspect_design_documents',changes[u.U/'workbench/trace.py'])
            self.assertIn(b'canonical',changes[u.U/'workbench/design_quality.py'])
            self.assertIn(b'dependency_files',changes[u.U/'workbench/workflow.py'])
            self.assertIn(b"2.0.3",changes[u.U/'workbench/__init__.py'])
            self.assertIn(b"2.2.2",changes[u.D/'build_installer.py'])
    def test_unknown_main_rejected_without_writes(self):
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t);setup(repo);before=u.source_snapshot(repo)
            with self.assertRaises(ValueError):u.plan(repo)
            self.assertEqual(before,u.source_snapshot(repo))
    def test_unmanaged_new_module_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t);setup(repo);target=repo/u.D/'skill/scripts/reassessment.py';target.write_text('custom')
            with self.assertRaisesRegex(ValueError,'Unmanaged'):u.plan(repo,verify_base=False)
            self.assertEqual(target.read_text(),'custom')
    def test_wrapper_dispatch_and_quote(self):
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t);setup(repo);changes=u.plan(repo,verify_base=False)
            root=repo/'bin with spaces';root.mkdir();wrapper=root/'gan-harness.sh'
            wrapper.write_bytes(changes[u.D/'skill/scripts/gan-harness.sh'])
            for name in ('harness','reassessment'):
                (root/(name+'.py')).write_text('import json,sys\nprint(json.dumps(["'+name+'",sys.argv[1:]]))\n')
            result=subprocess.run(['bash',str(wrapper),'reassess','--brief','x; touch HACK'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0);self.assertEqual(json.loads(result.stdout),['reassessment',['--brief','x; touch HACK']])
            result=subprocess.run(['bash',str(wrapper),'audit','--brief','x'],capture_output=True,text=True)
            self.assertEqual(json.loads(result.stdout)[0],'harness')
            self.assertFalse((root/'HACK').exists())
    def test_document_scopes_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t);setup(repo);changes=u.plan(repo,verify_base=False)
            for name in ('requirements','verification'):
                s=changes[u.U/f'assets/templates/{name}.md'].decode()
                self.assertEqual(s.count('<!-- upstream:section content -->'),1)
                self.assertEqual(s.count('<!-- /upstream:section -->'),1)
    def test_read_only_plan(self):
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t);setup(repo);before=u.source_snapshot(repo)
            with patch.object(u,'plan',return_value={u.D/'skill/SKILL.md':b'changed'}):
                result=u.apply(repo)
            self.assertEqual(result['action'],'plan');self.assertEqual(before,u.source_snapshot(repo))
            self.assertFalse((repo/'.upstream-research-light.lock').exists())
    def test_staged_failure_preserves_original(self):
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t);setup(repo);before=u.source_snapshot(repo)
            with patch.object(u,'plan',return_value={u.D/'skill/SKILL.md':b'changed'}),patch.object(u,'check_stage',side_effect=ValueError('test failed')):
                with self.assertRaisesRegex(ValueError,'test failed'):u.apply(repo,execute=True)
            self.assertEqual(before,u.source_snapshot(repo));self.assertFalse((repo/u.MANIFEST).exists())
            self.assertFalse((repo/'.upstream-research-light.lock').exists())
    def test_concurrent_source_edit_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t);setup(repo);target=repo/u.D/'skill/SKILL.md'
            def verify(stage,logs):target.write_text('human changed');return []
            with patch.object(u,'plan',return_value={u.D/'skill/SKILL.md':b'changed'}),patch.object(u,'check_stage',side_effect=verify):
                with self.assertRaisesRegex(ValueError,'changed while staging'):u.apply(repo,execute=True)
            self.assertEqual(target.read_text(),'human changed');self.assertFalse((repo/u.MANIFEST).exists())
    def test_same_applied_package_skips_and_edits_reject(self):
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t);setup(repo)
            with patch.object(u,'plan',return_value={u.D/'skill/SKILL.md':b'changed'}),patch.object(u,'check_stage',return_value=[]):
                result=u.apply(repo,execute=True)
            self.assertEqual(result['action'],'upgrade');self.assertTrue(u.already_applied(repo))
            self.assertEqual(u.apply(repo)['action'],'skip')
            (repo/u.D/'skill/SKILL.md').write_text('local change')
            with self.assertRaisesRegex(ValueError,'Local edits'):u.already_applied(repo)
    def test_write_failure_rolls_back(self):
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t);setup(repo);before=u.source_snapshot(repo)
            actual=u.os.replace;count=[0]
            def fail_second(a,b):
                count[0]+=1
                if count[0]==2:raise OSError('injected write failure')
                return actual(a,b)
            with patch.object(u,'plan',return_value={u.D/'skill/SKILL.md':b'changed'}),patch.object(u,'check_stage',return_value=[]),patch.object(u.os,'replace',side_effect=fail_second):
                with self.assertRaises(OSError):u.apply(repo,execute=True)
            self.assertEqual(before,u.source_snapshot(repo));self.assertFalse((repo/u.MANIFEST).exists())


if __name__=='__main__':unittest.main()
