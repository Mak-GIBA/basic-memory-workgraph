"""Fictional sequences only: no real memory or transcript access."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "tools/basic-memory-workgraph"
sys.path.insert(0, str(SOURCE))
import workgraph_tools as wg
from workgraph_sequence import sequence_issues


def data():
    return json.loads((REPO / 'tests/fixtures/progressive-case.json').read_text())


def piece(value):
    return {'summary': value, 'excerpt': None}


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


class SequenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.memory = self.root / 'memory'
        self.memory.mkdir()
        self.output = self.root / 'out.jsonl'

    def args(self, **kwargs):
        return argparse.Namespace(memory_dir=self.memory, output=self.output, dry_run=False, **kwargs)

    def note(self, content=None, path='cases/briefing.md', **metadata):
        values = {'title': 'Briefing', 'type': 'case', 'capture_kind': 'interaction_case',
                  'case_format_version': 2, 'integrity_status': 'unreviewed', **metadata}
        body = '\n## Interaction\n```json\n' + json.dumps(data() if content is None else content) + '\n```\n'
        note = wg.Note(path, values, body)
        target = self.memory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(note.render())
        return path

    def review(self, path, sharing='private', training='approved'):
        return wg.review(self.args(note=path, sharing=sharing, training=training))

    def codes(self, content):
        return {i['code'] for i in sequence_issues(content)}

    def test_no_rating_sequence_preserves_order_and_unknown_acceptance(self):
        payload = data()
        self.assertEqual(sequence_issues(payload), [])
        rel = self.note(payload)
        self.review(rel)
        self.assertEqual(wg.export_cases(self.args())['exported'], 1)
        row = json.loads(self.output.read_text())
        self.assertEqual(row['format_version'], 1)
        self.assertEqual(row['interaction'], payload)
        self.assertEqual(row['interaction']['acceptance'], 'unknown')
        self.assertEqual(row['interaction']['assessments'][0]['judgment'], 'tentative')
        self.assertEqual([s['id'] for s in row['interaction']['steps']], ['o1','c1','o2','c2','o3','v1','a1','a2'])

    def test_open_sequence_with_unknown_output_and_no_assessment(self):
        payload = data()
        payload.update(steps=[], latest_output_id=None, assessments=[], outcome='unverified', state='open')
        payload['steps'] = [dict(data()['steps'][1], target_id=None)]
        payload['context']['audience'] = None
        self.assertEqual(sequence_issues(payload), [])
        # Later material updates retain previous steps and use stable IDs.
        payload['steps'].append(dict(data()['steps'][2], target_id=None))
        payload['latest_output_id'] = 'o2'
        self.assertEqual(sequence_issues(payload), [])

    def success(self, signal=None):
        """A useful first attempt; no fabricated correction or acceptance."""
        payload = data()
        output = dict(payload['steps'][0], content=piece('Recovery procedure with a bounded retry and rollback'))
        check = dict(payload['steps'][5], target_id='o1',
                     content=piece('Injected an interrupted write; rollback retained the prior valid data'))
        payload.update(steps=[output, check], latest_output_id='o1', assessments=[])
        payload['context'].update(purpose='Recover interrupted writes', audience='Maintainers',
                                  deliverable='Recovery procedure', constraints='Preserve prior valid data',
                                  scope='Interrupted local writes with an existing valid backup')
        payload['request'] = piece('Produce a recovery procedure for interrupted writes')
        payload['transfer_use'] = 'Recover interrupted local writes in other tools with the same backup guarantee'
        if signal:
            payload['steps'].append(dict(data()['steps'][-1], target_id='o1', signal=signal,
                content=piece('Use this recovery procedure for the next importer')))
            payload['assessments'] = [dict(data()['assessments'][0], target_id='o1',
                aspect='Choice of recovery procedure for the next importer', judgment='supported',
                evidence_ids=['a2'], rationale=piece('Requested reuse; execution and satisfaction remain unknown'))]
        return payload

    def test_success_without_correction_or_rating_round_trips(self):
        for signal in (None, 'reuse_request', 'downstream_use'):
            with self.subTest(signal=signal):
                payload = self.success(signal)
                if signal == 'downstream_use':
                    payload['steps'][-1]['content'] = piece('The user reports using this procedure in another importer')
                    payload['assessments'][0]['rationale'] = piece('Reported downstream use of the procedure; satisfaction unknown')
                self.assertFalse(any(s['kind'] == 'correction' for s in payload['steps']))
                self.assertEqual(sequence_issues(payload), [])
                rel = self.note(payload)
                # Capture and local audit do not require acceptance or export approval.
                self.assertEqual(wg.audit(self.args(note=rel))['issues'], [])
                self.output = self.root / f'{signal}-unreviewed.jsonl'
                self.assertEqual(wg.export_cases(self.args())['exported'], 0)
                self.review(rel)
                self.output = self.root / f'{signal}-reviewed.jsonl'
                self.assertEqual(wg.export_cases(self.args())['exported'], 1)
                exported = json.loads(self.output.read_text())['interaction']
                self.assertEqual(exported, payload)
                self.assertEqual(exported['acceptance'], 'unknown')

    def test_verification_does_not_become_adoption_or_acceptance(self):
        payload = self.success()
        payload['assessments'] = [dict(data()['assessments'][0], target_id='o1',
            evidence_ids=['v1'], judgment='supported')]
        self.assertIn('unsupported_adoption', self.codes(payload))
        payload.update(acceptance='accepted', acceptance_evidence_ids=['v1'])
        self.assertIn('unsupported_acceptance', self.codes(payload))

    def test_success_reception_does_not_transfer_to_revised_output(self):
        payload = self.success('reuse_request')
        payload['steps'].append(dict(payload['steps'][0], id='o2', target_id='o1',
                                    change=piece('Changed the retry behavior')))
        payload.update(latest_output_id='o2', outcome='unverified')
        self.assertEqual(sequence_issues(payload), [])
        payload['assessments'][0]['target_id'] = 'o2'
        self.assertIn('evidence_target_mismatch', self.codes(payload))

    def test_structural_errors_have_controlled_locations(self):
        modifications = [
            (lambda d: d['steps'][2].update(id='o1'), 'duplicate_id'),
            (lambda d: d['steps'][1].update(target_id='o3'), 'invalid_target'),
            (lambda d: d['steps'][2].update(target_id='o2'), 'invalid_target'),
            (lambda d: d['steps'][1].update(target_id='missing'), 'invalid_target'),
            (lambda d: d.update(latest_output_id='o1'), 'latest_output_mismatch'),
            (lambda d: d['assessments'][0].update(target_id='missing'), 'invalid_assessment_target'),
            (lambda d: d['assessments'][0].update(evidence_ids=['c2']), 'evidence_target_mismatch'),
            (lambda d: d['assessments'][0].update(evidence_ids=['a1','a1']), 'duplicate_evidence'),
            (lambda d: d['steps'][5].update(target_id='o1'), 'unsupported_verification'),
        ]
        for mutate, code in modifications:
            with self.subTest(code=code):
                payload = data(); mutate(payload)
                self.assertIn(code, self.codes(payload))

    def test_implicit_delivery_is_not_explicit_acceptance(self):
        payload = data()
        payload.update(acceptance='accepted', acceptance_evidence_ids=['a1','a2'])
        self.assertIn('unsupported_acceptance', self.codes(payload))
        payload['steps'][-1]['signal'] = 'explicit_acceptance'
        payload['acceptance_evidence_ids'] = ['a2']
        self.assertNotIn('unsupported_acceptance', self.codes(payload))
        payload['steps'][-1]['target_id'] = 'o2'
        self.assertIn('unsupported_acceptance', self.codes(payload))

    def test_correlated_commits_never_upgrade_to_supported(self):
        payload = data()
        payload['assessments'][0]['judgment'] = 'supported'
        self.assertIn('overstated_adoption', self.codes(payload))
        payload['steps'][-1]['group_id'] = 'different-group'
        self.assertIn('overstated_adoption', self.codes(payload))
        payload['steps'][-1]['signal'] = 'reuse_request'
        self.assertEqual(sequence_issues(payload), [])

    def test_later_failure_or_rejection_invalidates_stale_success(self):
        payload=data()
        payload['steps'][-1]['signal']='explicit_acceptance'
        payload.update(acceptance='accepted',acceptance_evidence_ids=['a2'])
        self.assertEqual(sequence_issues(payload),[])
        payload['steps'].append(dict(payload['steps'][-1],id='later-rejection',signal='explicit_rejection'))
        self.assertIn('stale_acceptance',self.codes(payload))
        payload=data()
        payload['steps'].append(dict(payload['steps'][5],id='failed-check',result='failed'))
        self.assertIn('conflicting_verification',self.codes(payload))
        payload['outcome']='partial'
        self.assertEqual(sequence_issues(payload),[])

    def test_autonomous_or_checkpoint_actions_do_not_establish_adoption(self):
        for field, value in (('actor','assistant'), ('actor','tool'), ('signal','checkpoint_request'), ('signal','none')):
            with self.subTest(field=field, value=value):
                payload=data()
                for step in payload['steps'][-2:]: step[field]=value
                self.assertIn('unsupported_adoption', self.codes(payload))

    def test_reversal_requires_reassessment_without_deleting_original_action(self):
        payload=data()
        reversal=dict(payload['steps'][-1], id='reversal', signal='revert_request', content=piece('Restore the prior version'), group_id='reversal')
        payload['steps'].append(reversal)
        self.assertIn('unconsidered_counterevidence', self.codes(payload))
        assessment=payload['assessments'][0]
        assessment['counterevidence_ids']=['reversal']
        assessment['judgment']='contradicted'
        self.assertEqual(sequence_issues(payload), [])
        self.assertEqual(payload['steps'][-2]['signal'],'push_request')
        assessment['judgment']='supported'
        self.assertIn('overstated_adoption', self.codes(payload))

    def test_checked_status_does_not_bypass_validation(self):
        payload=data();payload['steps'][1]['target_id']='o3'
        rel=self.note(payload, integrity_status='checked')
        with self.assertRaises(wg.Invalid): self.review(rel)
        report=wg.audit(self.args(note=rel))
        self.assertIn('invalid_target', {i['code'] for i in report['issues']})

    def test_needs_review_blocks_all_exports_and_approval_even_with_fingerprint(self):
        rel=self.note(integrity_status='needs_review')
        with self.assertRaises(wg.Invalid): self.review(rel)
        note=wg.load_note(self.memory,rel)
        note.metadata.update(sharing_scope='team', training_use='approved', privacy_review='passed')
        note.metadata['review_sha256']=note.fingerprint()
        (self.memory/rel).write_text(note.render())
        before=snapshot(self.memory)
        self.assertEqual(wg.export_cases(self.args())['exported'],0)
        self.output=self.root/'share'
        self.assertEqual(wg.export_share(self.args(scope='team',include_cases=True))['exported'],0)
        self.assertEqual(snapshot(self.memory),before)

    def test_audit_reports_affected_knowledge_but_does_not_mutate(self):
        rel=self.note(integrity_status='needs_review')
        rule=wg.Note('rules/format.md',{'title':'Format','type':'rule'},'\n## Relations\n- learned_from [[cases/briefing]]\n')
        workflow=wg.Note('workflows/format.md',{'title':'Format procedure','type':'workflow'},'\n## Relations\n- implements [[rules/format]]\n')
        for n in (rule,workflow):
            target=self.memory/n.path;target.parent.mkdir();target.write_text(n.render())
        before=snapshot(self.root)
        report=wg.audit(self.args(note=rel))
        self.assertTrue(report['read_only'])
        self.assertEqual({(i['note'],i['depth']) for i in report['affected']}, {('rules/format.md',1),('workflows/format.md',2)})
        self.assertEqual(snapshot(self.root),before)
        # Independently reviewed rules are not invalidated solely by graph reachability.
        self.review(rule.path,sharing='team',training='excluded')
        self.assertTrue(wg.load_note(self.memory,rule.path).reviewed())

    def test_evidence_backed_repair_clears_concern_and_invalidates_privacy_review(self):
        rel=self.note()
        self.review(rel)
        original=wg.load_note(self.memory,rel)
        payload=data()
        payload['steps'][1]['content']=piece('Put the comparison first and keep supporting details')
        payload['repairs']=[{'id':'repair1','reason':piece('The stored instruction omitted the request to retain details'),
            'evidence':piece('The available user correction included both requirements'),
            'changes':[{'location':'/steps/1/content','before':data()['steps'][1]['content'],'after':payload['steps'][1]['content']}]}]
        self.assertEqual(sequence_issues(payload),[])
        # Emulate the documented agent edit, not an automatic CLI repair.
        self.note(payload, integrity_status='checked', training_use='approved', privacy_review='pending')
        self.assertFalse(wg.load_note(self.memory,rel).reviewed())
        self.assertNotEqual(wg.load_note(self.memory,rel).fingerprint(),original.fingerprint())
        self.assertEqual(wg.audit(self.args(note=rel))['issues'],[])
        self.assertEqual(wg.export_cases(self.args())['exported'],0)
        self.output=self.root/'reapproved.jsonl'
        self.review(rel)
        self.assertEqual(wg.export_cases(self.args())['exported'],1)
        self.assertEqual(json.loads(self.output.read_text())['interaction']['repairs'],payload['repairs'])

    def test_share_import_retains_sequence_but_resets_integrity_attestation(self):
        rel=self.note(integrity_status='checked')
        self.review(rel,sharing='team',training='excluded')
        self.output=self.root/'share'
        self.assertEqual(wg.export_share(self.args(scope='team',include_cases=True))['exported'],1)
        destination=self.root/'imported'
        args=argparse.Namespace(memory_dir=destination,bundle=self.output,dry_run=False)
        self.assertEqual(wg.import_share(args)['imported'],1)
        imported=wg.load_note(destination,rel)
        self.assertEqual(wg.interaction(imported),data())
        self.assertEqual(imported.metadata['integrity_status'],'unreviewed')
        self.assertEqual(imported.metadata['training_use'],'excluded')
        self.assertEqual(wg.import_share(args)['unchanged'],1)

    def test_legacy_case_is_not_rewritten_by_audit(self):
        path=self.memory/'cases/old.md';path.parent.mkdir()
        path.write_text('---\ntitle: Old case\ntype: case\n---\nUnstructured record\n')
        before=snapshot(self.root)
        report=wg.audit(self.args(note=None))
        self.assertEqual(report['issues'],[])
        self.assertEqual(len(report['legacy']),1)
        self.assertEqual(snapshot(self.root),before)

    def test_diagnostics_do_not_echo_sensitive_content_paths_or_ids(self):
        payload=data();payload['steps'][1]['target_id']='person@example.test'
        payload['steps'][1]['content']=piece('password: never-echo-this-value')
        rel=self.note(payload,path='cases/person@example.test.md')
        result=wg.audit(self.args(note=rel))
        report=json.dumps(result)
        self.assertNotIn('person@example.test',report)
        self.assertNotIn('never-echo-this-value',report)
        self.assertIn('sha256:',report)
        self.assertIn('privacy_concern',report)
        with self.assertRaises(wg.Invalid):self.review(rel)

    def test_audit_cli_is_read_only_and_exit_codes_are_consistent(self):
        rel=self.note()
        command=[sys.executable,str(SOURCE/'workgraph_tools.py'),'audit','--memory-dir',str(self.memory),'--note',rel]
        before=snapshot(self.root)
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(snapshot(self.root),before)
        self.note(integrity_status='needs_review')
        before=snapshot(self.root)
        result=subprocess.run(command+['--dry-run'],capture_output=True,text=True)
        self.assertEqual(result.returncode,2,result.stderr)
        self.assertEqual(snapshot(self.root),before)
        result=subprocess.run(command[:-1]+['../escape.md'],capture_output=True,text=True)
        self.assertEqual(result.returncode,1)

    def test_malformed_values_return_safe_issues(self):
        for field in data():
            for value in (None, True, [], {}, 42):
                payload=data();payload[field]=value
                self.assertIsInstance(sequence_issues(payload),list)
        for field in data()['steps'][-1]:
            for value in (None, [], {}, 42):
                payload=data();payload['steps'][-1][field]=value
                self.assertTrue(sequence_issues(payload),(field,value))


if __name__=='__main__':
    unittest.main()
