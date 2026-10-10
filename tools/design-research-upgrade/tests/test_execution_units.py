"""Operational contracts; these fixtures do not establish model effectiveness."""
from __future__ import annotations
import copy
import json
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_stages import StageTests
import execution_units as u
import harness as h
import runtime as rt


class UnitTests(unittest.TestCase):
    def setUp(self):
        StageTests.setUp(self)
        self.state.update(execution_contract_version=2)
        self.state['config'].update(allow_network=False, test_commands=[], target_methods=5)

    def test_unit_reuses_validated_output_and_detects_tampering(self):
        invoke = unittest.mock.Mock(return_value=copy.deepcopy(self.design))
        a = u.unit('producer-design', h.DESIGN, self.state, self.workspace, self.run, invoke)
        self.assertEqual(a, u.unit('producer-design', h.DESIGN, self.state, self.workspace, self.run, invoke))
        self.assertEqual(invoke.call_count, 1)
        self.state['units']['001-producer-design']['result']['reason'] = 'changed'
        with self.assertRaisesRegex(rt.Blocked, 'changed'):
            u.unit('producer-design', h.DESIGN, self.state, self.workspace, self.run, invoke)

    def test_failed_unit_stays_incomplete_and_preserves_completed_predecessor(self):
        invoke = unittest.mock.Mock(side_effect=[self.design, rt.Blocked('timeout')])
        u.unit('producer-design', h.DESIGN, self.state, self.workspace, self.run, invoke)
        with self.assertRaises(rt.Blocked):
            u.unit('producer-assets', h.ASSETS, self.state, self.workspace, self.run, invoke,
                   dependencies=['producer-design'])
        self.assertEqual(self.state['units']['001-producer-design']['status'], 'complete')
        self.assertEqual(self.state['units']['001-producer-assets']['status'], 'incomplete')

    def test_input_overflow_is_complete_hashed_reference_not_truncation(self):
        marker = '完全な原典の内容' * 10000
        self.state['proposal_design'] = copy.deepcopy(self.design)
        self.state['proposal_design']['dossier_json'] = json.dumps({**self.draft, 'scope': marker})
        self.state['config']['reader_friendly'] = True
        path = self.run / 'child'; path.mkdir()
        text = h.role_prompt('producer-reader', self.state, path)
        self.assertLessEqual(len(text.encode()), u.CONTEXT_BYTES)
        refs = json.loads(text.split('INPUT:\n', 1)[1])
        value = json.loads(Path(refs['proposal_design']['read_file']).read_text())
        self.assertEqual(json.loads(value['dossier_json'])['scope'], marker)
        u.assert_inputs(self.state)
        Path(refs['proposal_design']['read_file']).write_text('{}')
        with self.assertRaisesRegex(rt.Blocked, 'input changed'):
            u.assert_inputs(self.state)

    def test_assets_context_has_contract_once_and_no_full_report(self):
        self.state['proposal_design'] = copy.deepcopy(self.design)
        self.state['proposal_design']['dossier_json'] = json.dumps({**self.draft, 'reader_guide': {'takeaway': 'large narrative'}})
        inputs = u.select_inputs('producer-assets', self.state)
        self.assertNotIn('evaluation_json', inputs['plan'])
        self.assertNotIn('reader_guide', inputs['proposal_design'])
        self.assertNotIn('evidence', inputs)
        self.assertIn('evaluation_contract', inputs)

    def test_correction_design_can_read_existing_original_access_history(self):
        self.state['iteration'] = 2
        self.state['sources'] = {'OLD': {'status': 'unavailable'}, 'MIRROR': {'status': 'retrieved'}}
        self.state['dossier'] = copy.deepcopy(self.draft)
        self.state['reason'] = 'Decisive source unavailable: OLD'
        before = copy.deepcopy(self.state)
        inputs = u.select_inputs('producer-design', self.state)
        self.assertEqual(inputs['sources'], self.state['sources'])
        self.assertEqual(inputs['dossier'], self.draft)
        self.assertEqual(inputs['reason'], self.state['reason'])
        self.assertEqual(self.state, before)

    def test_unavailable_source_reference_repair_keeps_the_original_deadline(self):
        seen = []
        def run(role, schema, state, workspace, run_dir):
            seen.append((state['_role_deadline'], copy.deepcopy(state.get('repair_context'))))
            return copy.deepcopy(self.review)
        def check(value, state):
            if len(seen) == 1:
                raise rt.Blocked('Decisive source unavailable: OLD')
        with patch.object(h, 'run_role', side_effect=run):
            h.checked_role('reviewer-dossier', h.REVIEW, self.state, self.workspace, self.run, check)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0][0], seen[1][0])
        self.assertEqual(seen[1][1]['error'], 'Decisive source unavailable: OLD')

    def test_presentation_repair_receives_error_and_previous_output_in_same_deadline(self):
        self.state['role_contract_version'] = 1
        seen = []
        previous = {'status': 'proposed', 'reason': 'fixture', 'patch_json': '{}', 'sources': []}
        def run(role, schema, state, workspace, run_dir):
            seen.append((state['_role_deadline'], u.select_inputs(role, state)))
            return copy.deepcopy(previous)
        def check(value, state):
            if len(seen) == 1:
                raise rt.Blocked('Proposed-method chapter is incomplete: exact field is missing')
        with patch.object(h, 'run_role', side_effect=run):
            h.checked_role('producer-method', h.PATCH, self.state, self.workspace, self.run, check)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0][0], seen[1][0])
        self.assertNotIn('repair_context', seen[0][1])
        context = seen[1][1]['repair_context']
        self.assertIn('exact field is missing', context['error'])
        self.assertEqual(context['previous_output'], previous)
        self.assertNotIn('repair_context', self.state)

    def test_dependency_cannot_be_skipped(self):
        with self.assertRaisesRegex(rt.Blocked, 'dependency'):
            u.unit('producer-assets', h.ASSETS, self.state, self.workspace, self.run,
                   unittest.mock.Mock(), dependencies=['producer-design'])

    def test_minimal_design_defers_full_presentation_gate(self):
        self.state['config'].update(reader_friendly=True, report_profile='proposed-method')
        h.design_format(self.design, self.state)
        self.state.pop('execution_contract_version')
        with self.assertRaises(rt.Blocked):
            h.design_format(self.design, self.state)

    def test_execution_receipt_is_reused_and_output_mutation_is_rejected(self):
        directory = self.run/'001-checks'/'001'; directory.mkdir(parents=True)
        with tempfile.TemporaryDirectory() as scratch:
            with patch.object(h, 'sandbox_command', side_effect=lambda _s, _n, argv: argv):
                key = h.execute_check('python3 -c "print(42)"', ['R1'], self.state,
                                      self.workspace, directory, Path(scratch), {})
                with patch.object(h, 'capture', side_effect=AssertionError('must not execute again')):
                    reused = h.execute_check('python3 -c "print(42)"', ['R1'], self.state,
                                              self.workspace, directory, Path(scratch), {})
                self.assertEqual(key, reused)
                (directory/'stdout.log').write_text('tampered')
                with self.assertRaisesRegex(rt.Blocked, 'output changed'):
                    h.execute_check('python3 -c "print(42)"', ['R1'], self.state,
                                    self.workspace, directory, Path(scratch), {})

    def test_unconfirmed_execution_is_not_replayed(self):
        key = u.execution_key(self.state, 'false', ['R1'], None, None)
        self.state['execution_units'] = {key: {'status': 'running'}}
        with self.assertRaisesRegex(rt.Blocked, 'interrupted command'):
            u.prior_execution(self.state, self.workspace, key)

    def test_scoped_review_cannot_claim_other_criterion(self):
        self.state['unit_task'] = {'criterion_ids': ['R2']}
        bad = copy.deepcopy(self.review); bad['dossier_json'] = ''
        with self.assertRaisesRegex(rt.Blocked, 'exactly'):
            h.scoped_review_format(bad, self.state)

    def test_candidate_unit_cannot_mutate_other_candidate(self):
        value = {'patch_json': json.dumps({'candidate': self.draft['candidates'][1],
                 'sources': [], 'claims': [], 'comparison': []})}
        with self.assertRaisesRegex(rt.Blocked, 'assigned candidate'):
            h.patch_candidate(copy.deepcopy(self.draft), value, 'A')

    def test_presentation_can_repeat_reference_but_cannot_replace_core_evidence(self):
        draft=copy.deepcopy(self.draft)
        draft['sources']=[{'id':'S1','title':'Official source','url':'https://example.org/doc',
                          'local_path':None,'read_level':'relevant_sections'}]
        value={'patch_json':json.dumps({'reader_guide':{'takeaway':'Measured scope'}}),
               'sources':[{'id':'S1','title':'Official source','url':'https://example.org/doc',
                           'path':'','locator':'actual repeated passage','read_level':'relevant_sections'}]}
        h.merge_presentation(draft,value,'reader_guide')
        self.assertEqual(draft['reader_guide']['takeaway'],'Measured scope')
        value['sources'][0]['url']='https://example.org/different'
        with self.assertRaisesRegex(rt.Blocked,'Presentation unit changed'):
            h.merge_presentation(draft,value,'reader_guide')


if __name__ == '__main__':
    unittest.main()
