"""Offline contract tests with explicitly synthetic run records, not AI validation."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

PACKAGE=Path(__file__).resolve().parents[1]
SOURCE=Path(os.environ['UPGRADE_SOURCE_ROOT']) if os.environ.get('UPGRADE_SOURCE_ROOT') else PACKAGE/'overlay'
SCRIPTS=SOURCE/'tools/design-research/skill/scripts'
PRIOR=PACKAGE/'previous_report_upgrade/overlay/tools/design-research/skill/scripts'
sys.path[:0]=[str(SCRIPTS),str(PRIOR)]
import reassessment as reassess
import readable_report as reader
spec=importlib.util.spec_from_file_location('design_quality',SOURCE/'tools/speckit-upstream/workbench/design_quality.py')
quality=importlib.util.module_from_spec(spec);spec.loader.exec_module(quality)


def guide():
    return {**{k:'対象を知らない読者向けの説明。これは検証用の架空例です。' for k in reader.FIELDS},
            'diagram_source':'reader-guide','figures':[
      {'id':'F1','kind':'overview','title':'全体','caption':'設計例であり性能結果ではない。',
       'reading_guide':'入力が処理系へ渡る。','alt':'入力→処理系。',
       'nodes':[{'id':'Input','label':'入力'},{'id':'Core','label':'処理系'}],
       'edges':[{'from':'Input','to':'Core','label':'対象データ'}]},
      {'id':'F2','kind':'detail','parent_figure':'F1','expanded_component':'Core','title':'内部処理',
       'caption':'全体のCoreを拡大する。','reading_guide':'整形して比較する。','alt':'整形→比較。',
       'nodes':[{'id':'Normalize','label':'整形'},{'id':'Compare','label':'比較'}],
       'edges':[{'from':'Normalize','to':'Compare','label':'正規化した特徴'}]}]}


def dossier():
    roles=[{'candidate_id':f'C{i}','role':role,'mechanism':f'独立した原理{i}'}
           for i,role in enumerate(('incumbent','incremental','simpler','alternative','distant'))]
    roles[-1].update(difference='別分野の原理を転用する。',falsification='同一予算で効果がなければ棄却する。',
                     command='python compare.py --method distant',prerequisites='合成fixtureを用意する。',experiment_id='E1')
    return {'candidates':[{'id':f'C{i}'} for i in range(5)],'experiments':[{'id':'E1','status':'planned'}],
            'reader_guide':guide(),'reassessment':{
            **{k:'前回と今回を区別した、テスト用の説明。' for k in (
                'changed_conditions','retained_findings','invalidated_findings','comparability','decision_delta','next_experiment')},
            'candidate_roles':roles}}


def run_fixture(root):
    topic=root/'docs/design-research/previous'; run=topic/'runs/RUN001'
    req=root/'docs/upstream/requirements.md'; req.parent.mkdir(parents=True)
    req.write_text('# Requirements\nA synthetic requirement, not a user-approved decision.\n')
    snap=run/'inputs/bound-requirements.md';snap.parent.mkdir(parents=True);snap.write_bytes(req.read_bytes())
    report=run/'reports/report.md';report.parent.mkdir();report.write_text('# Report\nSynthetic test fixture.\n')
    state={'schema_version':1,'run_id':'RUN001','status':'research_complete','config':{'mode':'research'},
           'dossier':dossier(),'requirements_context':{
           'project_path':str(req.relative_to(root)),'snapshot':str(snap.relative_to(topic)),
           'sha256':quality.sha(req.read_bytes())}}
    path=run/'state.json';path.write_text(json.dumps(state,ensure_ascii=False))
    binding={'schema_version':1,'runs':[{'state':str(path.relative_to(root)),
             'report':str(report.relative_to(root)),'state_sha256':quality.sha(path.read_bytes()),
             'report_sha256':quality.sha(report.read_bytes()),'decisions':[
             {'design_id':'SYS-D1','candidate_id':'C0','rationale':'制約を満たす条件付き選定。'}]}],
             'uiux':{'applicable':False,'reason':'画面なしのバッチ処理。','artifacts':[]}}
    return path,state,binding


def design_text(binding):
    return quality.MARKER+'\n'+'''# 設計
## 目的
具体的な目的を記載する。
## 全体
```mermaid
flowchart LR
 A[利用者] -->|依頼| B[システム]
```
図1の読み方：境界を示す。
## コンポーネント
```mermaid
flowchart LR
 C[受付] -->|検証後| D[処理]
```
図2の読み方：システムの内部を示す。
## 処理
```mermaid
sequenceDiagram
 participant A
 participant B
 A->>B: 依頼
```
図3の読み方：操作の順を示す。
## フレームワーク
名称・版・役割・根拠を実ファイルから記載する。
```design-research
'''+json.dumps(binding,ensure_ascii=False)+'\n```\n'


class ReaderTests(unittest.TestCase):
    def setUp(self):self.state={'config':{'reader_friendly':True}};self.d=dossier()
    def test_valid(self):self.assertEqual(reader.quality_issues(self.d,self.state),[])
    def test_legacy_unchanged(self):self.assertEqual(reader.sections({'config':{}}),[])
    def test_missing_guide(self):self.assertTrue(reader.quality_issues({},self.state))
    def test_empty_explanation(self):
        self.d['reader_guide']['purpose']='';self.assertTrue(reader.quality_issues(self.d,self.state))
    def test_missing_detail(self):
        self.d['reader_guide']['figures'][1]['kind']='comparison';self.assertTrue(reader.quality_issues(self.d,self.state))
    def test_unknown_edge(self):
        self.d['reader_guide']['figures'][1]['edges'][0]['to']='Unknown';self.assertTrue(reader.quality_issues(self.d,self.state))
    def test_unknown_parent(self):
        self.d['reader_guide']['figures'][1]['parent_figure']='F9';self.assertTrue(reader.quality_issues(self.d,self.state))
    def test_unknown_expanded_component(self):
        self.d['reader_guide']['figures'][1]['expanded_component']='Missing';self.assertTrue(reader.quality_issues(self.d,self.state))
    def test_duplicate_graph(self):
        f=deepcopy(self.d['reader_guide']['figures'][0]);f.update(id='F2',kind='detail',parent_figure='F1',expanded_component='Core')
        self.d['reader_guide']['figures'][1]=f;self.assertTrue(reader.quality_issues(self.d,self.state))
    def test_syntax_injection_id(self):
        self.d['reader_guide']['figures'][0]['nodes'][0]['id']='X] click X';self.assertTrue(reader.quality_issues(self.d,self.state))
    def test_labels_escaped(self):self.assertNotIn('"',reader.mermaid_label('a"\n<script>'))
    def test_overview_before_detail(self):
        self.d['reader_guide']['figures'].reverse();self.state['dossier']=self.d
        out='\n'.join(reader.sections(self.state));self.assertLess(out.index('図1. 全体'),out.index('図2. 内部'))
    def test_stopped_draft_not_success(self):
        text='\n'.join(reader.sections(self.state));self.assertIn('未完成',text);self.assertNotIn('```mermaid',text)
    def test_reassessment_delta_render(self):
        self.state.update(dossier=self.d,reassessment_context={'run_id':'OLD'})
        self.assertIn('今回の実測', '\n'.join(reader.sections(self.state)))
    def test_malformed_types_return_findings(self):
        self.d['reader_guide']['figures']=[[],{}];self.assertTrue(reader.quality_issues(self.d,self.state))
    def test_existing_proposal_figures_reused(self):
        # Actual previous proposal validator, with its explicitly synthetic complete fixture.
        sys.path.insert(0, str(PACKAGE/'previous_report_upgrade/tests'))
        sp=importlib.util.spec_from_file_location('proposal_fixtures',PACKAGE/'previous_report_upgrade/tests/fixtures.py')
        fixtures=importlib.util.module_from_spec(sp);sp.loader.exec_module(fixtures)
        d=fixtures.fixture();d['reader_guide']=guide();d['reader_guide'].update(diagram_source='proposed-method',figures=[])
        state={'config':{'reader_friendly':True,'report_profile':'proposed-method','target_methods':5},'dossier':d}
        self.assertEqual(reader.quality_issues(d,state),[])
        out='\n'.join(reader.sections(state));self.assertNotIn('```mermaid',out);self.assertIn('提案手法',out)

    def test_audit_has_truthful_scope_diagram_without_research_quota(self):
        state={'config':{'mode':'audit','reader_friendly':True,'brief':'入力エラーを確認'},
               'iteration':1,'evidence':{},'plan':{'goal':'入力エラーを確認','baseline':'現行実装'}}
        self.assertEqual(reader.quality_issues({},state),[])
        text='\n'.join(reader.sections(state))
        self.assertIn('```mermaid',text);self.assertIn('実行記録 0 件',text);self.assertIn('レビュー未成立',text)
        self.assertNotIn('reader_guide with',reader.instructions('reviewer',state))

    def test_placeholder_explanation_rejected(self):
        self.d['reader_guide']['purpose']='TBD'
        self.assertTrue(reader.quality_issues(self.d,self.state))

    def test_fewer_reader_candidates_need_reason(self):
        self.d['candidates']=self.d['candidates'][:3]
        self.d.pop('reassessment')
        self.assertTrue(reader.quality_issues(self.d,self.state))
        self.d['reader_guide']['comparison_exception']='対象に適用可能な3方式へ絞る。'
        self.assertEqual(reader.quality_issues(self.d,self.state),[])


class ReassessmentTests(unittest.TestCase):
    def test_complete_previous_fresh_slug(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p,_,_=run_fixture(root);c=reassess.load_previous(root,str(p),'new')
            self.assertEqual(c['evidence_status'],'historical_context_only');reassess.assert_unchanged(c,root)
    def test_old_topic_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p,_,_=run_fixture(root)
            with self.assertRaises(ValueError):reassess.load_previous(root,str(p),'previous')
    def test_existing_new_topic_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p,_,_=run_fixture(root);(root/'docs/design-research/new').mkdir()
            with self.assertRaises(ValueError):reassess.load_previous(root,str(p),'new')
    def test_incomplete_previous_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p,s,_=run_fixture(root);s['status']='blocked';p.write_text(json.dumps(s))
            with self.assertRaises(ValueError):reassess.load_previous(root,str(p),'new')
    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p,_,_=run_fixture(root);alias=root/'alias.json';alias.symlink_to(p)
            with self.assertRaises(ValueError):reassess.load_previous(root,str(alias),'new')
    def test_path_escape_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            with self.assertRaises(ValueError):reassess.load_previous(root,'../state.json','new')
    def test_changed_previous_detected_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p,_,_=run_fixture(root);c=reassess.load_previous(root,str(p),'new');p.write_text('changed')
            with self.assertRaises(ValueError):reassess.assert_unchanged(c,root)
            self.assertEqual(p.read_text(),'changed')
    def test_snapshot_requirements_bound(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,_,_=run_fixture(root);w=root/'docs/design-research/new';r=w/'runs/NEW'
            c=reassess.snapshot_requirements(types.SimpleNamespace(requirements='docs/upstream/requirements.md'),root,r,w)
            reassess.check_requirements(c,root,w)
            (root/c['project_path']).write_text('changed')
            with self.assertRaises(ValueError):reassess.check_requirements(c,root,w)
    def test_children_cannot_recurse(self):
        with patch.dict(os.environ,{'DR_GAN_CHILD':'1'}):
            with self.assertRaises(ValueError):reassess.main([])
    def test_valid_five_and_distant_planned(self):
        self.assertEqual(reassess.quality_issues(dossier(),{'reassessment_context':{'run_id':'OLD'},'config':{}}),[])
    def test_distant_required(self):
        d=dossier();d['reassessment']['candidate_roles'][-1]['role']='alternative'
        self.assertTrue(reassess.quality_issues(d,{'reassessment_context':True,'config':{}}))
    def test_distinct_mechanism_required(self):
        d=dossier();d['reassessment']['candidate_roles'][-1]['mechanism']='独立した原理0'
        self.assertTrue(reassess.quality_issues(d,{'reassessment_context':True,'config':{}}))
    def test_executable_plan_required(self):
        d=dossier();d['reassessment']['candidate_roles'][-1]['command']=''
        self.assertTrue(reassess.quality_issues(d,{'reassessment_context':True,'config':{}}))
    def test_experiment_reference_required(self):
        d=dossier();d['reassessment']['candidate_roles'][-1]['experiment_id']='NOPE'
        self.assertTrue(reassess.quality_issues(d,{'reassessment_context':True,'config':{}}))
    def test_fewer_with_reason(self):
        d=dossier();del d['candidates'][2];del d['reassessment']['candidate_roles'][2]
        state={'reassessment_context':True,'config':{}}
        self.assertTrue(reassess.quality_issues(d,state));d['reassessment']['comparison_exception']='予算内に有効な4原理を比較する。'
        self.assertEqual(reassess.quality_issues(d,state),[])
    def test_malformed_candidate_role(self):
        d=dossier();d['reassessment']['candidate_roles'][-1]['role']=[]
        self.assertTrue(reassess.quality_issues(d,{'reassessment_context':True,'config':{}}))

    def test_incumbent_must_reference_real_previous_candidate(self):
        d=dossier();context={'previous_dossier':{'candidates':[{'id':'OLD'}],'decision':{'candidate_id':'OLD'}}}
        state={'config':{},'reassessment_context':context}
        self.assertTrue(reassess.quality_issues(d,state))
        d['reassessment']['candidate_roles'][0]['previous_candidate_id']='OLD'
        self.assertEqual(reassess.quality_issues(d,state),[])
        d['reassessment']['candidate_roles'][0]['previous_candidate_id']='OTHER'
        self.assertTrue(reassess.quality_issues(d,state))


class DesignGateTests(unittest.TestCase):
    def test_valid_binding(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,_,b=run_fixture(root)
            self.assertEqual(len(quality.validate_binding(root,b,{'SYS-D1'})),4)
    def test_canonical_requirements(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,_,b=run_fixture(root)
            with self.assertRaisesRegex(ValueError,'canonical'):quality.validate_binding(root,b,{'SYS-D1'},'other.md')
    def test_stale_requirements(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,_,b=run_fixture(root);(root/'docs/upstream/requirements.md').write_text('changed')
            with self.assertRaisesRegex(ValueError,'stale'):quality.validate_binding(root,b,{'SYS-D1'})
    def test_missing_research_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):quality.validate_binding(Path(t),{'runs':[]},{'SYS-D1'})
    def test_wrong_run_report(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,_,b=run_fixture(root);b['runs'][0]['report']='docs/design-research/previous/report.md'
            with self.assertRaisesRegex(ValueError,'archived'):quality.validate_binding(root,b,{'SYS-D1'})
    def test_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,_,b=run_fixture(root);b['runs'][0]['state_sha256']='bad'
            with self.assertRaisesRegex(ValueError,'hash'):quality.validate_binding(root,b,{'SYS-D1'})
    def test_unknown_candidate(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,_,b=run_fixture(root);b['runs'][0]['decisions'][0]['candidate_id']='MISSING'
            with self.assertRaises(ValueError):quality.validate_binding(root,b,{'SYS-D1'})
    def test_unmapped_design(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,_,b=run_fixture(root)
            with self.assertRaises(ValueError):quality.validate_binding(root,b,{'SYS-D1','SYS-D2'})
    def test_ui_skill_and_artifact_required(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,_,b=run_fixture(root);b['uiux']['applicable']=True
            with self.assertRaises(ValueError):quality.validate_binding(root,b,{'SYS-D1'})
            b['uiux'].update(skill='ooui-design',review_notes='入力保持を確認。',artifacts=['mock.png']);(root/'mock.png').write_bytes(b'\x89PNG fixture')
            self.assertIn(root/'mock.png',quality.validate_binding(root,b,{'SYS-D1'}))
    def test_ui_cannot_bypass(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,_,b=run_fixture(root);b['uiux']['artifacts']=['mock.png']
            with self.assertRaises(ValueError):quality.validate_binding(root,b,{'SYS-D1'})
    def test_progressive_document(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,_,b=run_fixture(root);text=design_text(b)
            self.assertEqual(quality.document_issues(root,text),[])
    def test_diagrams_missing(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertTrue(quality.document_issues(Path(t),'# Design\n## Purpose\nText.'))
    def test_dependencies_include_all(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,_,b=run_fixture(root);p=root/'design.md';p.write_text(design_text(b))
            self.assertEqual(len(quality.dependency_files(root,[p])),4)
    def test_gate_ready_and_draft(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,_,b=run_fixture(root);p=root/'design.md';p.write_text(design_text(b))
            rows=[{'id':'SYS-D1','type':'design','status':'proposed','_file':'design.md'}]
            self.assertEqual(quality.inspect_design_documents(root,rows,'ready'),[])
            b['runs']=[];p.write_text(design_text(b))
            self.assertEqual(quality.inspect_design_documents(root,rows,'draft')[0]['severity'],'warning')
            self.assertEqual(quality.inspect_design_documents(root,rows,'ready')[0]['severity'],'error')
    def test_legacy_not_auto_migrated(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);p=root/'design.md';p.write_text('An existing approved design.')
            rows=[{'id':'SYS-D1','type':'design','status':'approved','_file':'design.md'}]
            self.assertEqual(quality.inspect_design_documents(root,rows,'ready')[0]['severity'],'warning')
            self.assertEqual(p.read_text(),'An existing approved design.')
    def test_retired_ignored(self):
        self.assertEqual(quality.inspect_design_documents(Path('/missing'),[{'id':'D','type':'design','status':'retired'}]),[])
    def test_public_url_not_a_local_run(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):quality.local_file(Path(t),'https://example.org/state.json')
    def test_parent_path_escape(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):quality.local_file(Path(t),'../private/state.json')


if __name__=='__main__':unittest.main()
