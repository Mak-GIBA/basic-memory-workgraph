"""New design contracts, separate from legacy approval/scoping fixtures."""
import json
from pathlib import Path
import tempfile
import unittest
from workbench.design_quality import MARKER, inspect_design_documents, dependency_files, sha


class ResearchFirstTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.req=self.root/'docs/upstream/requirements.md';self.req.parent.mkdir(parents=True)
        self.req.write_text('# Synthetic unit-test requirements\nNo real user approval is claimed.\n')
        self.run=self.root/'docs/design-research/comparison/runs/FIXTURE'
        frozen=self.run/'inputs/bound-requirements.md';frozen.parent.mkdir(parents=True);frozen.write_bytes(self.req.read_bytes())
        self.report=self.run/'reports/report.md';self.report.parent.mkdir();self.report.write_text('# Synthetic contract fixture\n')
        self.state={'schema_version':1,'run_id':'FIXTURE','status':'research_complete','config':{'mode':'research'},
                    'dossier':{'candidates':[{'id':'A'}]},'requirements_context':{
                    'project_path':'docs/upstream/requirements.md','snapshot':'runs/FIXTURE/inputs/bound-requirements.md',
                    'sha256':sha(self.req.read_bytes())}}
        self.path=self.run/'state.json';self.path.write_text(json.dumps(self.state))
        self.binding={'schema_version':1,'runs':[{
            'state':str(self.path.relative_to(self.root)), 'report':str(self.report.relative_to(self.root)),
            'state_sha256':sha(self.path.read_bytes()),'report_sha256':sha(self.report.read_bytes()),
            'decisions':[{'design_id':'APP-D1','candidate_id':'A','rationale':'Unit fixture only.'}]}],
            'uiux':{'applicable':False,'reason':'No screen design in this fixture.','artifacts':[]}}
        self.design=self.req.with_name('design.md')
        self.rows=[{'type':'design','status':'proposed','id':'APP-D1','_file':'docs/upstream/design.md'}]
        self.write()

    def write(self):
        text=MARKER+'\n# Design\n## 目的\nA unit fixture.\n'
        for i,title in enumerate(('全体','コンポーネント','処理'),1):
            text+=f'## {title}\n```mermaid\nflowchart LR\n A{i}[入力] -->|データ| B{i}[結果]\n```\n図{i}の読み方：テスト例。\n'
        text+='## フレームワーク\nUnit-test fixture.\n```design-research\n'+json.dumps(self.binding)+'\n```\n'
        self.design.write_text(text)

    def inspect(self, phase='ready'):
        return inspect_design_documents(self.root,self.rows,phase,'docs/upstream/requirements.md')

    def test_contract_accepts_current_bound_input(self):self.assertEqual(self.inspect(),[])
    def test_missing_research_blocks_ready_not_draft(self):
        self.binding['runs']=[];self.write()
        self.assertEqual(self.inspect()[0]['severity'],'error')
        self.assertEqual(self.inspect('draft')[0]['severity'],'warning')
    def test_changed_requirements_invalidate_basis(self):
        self.req.write_text('New unit requirement.');self.assertTrue(self.inspect())
    def test_changed_report_invalidates_basis(self):
        self.report.write_text('Edited report.');self.assertTrue(self.inspect())
    def test_gate_dependencies_include_research(self):
        files=dependency_files(self.root,[self.design]);self.assertIn(self.path,files);self.assertIn(self.req,files)
    def test_legacy_document_is_not_rewritten(self):
        self.design.write_text('Previously approved legacy design.');self.assertEqual(self.inspect()[0]['severity'],'warning')
        self.assertEqual(self.design.read_text(),'Previously approved legacy design.')
    def test_screen_examples_need_skill_record(self):
        self.binding['uiux']['applicable']=True;self.write();self.assertTrue(self.inspect())
    def test_unknown_candidate_blocks_ready(self):
        self.binding['runs'][0]['decisions'][0]['candidate_id']='unknown';self.write();self.assertTrue(self.inspect())
