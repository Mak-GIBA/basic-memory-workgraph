from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'overlay/tools/design-research/skill/scripts'),
              str(ROOT/'core_upgrade/overlay/tools/design-research/skill/scripts')]
from workflow_overview import overview


class WorkflowOverviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'repo';self.root.mkdir()
    def fixture(self):
        source=ROOT/'core_upgrade/examples/workstream-demo'
        shutil.copytree(source,self.root,dirs_exist_ok=True)
        path=self.root/'.specify/workbench/research-plan.json'
        return hashlib.sha256(path.read_bytes()).hexdigest()
    def completed(self,key,sha,slug,runid):
        p=self.root/f'docs/design-research/{slug}/runs/{runid}/state.json'
        p.parent.mkdir(parents=True,exist_ok=True)
        s={'schema_version':1,'run_id':runid,'status':'research_complete','phase':'complete',
           'config':{'mode':'research','project':str(self.root),'slug':slug,'brief':'fixture'},
           'dossier':{'candidates':[{'id':'a'}]},
           'workstream_context':{'workstream_id':key,'plan_sha256':sha}}
        p.write_text(json.dumps(s,ensure_ascii=False))
        q=p.parent/'reports/report.md';q.parent.mkdir();q.write_text('Synthetic test report')
    def test_empty_repo_not_running(self):
        r=overview(self.root);self.assertEqual(r['workflow_stage'],'standalone')
        self.assertTrue(r['inspection_only']);self.assertFalse(r['ready_to_research'])
    def test_requirements_without_plan(self):
        p=self.root/'docs/upstream/requirements.md';p.parent.mkdir(parents=True);p.write_text('Requirement')
        r=overview(self.root);self.assertEqual(r['workflow_stage'],'needs_plan')
    def test_initial_plan_waves_are_not_execution(self):
        self.fixture();r=overview(self.root)
        self.assertEqual(r['workflow_stage'],'research_in_progress')
        self.assertEqual(r['ready_to_research'],['RP1','RP2'])
        self.assertEqual(r['execution_waves'],[['RP1','RP2'],['RP3']])
    def test_dependency_completed_and_integration_pending(self):
        h=self.fixture();self.completed('RP1',h,'logic-1','run-1');self.completed('RP2',h,'logic-2','run-2')
        r=overview(self.root);self.assertEqual(r['ready_to_research'],['RP3'])
        self.completed('RP3',h,'logic-3','run-3');r=overview(self.root)
        self.assertEqual(r['workflow_stage'],'integration_pending')
        self.assertEqual(r['ready_to_research'],[])
    def test_stale_requirement_blocks(self):
        self.fixture();p=self.root/'docs/upstream/requirements.md';p.write_text('changed')
        r=overview(self.root);self.assertEqual(r['workflow_stage'],'plan_invalid')
    def test_duplicate_completed_runs_are_not_silently_chosen(self):
        h=self.fixture();self.completed('RP1',h,'logic-1','run-1');self.completed('RP1',h,'logic-1','run-2')
        r=overview(self.root);self.assertEqual(r['workflow_stage'],'needs_run_selection')
        self.assertEqual(next(x for x in r['workstreams'] if x['id']=='RP1')['status'],'ambiguous')
    def test_wrong_plan_run_not_counted(self):
        self.fixture();self.completed('RP1','0'*64,'logic-1','run-1')
        r=overview(self.root);self.assertEqual(r['ready_to_research'],['RP1','RP2'])

if __name__=='__main__':unittest.main()
