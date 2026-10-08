from __future__ import annotations
import json
from test_workbench import Base, demo_records
from workbench.approval import create_review, approve, revoke, approval_plan, set_profile
from workbench.approval_core import approval_states
from workbench.common import WorkbenchError
from workbench.trace import inspect


def proposed_rows():
    rows=demo_records()
    for row in rows:
        row['status']='proposed';row.pop('approval',None)
    return rows


class ApprovalTests(Base):
    def setUp(self):
        super().setUp();self.attach(docs_only=True)

    def states(self):
        result=inspect(self.root,'draft');byid={r['id']:r for r in result['items']}
        return approval_states(self.root,byid)

    def test_review_then_approve_checkpoint(self):
        self.write_records(proposed_rows())
        packet=create_review(self.root,'next',True)
        self.assertEqual(packet['checkpoint'],'intent')
        self.assertEqual({x['id'] for x in packet['items']},{'APP-GOL-001','APP-NEED-001','APP-US-001'})
        approve(self.root,packet['review_id'],[],'user','explicit test approval',True,all_reviewed=True)
        st=self.states()
        self.assertEqual(st['APP-GOL-001']['state'],'valid')
        self.assertEqual(st['APP-NEED-001']['state'],'valid')
        self.assertEqual(st['APP-US-001']['state'],'valid')
        current=inspect(self.root,'draft');goal=next(r for r in current['items'] if r['id']=='APP-GOL-001')
        self.assertEqual(goal['basis'],'agreed')
        plan=approval_plan(self.root)
        self.assertTrue(plan['checkpoints'][0]['complete'])
        self.assertIn('APP-FR-001',plan['checkpoints'][1]['pending'])

    def test_stale_review_cannot_approve(self):
        self.write_records(proposed_rows())
        packet=create_review(self.root,'next',True)
        p=self.root/'docs/upstream/requirements/demo.md'
        p.write_text(p.read_text().replace('架空の説明 APP-GOL-001','変更された目的',1))
        with self.assertRaisesRegex(WorkbenchError,'STALE_REVIEW'):
            approve(self.root,packet['review_id'],['APP-GOL-001'],'user','old review',True)

    def test_content_change_stales_approval_and_dependencies(self):
        self.write_records(demo_records())
        self.assertTrue(all(v['state']=='valid' for v in self.states().values()))
        p=self.root/'docs/upstream/requirements/demo.md'
        p.write_text(p.read_text().replace('架空の説明 APP-GOL-001','変更された目的',1))
        st=self.states()
        self.assertEqual(st['APP-GOL-001']['state'],'stale_content')
        self.assertEqual(st['APP-NEED-001']['state'],'stale_dependency')
        self.assertEqual(st['APP-US-001']['state'],'stale_dependency')
        codes={x['code'] for x in inspect(self.root,'ready')['findings']}
        self.assertIn('STALE_APPROVAL',codes)
        self.assertIn('STALE_DEPENDENCY_APPROVAL',codes)

    def test_revoke_returns_item_to_proposed(self):
        self.write_records(demo_records())
        revoke(self.root,['APP-FR-001'],'user','requirements changed',True)
        result=inspect(self.root,'draft');row=next(r for r in result['items'] if r['id']=='APP-FR-001')
        self.assertEqual(row['status'],'proposed')
        self.assertEqual(self.states()['APP-FR-001']['state'],'revoked')

    def test_approve_needs_ids_or_explicit_all(self):
        self.write_records(proposed_rows());packet=create_review(self.root,'next',True)
        with self.assertRaises(WorkbenchError):
            approve(self.root,packet['review_id'],[],'user','explicit',True,all_reviewed=False)

    def test_profile_can_change_explicitly(self):
        self.assertEqual(approval_plan(self.root)['profile'],'normal')
        set_profile(self.root,'critical',True)
        plan=approval_plan(self.root)
        self.assertEqual(plan['profile'],'critical')
        self.assertEqual([x['checkpoint'] for x in plan['checkpoints']],['purpose','stories','requirements','design','verification'])

    def test_review_packet_and_summary_are_written(self):
        self.write_records(proposed_rows());packet=create_review(self.root,'next',True)
        approve(self.root,packet['review_id'],['APP-GOL-001'],'user','explicit',True)
        self.assertTrue((self.root/f"docs/upstream/governance/reviews/{packet['review_id']}.md").is_file())
        self.assertTrue((self.root/'docs/upstream/governance/approvals.md').is_file())
        self.assertTrue((self.root/'.specify/workbench/approvals.jsonl').is_file())

if __name__=='__main__':
    import unittest;unittest.main(verbosity=2)
