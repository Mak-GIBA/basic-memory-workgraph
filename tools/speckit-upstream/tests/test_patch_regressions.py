"""Regression tests for audit G01-G05; fixed fixtures, no Codex/model calls."""
from __future__ import annotations
import copy, datetime, json, re
from unittest.mock import patch
from test_workbench import Base, demo_records
from workbench.approval import create_review, approve, revoke, approval_plan, set_profile
from workbench.approval_core import approval_states, item_hash, HASH_VERSION
from workbench.common import WorkbenchError, load_project, json_text
from workbench.trace import inspect, has_document_content, save_report
from workbench.workflow import run_gate, verify_gate


class PatchRegressionTests(Base):
    def setUp(self):
        super().setUp()
        self.attach(docs_only=True)

    @property
    def item_file(self):
        return self.root/'docs/upstream/requirements/demo.md'

    def edit_json(self, key, edit):
        def repl(m):
            obj=json.loads(m.group(1))
            if obj['id']==key: obj=edit(obj)
            return '```upstream\n'+json.dumps(obj,ensure_ascii=False,indent=2)+'\n```'
        self.item_file.write_text(re.sub(r'```upstream\n(.*?)\n```',repl,self.item_file.read_text(),flags=re.S))

    def current_states(self):
        result=inspect(self.root,'draft')
        return approval_states(self.root,{r['id']:r for r in result['items']})

    def reapprove_all(self):
        # A subsequent user review occurs later; deterministic test clock avoids
        # the intentional same-second/same-snapshot review-ID collision guard.
        later=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=5)
        with patch('workbench.approval._now',return_value=later):
            packet=create_review(self.root,'all',True)
        return approve(self.root,packet['review_id'],[], 'TEST reviewer',
                       'TEST ONLY: explicit simulated approval', True, all_reviewed=True)

    def test_G01_normal_prose_change_blocks_new_gate(self):
        self.write_records(demo_records());self.assertTrue(run_gate(self.root,True)['passed'])
        self.item_file.write_text(self.item_file.read_text()+'\n仕様変更: 保存失敗でも操作を完了と扱う。\n')
        with self.assertRaisesRegex(WorkbenchError,'STALE'):verify_gate(self.root)
        gate=run_gate(self.root,True)
        self.assertFalse(gate['passed'])
        self.assertIn('STALE_APPROVAL',{f['code'] for f in gate['findings']})

    def test_prose_change_after_review_rejects_approve(self):
        rows=demo_records()
        for row in rows:row['status']='proposed';row.pop('approval')
        self.write_records(rows);packet=create_review(self.root,'intent',True)
        self.item_file.write_text(self.item_file.read_text()+'\n未レビューの仕様変更。\n')
        with self.assertRaisesRegex(WorkbenchError,'STALE_REVIEW'):
            approve(self.root,packet['review_id'],['APP-GOL-001'],'TEST','TEST',True)

    def test_new_review_after_prose_change_can_restore_ready(self):
        self.write_records(demo_records())
        self.item_file.write_text(self.item_file.read_text()+'\n再レビューした追記。\n')
        self.assertFalse(run_gate(self.root)['passed'])
        self.reapprove_all()
        self.assertTrue(run_gate(self.root,True)['passed'])
        self.assertTrue(verify_gate(self.root)['passed'])

    def test_prose_scope_is_same_file_not_unrelated_file(self):
        self.write_records(demo_records());before=self.current_states()
        p=self.root/'docs/upstream/product/glossary.md'
        p.write_text(p.read_text()+'\n独立した用語の補足。\n')
        after=self.current_states()
        self.assertEqual({k:v['state'] for k,v in before.items()},
                         {k:v['state'] for k,v in after.items()})

    def test_shared_prose_conservatively_stales_same_file_items(self):
        self.write_records(demo_records())
        self.item_file.write_text(self.item_file.read_text().replace('架空例。','更新した共通説明。',1))
        self.assertTrue(all(v['state']=='stale_content' for v in self.current_states().values()))

    def test_json_only_edit_is_still_item_scoped(self):
        self.write_records(demo_records())
        self.edit_json('APP-FR-001',lambda r:{**r,'acceptance':'24時間内の操作だけを同一とみなす。'})
        states=self.current_states()
        self.assertEqual(states['APP-FR-001']['state'],'stale_content')
        self.assertEqual(states['APP-GOL-001']['state'],'valid')
        self.assertEqual(states['APP-US-001']['state'],'valid')
        self.assertEqual(states['APP-DES-001']['state'],'stale_dependency')

    def test_verification_results_do_not_change_plan_approval(self):
        self.write_records(demo_records())
        self.edit_json('APP-TEST-001',lambda r:{**r,'result':'partial','result_evidence':['TEST-only local evidence']})
        self.assertTrue(all(v['state']=='valid' for v in self.current_states().values()))

    def test_staged_approval_does_not_stale_on_metadata_write(self):
        rows=demo_records()
        for r in rows:r['status']='proposed';r['basis']='proposed';r.pop('approval')
        self.write_records(rows)
        for expected in ['intent','requirements','solution']:
            packet=create_review(self.root,'next',True)
            self.assertEqual(packet['checkpoint'],expected)
            approve(self.root,packet['review_id'],[],'TEST','TEST-only staged approval',True,all_reviewed=True)
        self.assertTrue(run_gate(self.root)['passed'])

    def test_review_packet_contains_prose_and_full_semantic_data(self):
        self.write_records(demo_records())
        self.edit_json('APP-DES-001',lambda r:{**r,'detail':'並行処理の実現方式もレビュー対象にする。'})
        packet=create_review(self.root,'all',True)
        body=packet['documents']['docs/upstream/requirements/demo.md']['prose']
        self.assertIn('架空例。',body)
        row=next(x for x in packet['items'] if x['id']=='APP-DES-001')
        self.assertIn('detail',row['semantic'])
        md=(self.root/packet['saved_markdown']).read_text()
        self.assertIn('並行処理の実現方式',md);self.assertIn('架空例。',md)

    def test_old_review_is_not_silently_upgraded(self):
        self.write_records(demo_records());packet=create_review(self.root,'intent',True)
        path=self.root/packet['saved_json'];saved=json.loads(path.read_text());saved.pop('hash_version')
        path.write_text(json_text(saved))
        with self.assertRaisesRegex(WorkbenchError,'STALE_REVIEW'):
            approve(self.root,packet['review_id'],['APP-GOL-001'],'TEST','TEST',True)

    def test_old_approval_requires_explicit_rereview(self):
        self.write_records(demo_records())
        path=self.root/'.specify/workbench/approvals.jsonl'
        events=[json.loads(line) for line in path.read_text().splitlines()]
        for e in events:e.pop('hash_version')
        path.write_text(''.join(json.dumps(e)+'\n' for e in events))
        self.assertIn('LEGACY_APPROVAL_UNBOUND',self.codes())
        self.assertFalse(run_gate(self.root)['passed'])
        self.reapprove_all();self.assertTrue(run_gate(self.root)['passed'])

    def test_generated_trace_does_not_stale_approvals(self):
        self.write_records(demo_records());run_gate(self.root,True)
        save_report(self.root,inspect(self.root))
        self.assertTrue(verify_gate(self.root)['passed'])

    def no_stories(self):
        rows=[r for r in demo_records() if r['type'] not in {'need','story'}]
        for r in rows:
            if r['type']=='requirement':r['links']={'derives_from':['APP-GOL-001']}
        return rows

    def test_G02_missing_need_story_blocks_ready(self):
        self.write_records(self.no_stories())
        gate=run_gate(self.root)
        self.assertFalse(gate['passed'])
        missing={f['item'] for f in gate['findings'] if f['code']=='MISSING_CATEGORY'}
        self.assertTrue({'need','story'}<=missing)
        plan=approval_plan(self.root)
        self.assertFalse(plan['checkpoints'][0]['complete'])

    def test_approved_reason_allows_legitimate_story_omission(self):
        rows=self.no_stories()
        rows[0]['readiness_exemptions']={
            'need':'内部インフラの既存品質要求が直接の根拠で、新たな利用者要求は発生しない。',
            'story':'内部ログ基盤の置換で、利用者の操作と価値は変更しない。'}
        self.write_records(rows)
        self.assertTrue(run_gate(self.root)['passed'])
        self.assertTrue(all(r['complete'] for r in approval_plan(self.root)['checkpoints']))

    def test_critical_profile_can_explicitly_exempt_empty_stories_stage(self):
        rows=self.no_stories()
        rows[0]['readiness_exemptions']={'need':'既存の品質制約に基づく内部変更。','story':'新しい利用者操作はない。'}
        self.write_records(rows);set_profile(self.root,'critical',True)
        plan=approval_plan(self.root);stories=next(r for r in plan['checkpoints'] if r['checkpoint']=='stories')
        self.assertTrue(stories['complete']);self.assertEqual(stories['ids'],[])
        self.assertTrue(run_gate(self.root)['passed'])

    def test_omission_reason_changed_needs_new_approval(self):
        rows=self.no_stories();rows[0]['readiness_exemptions']={'need':'TEST-only 内部変更。','story':'TEST-only 操作変更なし。'}
        self.write_records(rows)
        self.edit_json('APP-GOL-001',lambda r:{**r,'readiness_exemptions':{'need':'別の理由。','story':'別の理由。'}})
        self.assertFalse(run_gate(self.root)['passed'])
        self.assertIn('STALE_APPROVAL',self.codes())

    def test_unapproved_exemption_is_not_coverage(self):
        rows=self.no_stories();rows[0]['readiness_exemptions']={'need':'既存要件のみ。','story':'利用操作は不変。'}
        for r in rows:r['status']='proposed';r.pop('approval')
        self.write_records(rows)
        missing={f['item'] for f in inspect(self.root,'ready')['findings'] if f['code']=='MISSING_CATEGORY'}
        self.assertTrue({'need','story'}<=missing)

    def test_fake_core_exemption_rejected(self):
        rows=demo_records();rows[0]['readiness_exemptions']={'requirements':'要求は作りたくない。'}
        self.write_records(rows)
        self.assertIn('BAD_READINESS_EXEMPTION',self.codes())

    def test_placeholder_omission_reason_rejected(self):
        rows=demo_records();rows[0]['readiness_exemptions']={'story':'TBD'}
        self.write_records(rows)
        self.assertIn('BAD_READINESS_EXEMPTION',self.codes())

    def test_G03_goal_only_blocks_all_profiles(self):
        self.write_records([demo_records()[0]])
        for p in ['small','normal','critical']:
            with self.subTest(profile=p):
                set_profile(self.root,p,True);gate=run_gate(self.root)
                self.assertFalse(gate['passed'])
                self.assertIn('INCOMPLETE_CHECKPOINT',{x['code'] for x in gate['findings']})

    def test_missing_categories_warn_in_draft_not_prevent_incremental_approval(self):
        rows=[demo_records()[0]];rows[0]['status']='proposed';rows[0].pop('approval')
        self.write_records(rows)
        self.assertEqual(inspect(self.root,'draft')['errors'],0)
        packet=create_review(self.root,'next',True)
        approve(self.root,packet['review_id'],['APP-GOL-001'],'TEST','TEST-only purpose agreement',True)
        self.assertEqual(self.current_states()['APP-GOL-001']['state'],'valid')
        self.assertFalse(run_gate(self.root)['passed'])

    def test_next_review_reports_missing_category_instead_of_done(self):
        self.write_records([demo_records()[0]])
        with self.assertRaisesRegex(WorkbenchError,'未作成'):
            create_review(self.root,'next',False)

    def test_retired_story_does_not_count_for_coverage(self):
        self.write_records(demo_records())
        self.edit_json('APP-US-001',lambda r:{**r,'status':'retired'})
        gate=run_gate(self.root)
        self.assertFalse(gate['passed'])
        self.assertFalse(gate['coverage']['story']['satisfied'])

    def test_G04_empty_required_document_rejected(self):
        self.write_records(demo_records())
        p=self.root/'docs/upstream/architecture/overview.md';p.write_text('')
        self.assertFalse(run_gate(self.root)['passed']);self.assertIn('EMPTY_DOCUMENT',self.codes())

    def test_headings_and_comments_only_document_rejected(self):
        self.write_records(demo_records())
        p=self.root/'docs/upstream/architecture/overview.md'
        p.write_text('---\ntitle: overview\n---\n# Architecture\n## 構成\n<!-- 未表示の注記 -->\n---\n')
        self.assertIn('EMPTY_DOCUMENT',self.codes())

    def test_placeholder_table_header_is_not_document_content(self):
        self.assertFalse(has_document_content('# 設計\n\n| Component | Responsibility |\n|---|---|\n'))

    def test_real_prose_and_table_rows_are_content(self):
        for text in ['# Design\n処理責務は既存モジュールに対応する。',
                     '| Module | Role |\n|---|---|\n| API | 入力検証 |',
                     '```text\nAPI -> Storage\n```']:
            self.assertTrue(has_document_content(text))

    def test_json_metadata_only_does_not_complete_required_narrative(self):
        self.assertFalse(has_document_content('# Design\n```upstream\n{"title":"design"}\n```\n'))

    def test_G05_approval_display_matches_ledger(self):
        self.write_records(demo_records())
        self.edit_json('APP-FR-001',lambda r:{**r,'approval':{**r['approval'],'by':'OTHER PERSON',
                            'reference':'different statement','date':'2000-01-01'}})
        self.assertIn('APPROVAL_METADATA_MISMATCH',self.codes());self.assertFalse(run_gate(self.root)['passed'])

    def test_individual_approval_metadata_fields_are_compared(self):
        self.write_records(demo_records());original=self.item_file.read_text()
        for field in ['by','reference','date']:
            with self.subTest(field=field):
                self.item_file.write_text(original)
                self.edit_json('APP-FR-001',lambda r:{**r,'approval':{**r['approval'],field:'different'}})
                self.assertEqual(self.current_states()['APP-FR-001']['state'],'metadata_mismatch')

    def test_approval_updates_do_not_claim_real_user_identity(self):
        self.write_records(demo_records());packet=create_review(self.root,'all',False)
        self.assertEqual(packet['hash_version'],HASH_VERSION)
        self.assertTrue(any('本人性' in x for x in packet['limitations']))

if __name__=='__main__':
    import unittest;unittest.main(verbosity=2)
