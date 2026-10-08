from __future__ import annotations

import json
from unittest.mock import patch

from test_workbench import Base, demo_records
from workbench.approval import approve, create_review
from workbench.approval_core import approval_states, item_hash
from workbench.common import WorkbenchError, json_text, load_project
from workbench.layout import destination
from workbench.migration import migrate
from workbench.project_ops import add_item
from workbench.trace import inspect, parse_file, save_report
from workbench.workflow import run_gate, verify_gate


class CompactTests(Base):
    legacy_layout = False

    def setUp(self):
        super().setUp()
        self.attach(docs_only=True)

    def rows(self):
        rows = demo_records()
        for r in rows:
            r['status']='proposed';r.pop('approval')
            p = self.root/'docs/upstream'/destination(r['type'])
            with p.open('a') as f:
                f.write(f"\n<!-- upstream:section {r['id']} -->\n## {r['id']}\n\n```upstream\n"+json_text(r)+f"```\n\n本文 {r['id']}\n<!-- /upstream:section -->\n")
        for rel in load_project(self.root)['required_docs']:
            p=self.root/rel;p.write_text(p.read_text().replace('TBD','例: 説明済み'))
        return rows

    def states(self):
        return approval_states(self.root,{r['id']:r for r in inspect(self.root)['items']})

    def approved(self):
        self.rows()
        packet=create_review(self.root,'all',True)
        approve(self.root,packet['review_id'],[],'fixture','explicit approval',True,True)
        self.assertTrue(all(s['state']=='valid' for s in self.states().values()))
        return packet

    def test_default_three_documents_and_routing(self):
        self.assertEqual({p.name for p in (self.root/'docs/upstream').rglob('*.md')},
                         {'requirements.md','design.md','verification.md'})
        for n,kind in enumerate(('goal','design','decision','verification','evidence')):
            key=f'APP-ITEM-{n+1:03}'
            add_item(self.root,kind,key,kind,[],None,True)
            row=next(r for r in inspect(self.root)['items'] if r['id']==key)
            self.assertEqual(row['_file'],'docs/upstream/'+destination(kind))
            self.assertEqual(row['_section'],key)
        self.assertFalse((self.root/'docs/upstream/items').exists())

    def test_explicit_file_still_supported(self):
        p=self.root/'specs/a/spec.md';p.parent.mkdir(parents=True);p.write_text('Official detail\n')
        add_item(self.root,'design','APP-DES-001','design',[],'specs/a/spec.md',True)
        self.assertIn('Official detail',p.read_text())
        self.assertEqual(inspect(self.root)['items'][0]['_file'],'specs/a/spec.md')

    def test_explicit_file_with_legacy_items_keeps_its_context_format(self):
        p=self.root/'specs/a/spec.md';p.parent.mkdir(parents=True)
        p.write_text('Official detail\n```upstream\n'+json_text(demo_records()[0])+'```\nLegacy prose\n')
        add_item(self.root,'goal','APP-GOL-002','Another goal',[],'specs/a/spec.md',True)
        result=inspect(self.root)
        self.assertNotIn('INVALID_SCOPE',{f['code'] for f in result['findings']})
        self.assertTrue(all(r['_section'] is None for r in result['items']))
        self.assertIn('Legacy prose',p.read_text())

    def test_scoped_review_binds_distinct_prose(self):
        self.rows();packet=create_review(self.root,'all',True)
        self.assertEqual({r['hash_version'] for r in packet['items']},{3})
        self.assertEqual(len(packet['documents']),6)
        self.assertIn('本文 APP-GOL-001',packet['documents']['docs/upstream/requirements.md#APP-GOL-001']['prose'])
        self.assertNotIn('本文 APP-FR-001',packet['documents']['docs/upstream/requirements.md#APP-GOL-001']['prose'])
        self.assertTrue((self.root/packet['saved_markdown']).is_relative_to(self.root/'.specify/workbench'))

    def test_unrelated_section_does_not_invalidate_same_file(self):
        self.approved()
        p=self.root/'docs/upstream/requirements.md'
        p.write_text(p.read_text().replace('本文 APP-FR-001','変更した要件本文'))
        states=self.states()
        self.assertEqual(states['APP-GOL-001']['state'],'valid')
        self.assertEqual(states['APP-US-001']['state'],'valid')
        self.assertEqual(states['APP-FR-001']['state'],'stale_content')
        self.assertEqual(states['APP-DES-001']['state'],'stale_dependency')
        self.assertEqual(states['APP-TEST-001']['state'],'stale_dependency')

    def test_appending_a_new_section_keeps_prior_approvals_current(self):
        self.approved()
        add_item(self.root,'goal','APP-GOL-002','Another goal',[],None,True)
        states=self.states()
        self.assertEqual(states['APP-GOL-002']['state'],'missing')
        self.assertTrue(all(states[key]['state']=='valid' for key in ('APP-GOL-001','APP-NEED-001','APP-US-001','APP-FR-001','APP-DES-001','APP-TEST-001')))

    def test_shared_conditions_invalidate_every_item_in_document(self):
        self.approved();p=self.root/'docs/upstream/requirements.md'
        p.write_text(p.read_text().replace('この文書全体に適用する','変更した共通条件。この文書全体に適用する'))
        self.assertTrue(all(self.states()[key]['state']=='stale_content'
                            for key in ('APP-GOL-001','APP-NEED-001','APP-US-001','APP-FR-001')))

    def test_results_remain_outside_plan_hash(self):
        self.approved();p=self.root/'docs/upstream/verification.md'
        row=next(r for r in inspect(self.root)['items'] if r['type']=='verification')
        before=item_hash(row)
        p.write_text(p.read_text().replace('"result": "not_run"','"result": "pass"').replace('"result_evidence": []','"result_evidence": ["runs/check.json"]'))
        row=next(r for r in inspect(self.root)['items'] if r['type']=='verification')
        self.assertEqual(before,item_hash(row));self.assertEqual(self.states()[row['id']]['state'],'valid')

    def test_invalid_scope_is_rejected(self):
        self.rows();p=self.root/'docs/upstream/requirements.md'
        original=p.read_text()
        for suffix in ('<!-- upstream:section APP-GOL-001 -->\n<!-- /upstream:section -->',
                       '<!-- upstream:section nested -->\n<!-- upstream:section inner -->',
                       '<!-- /upstream:section -->'):
            p.write_text(original+'\n'+suffix)
            self.assertIn('INVALID_SCOPE',{f['code'] for f in inspect(self.root)['findings']})
            with self.assertRaises(WorkbenchError):create_review(self.root,'all')

    def test_gate_coverage_and_internal_trace_do_not_add_primary_documents(self):
        self.approved();self.assertTrue(run_gate(self.root,True)['passed'])
        save_report(self.root,inspect(self.root))
        self.assertTrue(verify_gate(self.root)['passed'])
        self.assertEqual(len(list((self.root/'docs/upstream').rglob('*.md'))),3)
        self.assertTrue((self.root/'.specify/workbench/trace/index.json').is_file())


