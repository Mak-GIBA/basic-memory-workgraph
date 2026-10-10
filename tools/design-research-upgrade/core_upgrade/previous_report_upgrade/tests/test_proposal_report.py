from __future__ import annotations
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[1]
SCRIPTS = next(path for parent in Path(__file__).resolve().parents
               for path in (parent/'overlay/tools/design-research/skill/scripts', parent/'tools/design-research/skill/scripts')
               if (path/'proposal_report.py').is_file())
sys.path.insert(0,str(SCRIPTS))
try:
    from .fixtures import fixture
except ImportError:
    from fixtures import fixture
import proposal_report as report
import method_workflow as workflow


class ReportTests(unittest.TestCase):
    def test_japanese_font_and_portable_arrow_labels(self):
        f=fixture()['method_ideas']['candidates'][2]['presentation']['figures'][0]
        output=report.svg(f).decode('utf-8')
        self.assertIn('Noto Sans CJK JP',output)
        self.assertNotIn('paint-order',output)
        for edge in f['edges']:
            self.assertIn(report.html.escape(edge['label']),output)

    def test_architecture_must_cover_all_components(self):
        d=fixture();p=d['method_ideas']['candidates'][2]['presentation']
        f=p['figures'][0]
        f['component_ids'].remove('M2')
        for node in f['nodes']:
            if node['component_id']=='M2':node['component_id']=''
        self.assertTrue(any('cover every described component' in e for e in report.validation_issues(d)))

    def test_identical_graphs_do_not_pad_required_figures(self):
        d=fixture();p=d['method_ideas']['candidates'][2]['presentation']
        p['figures'][1]['nodes']=deepcopy(p['figures'][0]['nodes'])
        p['figures'][1]['edges']=deepcopy(p['figures'][0]['edges'])
        p['figures'][1]['component_ids']=deepcopy(p['figures'][0]['component_ids'])
        self.assertTrue(any('identical graphs' in e for e in report.validation_issues(d)))

    def test_complete_fixture_and_five_methods(self):
        d=fixture()
        self.assertEqual(report.validation_issues(d),[])
        self.assertEqual(len(d['candidates']),5)

    def test_missing_selected_presentation_is_incomplete(self):
        d=fixture();del d['method_ideas']['candidates'][2]['presentation']
        self.assertTrue(any('Methods chapter' in e for e in report.validation_issues(d)))

    def test_missing_diagram_kind_is_rejected(self):
        d=fixture();d['method_ideas']['candidates'][2]['presentation']['figures'].pop()
        self.assertTrue(any('baseline_comparison' in e for e in report.validation_issues(d)))

    def test_dangling_component_or_edge_is_rejected(self):
        for part in ['component','edge']:
            d=fixture();f=d['method_ideas']['candidates'][2]['presentation']['figures'][0]
            if part=='component':f['nodes'][0]['component_id']='BAD'
            else:f['edges'][0]['to']='BAD'
            self.assertTrue(report.validation_issues(d),part)

    def test_cycle_must_be_explicit_feedback(self):
        d=fixture();f=d['method_ideas']['candidates'][2]['presentation']['figures'][1]
        f['edges'].append(dict(**{'from':'S','to':'N'},label='feedback',kind='flow'))
        self.assertTrue(any('cycle' in e for e in report.validation_issues(d)))
        f['edges'][-1]['kind']='feedback'
        self.assertEqual(report.validation_issues(d),[])
        image=report.svg(f).decode();self.assertIn('stroke-dasharray',image)

    def test_orphan_and_duplicate_arrow_are_rejected(self):
        d=fixture();f=d['method_ideas']['candidates'][2]['presentation']['figures'][0]
        f['edges'].append(deepcopy(f['edges'][0]))
        self.assertTrue(any('duplicate arrow' in e for e in report.validation_issues(d)))
        f['edges']=f['edges'][:-1];f['edges']=[e for e in f['edges'] if e['from']!='Q']
        self.assertTrue(any('disconnected' in e for e in report.validation_issues(d)))

    def test_source_identity_read_depth_and_experiment_links(self):
        for key in ('source','depth','experiment','candidate'):
            d=fixture()
            if key=='source':d['sources'][0]['url']='https://different.invalid'
            if key=='depth':d['sources'][0]['read_level']='abstract'
            if key=='experiment':d['experiments']=[]
            if key=='candidate':d['candidates'].pop()
            self.assertTrue(report.validation_issues(d),key)

    def test_comparison_target_is_frozen_and_exception_is_allowed(self):
        d=fixture();self.assertTrue(any('frozen target' in e for e in report.validation_issues(d,target_methods=6)))
        d['candidates'].pop();d['method_ideas']['candidates'].pop()
        d['method_ideas']['selection']['rejected_candidate_ids']=['P1','P2']
        self.assertTrue(report.validation_issues(d))
        d['method_ideas']['comparison_plan']['exception_reason']='Fixed compute budget and available evidence support only three distinct alternatives without cosmetic padding.'
        self.assertEqual(report.validation_issues(d),[])

    def test_symbols_and_equation_explanation_required(self):
        for key in ['symbols','equation_explanation']:
            d=fixture();p=d['method_ideas']['candidates'][2]['presentation'];p[key]=[] if key=='symbols' else ''
            self.assertTrue(report.validation_issues(d),key)

    def test_pseudocode_only_with_reason_is_allowed(self):
        d=fixture();c=d['method_ideas']['candidates'][2]
        c['mathematical_specification']='';c['presentation']['symbols']=[]
        c['presentation']['formalism_note']='この条件分岐手法は擬似コードで仕様を定義し、独立の数式を追加しない。'
        self.assertEqual(report.validation_issues(d),[])
        c['pseudocode']=''
        self.assertTrue(report.validation_issues(d))

    def test_placeholders_do_not_count_as_explanation(self):
        d=fixture();d['method_ideas']['candidates'][2]['presentation']['overview']='TODO'
        self.assertTrue(any('placeholders' in e for e in report.validation_issues(d)))

    def test_malformed_values_fail_closed_without_crash(self):
        variations=[None,[],False,{'method_ideas':[]},fixture()]
        variations[-1]['method_ideas']['candidates'][2]['presentation']['figures'][0]['kind']={}
        for d in variations:self.assertTrue(report.validation_issues(d))
        d=fixture();d['method_ideas']['schema_version']=True
        self.assertTrue(report.validation_issues(d))

    def test_svg_has_actual_text_and_no_active_xml(self):
        d=fixture();f=d['method_ideas']['candidates'][2]['presentation']['figures'][0]
        f['nodes'][0]['label']='<script>do_not_run()</script>'
        out=report.svg(f);tree=ET.fromstring(out)
        self.assertFalse(tree.findall('.//{http://www.w3.org/2000/svg}script'))
        self.assertIn('&lt;script&gt;',out.decode())
        self.assertIn('aria-labelledby',out.decode())

    def test_svg_boxes_stay_in_viewbox_and_do_not_overlap(self):
        for f in fixture()['method_ideas']['candidates'][2]['presentation']['figures']:
            tree=ET.fromstring(report.svg(f));w,h=float(tree.attrib['width']),float(tree.attrib['height'])
            rects=[]
            for r in tree.findall('.//{http://www.w3.org/2000/svg}rect'):
                if 'rx' not in r.attrib:continue
                x,y,rw,rh=[float(r.attrib[k]) for k in ['x','y','width','height']]
                self.assertTrue(0<=x<x+rw<=w and 0<=y<y+rh<=h)
                for a,b,c,d in rects:self.assertTrue(x+rw<=a or a+c<=x or y+rh<=b or b+d<=y)
                rects.append((x,y,rw,rh))

    def test_rendered_chapter_is_detailed_and_files_exist(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);lines=report.render_chapter(fixture(),root,root/'runs/r1/method-figures')
            body='\n'.join(lines)
            for title in ['## 提案手法','ねらいと直感','構成要素の詳細','記号・定式化','既存法との差分','仮説と検証実験','未測定','全5手法']:
                self.assertIn(title,body)
            paths=re.findall(r'!\[[^\n]*?\]\(([^)]+)\)',body)
            self.assertEqual(len(paths),3)
            for path in paths:self.assertTrue((root/path).is_file())
            self.assertIn('平均',body)

    def test_draft_still_has_mandatory_chapter_but_no_fake_figures(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);body='\n'.join(report.render_chapter({},root,root/'figures'))
            self.assertIn('## 提案手法',body);self.assertIn('未完成',body)
            self.assertNotIn('![',body);self.assertFalse((root/'figures').exists())

    def test_immutable_files_and_revision_paths(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);d=fixture();report.render_chapter(d,root,root/'figures')
            before={p:p.read_bytes() for p in root.rglob('*.svg')}
            report.render_chapter(d,root,root/'figures')
            d['method_ideas']['candidates'][2]['presentation']['overview']+=' 設計を改訂した。'
            report.render_chapter(d,root,root/'figures')
            self.assertEqual(len(list(root.rglob('*.svg'))),6)
            for p,content in before.items():self.assertEqual(p.read_bytes(),content)
            path=next(iter(before));path.write_bytes(b'changed')
            with self.assertRaises(ValueError):report.render_chapter(fixture(),root,root/'figures')

    def test_symlink_and_outside_workspace_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'link').symlink_to(root/'outside')
            with self.assertRaises(ValueError):report.render_chapter(fixture(),root,root/'link')
            with self.assertRaises(ValueError):report.render_chapter(fixture(),root,root.parent/'outside')

    def test_producer_preview_is_generated_before_review(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);run=root/'runs/r1';run.mkdir(parents=True)
            state={'config':{'mode':'research','report_profile':'proposed-method','target_methods':5},'proposal':{'dossier_json':json.dumps(fixture(),ensure_ascii=False)}}
            report.prepare_preview(state,root,run)
            preview=state['method_report_preview'];self.assertEqual(preview['status'],'rendered')
            doc=root/preview['path'];self.assertTrue(doc.is_file())
            for ref in re.findall(r'\]\(([^)]+)\)',doc.read_text()):self.assertTrue((doc.parent/ref).is_file())
            self.assertEqual(len(list(run.rglob('*.svg'))),3)
            self.assertNotIn('evidence',state)

    def test_invalid_preview_is_not_forged(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);state={'config':{'mode':'research','report_profile':'proposed-method'},'proposal':{'dossier_json':'{}'}}
            report.prepare_preview(state,root,root/'run')
            self.assertEqual(state['method_report_preview']['status'],'incomplete')
            self.assertEqual(list(root.rglob('*.svg')),[])

    def test_old_runs_audits_and_comparison_mode_unchanged(self):
        for conf in [{'mode':'research'},{'mode':'audit','report_profile':'proposed-method'},{'mode':'run'},{'mode':'research','report_profile':'comparison'}]:
            state={'config':conf}
            self.assertFalse(report.method_required(state))
            self.assertEqual(workflow.role_instructions('producer',state),'')
            self.assertEqual(workflow.additional_gate_reasons(state),[])
            self.assertEqual(report.render_chapter({},'.','figures',required=False),[])

    def test_profile_instructions_and_completion_gate(self):
        state={'config':{'mode':'research','report_profile':'proposed-method','target_methods':5},'dossier':fixture()}
        self.assertIn('approximately 5',workflow.role_instructions('producer',state))
        self.assertEqual(workflow.additional_gate_reasons(state),[])
        state['dossier']['method_ideas']['candidates'][2]['presentation']['figures']=[]
        self.assertTrue(workflow.additional_gate_reasons(state))

    def test_runtime_reviewer_rejects_incomplete_design(self):
        class Blocked(Exception):pass
        runtime=types.ModuleType('runtime');runtime.Blocked=Blocked
        state={'config':{'mode':'research','report_profile':'proposed-method','target_methods':5}}
        with patch.dict(sys.modules,{'runtime':runtime}):
            report.require_method_report(fixture(),state)
            self.assertTrue(state['method_report_validation']['valid'])
            with self.assertRaises(Blocked):report.require_method_report({},state)
            self.assertFalse(state['method_report_validation']['valid'])

    def test_negative_decision_does_not_require_a_winning_proposal(self):
        d=fixture();d['decision']['candidate_id']='BASE'
        d['decision']['rationale']='比較が未完了のため既存法を維持する。'
        d['method_ideas']['candidates'][2]['presentation']['selection_note']='未評価の設計を説明するが、現段階の採用判断は既存法維持である。'
        self.assertEqual(report.validation_issues(d),[])

    def test_cli_strict_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);file=root/'input.json';out=root/'report.md';cli=SCRIPTS/'proposal_report.py'
            file.write_text(json.dumps(fixture(),ensure_ascii=False))
            cmd=[sys.executable,str(cli),'render',str(file),'--out',str(out),'--strict']
            r=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
            r=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(r.returncode,2)
            file.write_text('{}');out.unlink()
            r=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(r.returncode,1)
            self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
