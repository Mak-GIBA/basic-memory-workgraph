"""Offline work-package tests; run records are explicitly synthetic fixtures."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

P = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ['UPGRADE_SOURCE_ROOT']) if os.environ.get('UPGRADE_SOURCE_ROOT') else P/'overlay'
sys.path.insert(0, str(ROOT/'tools/design-research/skill/scripts'))
import research_workstreams as w
spec = importlib.util.spec_from_file_location('workstream_design_quality', ROOT/'tools/speckit-upstream/workbench/design_quality.py')
q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)


def plan_fixture():
    tasks = []
    for n, title in enumerate(('候補抽出の漏れを減らす', '検索順位を改善する', '組合せの速度を改善する'), 1):
        task = {'id': f'RP{n}', 'slug': f'logic-{n}', 'title': title,
                'requirement_ids': ['SYS-R1' if n < 3 else 'SYS-R2'],
                'question': title+'には、どの方式が制約内で有効か。',
                'rationale': '要件達成を左右する不確実な計算・判断処理である。',
                'baseline': '現行方式。比較前に版とデータを固定する。',
                'boundary': '対象の入出力変換だけ。UIやAPIの再設計は含めない。',
                'input_contract_ids': ['C1'], 'output_contract_ids': ['C1'],
                'acceptance': '固定した評価セットで主指標とガードレールを確認する。',
                'test_plan': '同じデータと予算で比較し、必要な反証実験を行う。',
                'depends_on': [], 'dependency_reasons': {}, 'target_methods': 5,
                'mode': 'research', 'exclusive_resources': [],
                'allocation': {'provider_requests': 3 if n<3 else 2, 'experiments': 1, 'gpu_slots': 0}}
        tasks.append(task)
    tasks[2]['depends_on'] = ['RP1', 'RP2']
    tasks[2]['dependency_reasons'] = {'RP1': '選んだ候補抽出の出力で測る。', 'RP2': '選んだ順位付けの出力で測る。'}
    return {'schema_version': 1,
            'requirements': {'path': 'docs/upstream/requirements.md', 'sha256': '0'*64,
              'items': [{'id': 'SYS-R1', 'disposition': 'research', 'reason': '精度の達成方式が未確定。', 'workstream_ids': ['RP1','RP2']},
                        {'id': 'SYS-R2', 'disposition': 'research', 'reason': '応答時間との両立を検討。', 'workstream_ids': ['RP3']},
                        {'id': 'SYS-R3', 'disposition': 'standard', 'reason': '監査ログは既存の確定仕様を使う。', 'workstream_ids': []}]},
            'contracts': [{'id': 'C1', 'version': 'fixture-v1', 'definition': '固定入力と候補ID、スコアのスキーマ。テスト用。'}],
            'budget': {'provider_requests': 8, 'experiments': 3, 'max_parallel': 2, 'gpu_slots': 1, 'isolation': 'isolated-projects'},
            'workstreams': tasks,
            'integration': {'requirement_ids': ['SYS-R1','SYS-R2','SYS-R3'], 'owner': '親のupstream担当',
                'combination_checks': '現行全体と選定部品の組合せを比較する。',
                'end_to_end_acceptance': '検索結果の品質と最終応答時間を同時に確認する。',
                'budget_checks': 'GPU・メモリ・利用コストの総量を確認する。',
                'conflict_resolution': '部分最適を採用せず、衝突時は関連テーマへ差し戻す。'}}


def write_plan(root, plan):
    req = root/plan['requirements']['path']; req.parent.mkdir(parents=True, exist_ok=True)
    if not req.exists():
        req.write_text('# Synthetic requirements\n'+'\n'.join('```upstream\n'+json.dumps({'id':r['id'],'type':'requirement'})+'\n```' for r in plan['requirements']['items']))
    plan['requirements']['sha256'] = w.digest(req.read_bytes())
    name = '.specify/workbench/research-plan.json'
    path = root/name; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False))
    return name


def binding_fixture(root):
    plan = plan_fixture(); name = write_plan(root, plan)
    binding = {'schema_version': 2, 'workstream_plan': {'path': name, 'sha256': w.digest((root/name).read_bytes())}, 'runs': [],
       'standard_decisions': [{'design_id': 'SYS-D2', 'requirement_ids':['SYS-R3'], 'reason':'既存仕様の継続。', 'evidence':['docs/standard.md']}],
       'integration': {'status':'planned','rationale':'個別結果の後で全体を測る。', 'selected_combination':'RP1とRP2の選定を組み合わせRP3で検証。',
                       'tradeoffs':'精度と速度を同時に満たす。', 'verification_ids':['SYS-V1'], 'artifacts':[]},
       'uiux': {'applicable':False,'reason':'バックエンド計算だけのテストfixture。','artifacts':[]}}
    (root/'docs/standard.md').write_text('Synthetic standard design evidence.\n')
    for task in plan['workstreams']:
        workspace = root/'docs/design-research'/task['slug']; run = workspace/'runs'/task['id']
        args = types.SimpleNamespace(workstream_plan=name, workstream_id=task['id'], requirements=plan['requirements']['path'], slug=task['slug'],mode='research',target_methods=5)
        context = w.snapshot_task(args,root,run,workspace)
        snap=run/'inputs/bound-requirements.md'; snap.write_bytes((root/args.requirements).read_bytes())
        state={'schema_version':1,'run_id':task['id'],'status':'research_complete', 'config':{'mode':'research','project':str(root)},
               'workstream_context':context, 'dossier':{'candidates':[{'id':'A'}]},
               'requirements_context':{'project_path':args.requirements,'snapshot':snap.relative_to(workspace).as_posix(),'sha256':w.digest(snap.read_bytes())}}
        path=run/'state.json';path.write_text(json.dumps(state))
        report=run/'reports/report.md';report.parent.mkdir();report.write_text('# Synthetic test result\n')
        binding['runs'].append({'workstream_id':task['id'], 'state':path.relative_to(root).as_posix(), 'report':report.relative_to(root).as_posix(),
           'state_sha256':w.digest(path.read_bytes()),'report_sha256':w.digest(report.read_bytes()),
           'decisions':[{'design_id':'SYS-D1','candidate_id':'A','rationale':'複数の研究結果を1つの全体設計に統合する。'}]})
    return plan, binding


class WorkstreamPlanTests(unittest.TestCase):
    def setUp(self): self.p=plan_fixture()
    def test_5_methods_per_logic_not_five_topics(self):
        self.assertEqual(len(w.validate_plan(self.p)['workstreams']),3)
        self.assertTrue(all(t['target_methods']==5 for t in self.p['workstreams']))
    def test_independent_research_waves(self): self.assertEqual(w.execution_waves(self.p),[['RP1','RP2'],['RP3']])
    def test_shared_project_lock_remains_serial(self):
        self.p['budget']['isolation']='same-project-serial'; self.assertEqual(w.execution_waves(self.p),[['RP1'],['RP2'],['RP3']])
    def test_max_parallel_one(self):
        self.p['budget']['max_parallel']=1; self.assertEqual(len(w.execution_waves(self.p)),3)
    def test_gpu_contention_serializes(self):
        for task in self.p['workstreams']:task['allocation']['gpu_slots']=1
        self.assertEqual(len(w.execution_waves(self.p)),3)
    def test_exclusive_shared_resource_serializes(self):
        for task in self.p['workstreams']:task['exclusive_resources']=['benchmark-port']
        self.assertEqual(len(w.execution_waves(self.p)),3)
    def test_unknown_requirement_refused(self):
        self.p['workstreams'][0]['requirement_ids']=['MISSING']
        with self.assertRaises(ValueError):w.validate_plan(self.p)
    def test_uncovered_requirement_refused(self):
        self.p['requirements']['items'][0]['workstream_ids']=[]
        with self.assertRaises(ValueError):w.validate_plan(self.p)
    def test_no_forced_research_for_standard_logic(self):
        self.assertEqual(w.validate_plan(self.p)['requirements']['items'][2]['workstream_ids'],[])
    def test_unnecessary_task_for_standard_requirement_refused(self):
        self.p['workstreams'][0]['requirement_ids'].append('SYS-R3')
        with self.assertRaises(ValueError):w.validate_plan(self.p)
    def test_cyclic_dependencies_refused(self):
        self.p['workstreams'][0].update(depends_on=['RP3'],dependency_reasons={'RP3':'循環する入力。'})
        with self.assertRaisesRegex(ValueError,'Cyclic'):w.validate_plan(self.p)
    def test_no_unknown_dependencies(self):
        self.p['workstreams'][0]['depends_on']=['MISSING']
        with self.assertRaises(ValueError):w.validate_plan(self.p)
    def test_runtime_pipeline_not_automatically_research_dependency(self):
        self.p['workstreams'][1]['depends_on']=['RP1']
        with self.assertRaises(ValueError):w.validate_plan(self.p)
    def test_shared_contract_required_for_dependency(self):
        self.p['contracts'].append({'id':'C2','definition':'異なる型。','version':'fixture'})
        self.p['workstreams'][2]['input_contract_ids']=['C2']
        with self.assertRaisesRegex(ValueError,'input contract'):w.validate_plan(self.p)
    def test_aggregate_query_budget(self):
        self.p['budget']['provider_requests']=7
        with self.assertRaisesRegex(ValueError,'budget'):w.validate_plan(self.p)
    def test_aggregate_experiment_budget(self):
        self.p['budget']['experiments']=2
        with self.assertRaises(ValueError):w.validate_plan(self.p)
    def test_compare_target_changes_need_reason(self):
        self.p['workstreams'][0]['target_methods']=3
        with self.assertRaises(ValueError):w.validate_plan(self.p)
        self.p['workstreams'][0]['method_count_reason']='適用可能な原理が3つのため。';w.validate_plan(self.p)
    def test_integration_acceptance_required(self):
        self.p['integration']['end_to_end_acceptance']=''
        with self.assertRaises(ValueError):w.validate_plan(self.p)
    def test_integration_covers_all_requirements(self):
        self.p['integration']['requirement_ids'].pop()
        with self.assertRaises(ValueError):w.validate_plan(self.p)
    def test_duplicate_topic_refused(self):
        self.p['workstreams'][1]['slug']='logic-1'
        with self.assertRaises(ValueError):w.validate_plan(self.p)
    def test_reassess_needs_actual_prior_path(self):
        self.p['workstreams'][0]['mode']='reassess'
        with self.assertRaises(ValueError):w.validate_plan(self.p)
    def test_placeholder_refused(self):
        self.p['workstreams'][0]['question']='TODO'
        with self.assertRaises(ValueError):w.validate_plan(self.p)
    def test_render_does_not_claim_execution(self):
        output=w.render(self.p)
        self.assertIn('実行計画',output);self.assertIn('研究上の依存関係',output);self.assertIn('```mermaid',output)
    def test_invalid_sensitive_paths_refused(self):
        for path in ('../x','/tmp/x','.env','docs/../../x'):
            with self.subTest(path=path),self.assertRaises(ValueError):w.relative(path)
    def test_requirement_bytes_pin_and_inventory(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);name=write_plan(root,self.p);w.load_plan(root,name)
            (root/self.p['requirements']['path']).write_text('changed')
            with self.assertRaisesRegex(ValueError,'Requirements changed'):w.load_plan(root,name)
    def test_metadata_requirement_omission_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);name=write_plan(root,self.p)
            self.p['requirements']['items'].pop(); self.p['integration']['requirement_ids'].pop()
            (root/name).write_text(json.dumps(self.p))
            with self.assertRaisesRegex(ValueError,'Inventory'):w.load_plan(root,name)
    def test_symlink_plan_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);name=write_plan(root,self.p);(root/'alias.json').symlink_to(root/name)
            with self.assertRaises(ValueError):w.load_plan(root,'alias.json')


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name);self.p,self.b=binding_fixture(self.root)
    def check(self):return q.validate_binding(self.root,self.b,{'SYS-D1','SYS-D2'},'docs/upstream/requirements.md')
    def test_many_runs_one_integrated_design(self): self.assertTrue(self.check())
    def test_missing_workstream_run_refused(self):
        self.b['runs'].pop()
        with self.assertRaises(ValueError):self.check()
    def test_unknown_workstream_run_refused(self):
        self.b['runs'][0]['workstream_id']='UNKNOWN'
        with self.assertRaises(ValueError):self.check()
    def test_changed_plan_refused(self):
        (self.root/self.b['workstream_plan']['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'stale'):self.check()
    def test_actual_run_context_not_just_label(self):
        entry=self.b['runs'][0];p=self.root/entry['state'];s=json.loads(p.read_text());s['workstream_context']['workstream_id']='RP2'
        p.write_text(json.dumps(s));entry['state_sha256']=w.digest(p.read_bytes())
        with self.assertRaises(ValueError):self.check()
    def test_combination_success_needs_evidence(self):
        self.b['integration']['status']='verified'
        with self.assertRaisesRegex(ValueError,'combined'):self.check()
    def test_standard_decision_needs_evidence(self):
        self.b['standard_decisions'][0]['evidence']=[]
        with self.assertRaises(ValueError):self.check()
    def test_standard_route_cannot_claim_research_requirement(self):
        self.b['standard_decisions'][0]['requirement_ids']=['SYS-R1']
        with self.assertRaises(ValueError):self.check()
    def test_snapshot_context_integrity(self):
        row=self.b['runs'][0];s=json.loads((self.root/row['state']).read_text());workspace=(self.root/row['state']).parents[2]
        w.assert_context(s,workspace)
        (workspace/s['workstream_context']['snapshot']).write_text('{}')
        with self.assertRaises(ValueError):w.assert_context(s,workspace)
    def test_bound_plan_in_gate_dependencies(self):
        path=self.root/'docs/upstream/design.md'
        path.write_text(q.WORKSTREAM_MARKER+'\n```design-research\n'+json.dumps(self.b)+'\n```\n')
        paths=q.dependency_files(self.root,[path])
        self.assertIn(self.root/self.b['workstream_plan']['path'],paths)
        self.assertIn(self.root/'docs/standard.md',paths)
    def test_snapshot_wrong_identity(self):
        args=types.SimpleNamespace(workstream_plan=self.b['workstream_plan']['path'], workstream_id='RP1',
             requirements='docs/upstream/requirements.md',slug='wrong-slug',mode='research',target_methods=5)
        with self.assertRaisesRegex(ValueError,'slug'):w.snapshot_task(args,self.root,self.root/'docs/design-research/new/runs/NEW',self.root/'docs/design-research/new')
    def test_missing_id_pair_rejected(self):
        args=types.SimpleNamespace(workstream_plan=self.b['workstream_plan']['path'])
        with self.assertRaises(ValueError):w.snapshot_task(args,self.root,self.root/'unused',self.root/'unused')
    def test_role_prompt_scopes_one_logic(self):
        prompt=w.role_instructions('producer',{'workstream_context':{'workstream_id':'RP1'}})
        self.assertIn('not the whole app',prompt);self.assertIn('Never start nested',prompt)
    def test_changed_context_contract_refused(self):
        row=self.b['runs'][0];s=json.loads((self.root/row['state']).read_text());workspace=(self.root/row['state']).parents[2]
        s['workstream_context']['contracts'][0]['definition']='changed contract'
        with self.assertRaises(ValueError):w.assert_context(s,workspace)
    def test_report_identifies_its_question_even_before_completion(self):
        import readable_report
        row=self.b['runs'][0];s=json.loads((self.root/row['state']).read_text());s['config']['reader_friendly']=True
        output='\n'.join(readable_report.sections(s))
        self.assertIn('この研究が担当するコアロジック',output)
        self.assertIn('RP1',output);self.assertIn('SYS-R1',output)
    def test_old_runs_have_no_added_requirements(self):
        self.assertEqual(w.role_instructions('producer',{}),'');w.assert_context({},self.root)


class IntegrationAnchorTests(unittest.TestCase):
    def test_harness_hooks_compile_and_required_flags_exist(self):
        from test_upgrade import u,prior,H
        out=u.patch_workstream_harness(u.patch_harness(prior.patch_harness(H)))
        compile(out,'harness.py','exec')
        for token in ('--workstream-plan','--workstream-id','workstream_context','snapshot_task(args','workstream_instructions(role'):
            self.assertIn(token,out)
    def test_two_installer_copies_identical(self):
        self.assertEqual((ROOT/'tools/design-research/skill/scripts/research_workstreams.py').read_bytes(),
                         (ROOT/'tools/speckit-upstream/workbench/research_workstreams.py').read_bytes())