class MigrationTests(Base):
    def setUp(self):
        super().setUp();self.attach(docs_only=True);self.write_records(demo_records())
        self.include=['docs/upstream/requirements/demo.md']

    def tree(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_preview_has_content_links_and_rereview_without_writes(self):
        before=self.tree();result=migrate(self.root,include=self.include)
        self.assertFalse(result['applied']);self.assertEqual(self.tree(),before)
        self.assertEqual(len(result['content']),3)
        self.assertEqual(len(result['re_review_ids']),6)
        self.assertIn('架空例',result['content']['docs/upstream/requirements.md'])

    def test_apply_preserves_ids_evidence_history_and_is_idempotent(self):
        old=self.tree();result=migrate(self.root,True,self.include)
        self.assertEqual(len(inspect(self.root)['items']),6)
        ledger='.specify/workbench/approvals.jsonl'
        self.assertEqual((self.root/ledger).read_bytes(),old[ledger])
        self.assertEqual(len(list((self.root/'docs/upstream').rglob('*.md'))),3)
        for oldpath,newpath in result['internal_records'].items():
            self.assertEqual((self.root/newpath).read_bytes(),old[oldpath])
        states=approval_states(self.root,{r['id']:r for r in inspect(self.root)['items']})
        self.assertTrue(all(v['state']!='valid' for v in states.values()))
        for name in result['sources']+['.specify/workbench.json']:
            self.assertEqual((self.root/result['backup']/'original'/name).read_bytes(),old[name])
        before=self.tree();self.assertTrue(migrate(self.root,True)['already_compact']);self.assertEqual(self.tree(),before)

    def test_markdown_links_rebase_to_migrated_headings_and_unchanged_evidence(self):
        save_report(self.root,inspect(self.root))
        p=self.root/'docs/upstream/product/vision.md'
        p.write_text(p.read_text()+'\n[検証](../verification/plan.md)\n[本文](../requirements/demo.md#app-fr-001)\n[出典](../../../source.txt)\n[旧対応表](../traceability/matrix.md)\n')
        (self.root/'source.txt').write_text('evidence')
        result=migrate(self.root,True,self.include)
        import re
        for target in result['documents']:
            text=(self.root/target).read_text()
            for link in re.findall(r'\]\(([^)]+)\)',text):
                if link.startswith('http'):continue
                file,_,anchor=link.partition('#');path=(self.root/target).parent/file
                self.assertTrue(path.is_file(),link)
                if anchor:self.assertIn('id="'+anchor+'"',path.read_text(),link)

    def test_official_and_custom_documents_are_preserved(self):
        p=self.root/'specs/f/spec.md';p.parent.mkdir(parents=True);p.write_text('Official detail')
        custom=self.root/'docs/upstream/custom.md';custom.write_text('Keep custom')
        migrate(self.root,True,self.include)
        self.assertEqual(p.read_text(),'Official detail');self.assertEqual(custom.read_text(),'Keep custom')

    def test_conflict_duplicate_ids_and_broken_json_refuse_without_changes(self):
        p=self.root/'docs/upstream/requirements.md';p.write_text('foreign')
        before=self.tree()
        with self.assertRaises(WorkbenchError):migrate(self.root,True,self.include)
        self.assertEqual(self.tree(),before);p.unlink()
        p=self.root/'docs/upstream/duplicate.md';p.write_bytes((self.root/self.include[0]).read_bytes())
        before=self.tree()
        with self.assertRaisesRegex(WorkbenchError,'DUPLICATE_ID'):migrate(self.root,True,self.include)
        self.assertEqual(self.tree(),before)

    def test_failure_rolls_back_documents_and_config(self):
        import workbench.migration as module
        original=module.atomic_write;writes=[]
        def fail_once(path,data):
            if str(path).endswith('/design.md') and not writes:
                writes.append(True);raise OSError('simulated write failure')
            return original(path,data)
        before=self.tree()
        with patch.object(module,'atomic_write',side_effect=fail_once):
            with self.assertRaisesRegex(OSError,'simulated'):migrate(self.root,True,self.include)
        self.assertEqual(self.tree(),before)

    def test_termination_during_apply_rolls_back(self):
        import os,signal
        import workbench.migration as module
        from workbench.cli import main
        original=module.atomic_write;interrupted=[]
        def interrupt_once(path,data):
            if str(path).endswith('/design.md') and not interrupted:
                interrupted.append(True);os.kill(os.getpid(),signal.SIGTERM)
            return original(path,data)
        before=self.tree()
        with patch.object(module,'atomic_write',side_effect=interrupt_once):
            status=main(['migrate','--project',str(self.root),'--include-doc',self.include[0],'--apply'])
        self.assertEqual(status,2);self.assertEqual(self.tree(),before)

    def test_upgrade_attach_does_not_migrate(self):
        before=self.tree();self.attach(docs_only=True);self.assertEqual(self.tree(),before)

    def test_legacy_comments_do_not_implicitly_activate_new_scope_hashes(self):
        p=self.root/self.include[0]
        p.write_text('<!-- upstream:section example -->\n'+p.read_text()+'\n<!-- /upstream:section -->\n')
        packet=create_review(self.root,'all',True)
        self.assertEqual({r['hash_version'] for r in packet['items']},{2})
        approve(self.root,packet['review_id'],[],'fixture','explicit',True,True)
        rows=inspect(self.root)['items']
        self.assertTrue(all(r['_section'] is None for r in rows))
        self.assertTrue(all(s['state']=='valid' for s in approval_states(self.root,{r['id']:r for r in rows}).values()))
