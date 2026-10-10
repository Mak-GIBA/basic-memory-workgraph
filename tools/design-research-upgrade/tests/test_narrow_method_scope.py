"""Structural exception tests use fictional records, not research evidence."""
from copy import deepcopy
import json
import tempfile
from pathlib import Path
import sys
import unittest

import test_stages
import proposal_report as report

FIXTURES = Path(__file__).resolve().parents[1] / 'core_upgrade/previous_report_upgrade/tests'
sys.path.insert(0, str(FIXTURES))
from fixtures import fixture


class NarrowMethodScopeTests(unittest.TestCase):
    def narrow(self):
        dossier = fixture()
        ideas = dossier['method_ideas']
        selected = ideas['selection']['leading_candidate_id']
        ideas['candidates'] = [c for c in ideas['candidates'] if c['id'] == selected]
        ideas['selection']['rejected_candidate_ids'] = []
        dossier['candidates'] = [c for c in dossier['candidates'] if c['baseline'] or c['id'] == selected]
        ideas['comparison_plan']['exception_reason'] = (
            'The user explicitly fixed the comparison to the existing method and one proposed method; '
            'adding unrelated mechanisms would change that question rather than test it.')
        return dossier

    def test_scoped_two_method_report_keeps_legacy_breadth_requirement(self):
        d = self.narrow()
        self.assertTrue(report.validation_issues(d))
        self.assertEqual(report.validation_issues(d, allow_single_proposal=True), [])
        from method_workflow import additional_gate_reasons
        state = {'execution_contract_version': 2, 'dossier': d,
                 'config': {'mode': 'research', 'report_profile': 'proposed-method', 'target_methods': 5}}
        self.assertEqual(additional_gate_reasons(state), [])
        state.pop('execution_contract_version')
        self.assertTrue(additional_gate_reasons(state))

    def test_v2_preview_uses_completed_presentation_before_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            run = workspace / 'runs' / 'run1'
            run.mkdir(parents=True)
            state = {'execution_contract_version': 2,
                     'config': {'mode': 'research', 'report_profile': 'proposed-method', 'target_methods': 5},
                     'proposal': {'dossier_json': '{}'},
                     'proposal_design': {'dossier_json': json.dumps(self.narrow())}}
            report.prepare_preview(state, workspace, run)
            preview = state['method_report_preview']
            self.assertEqual(preview['status'], 'rendered')
            chapter = workspace / preview['path']
            self.assertTrue(chapter.is_file())
            self.assertEqual(len(list(chapter.parent.joinpath('figures').rglob('*.svg'))), 3)
            self.assertIn('not empirical or visual-review evidence', preview['scope'])

    def test_scope_exception_does_not_remove_evidence_or_mechanism_gates(self):
        d = self.narrow()
        for change in ('reason', 'source', 'mechanism'):
            with self.subTest(change=change):
                bad = deepcopy(d)
                ideas = bad['method_ideas']
                if change == 'reason':
                    ideas['comparison_plan']['exception_reason'] = 'too short'
                elif change == 'source':
                    ideas['sources'] = ideas['sources'][:1]
                else:
                    ideas['candidates'][0]['mechanistic_explanation'] = ''
                self.assertTrue(report.validation_issues(bad, allow_single_proposal=True))
