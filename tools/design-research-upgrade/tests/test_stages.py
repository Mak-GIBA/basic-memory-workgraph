"""Resume orchestration fixtures; model choices are synthetic, not quality evidence."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = os.environ.get('CODEX_INTERFACE_SOURCE_ROOT')
SCRIPTS = (Path(SOURCE) if SOURCE else ROOT/'overlay')/'tools/design-research/skill/scripts'
sys.path.insert(0, str(SCRIPTS))
import harness as h
import runtime as rt
import evaluation_contract as ec
from test_effectiveness import contract


class StageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)/'project'; self.project.mkdir()
        self.workspace = self.project/'docs/design-research/demo'; self.workspace.mkdir(parents=True)
        self.run = self.workspace/'runs/run1'; self.run.mkdir(parents=True)
        from layout import initialize
        initialize(self.workspace)
        c = contract('design'); c['metrics'] = []
        self.state = {'evaluation_contract_version': 1, 'iteration': 1, 'evidence': {},
                      'run_id': 'run1', 'sources': {}, 'phase': 'proposal_design', 'status': 'running',
                      'config': {'evaluation_purpose': 'design', 'phase_timeout': 60,
                                 'project': str(self.project), 'mode': 'research', 'slug': 'demo',
                                 'brief': 'design only', 'test_env_file': '', 'max_iterations': 2,
                                 'reader_friendly': False, 'report_profile': 'comparison'},
                      'expected_source': rt.fingerprint(self.project, self.workspace),
                      'plan': {'domain': 'research', 'goal': 'design only', 'baseline': 'A',
                               'criteria': [{'id': 'R1', 'title': 'design', 'kind': 'research',
                                             'required': False, 'acceptance': 'documented'}],
                               'test_commands': [], 'evaluation_json': json.dumps(c)}}
        ec.freeze(self.state)
        self.draft = {'schema_version': 1, 'question': 'design', 'scope': 'synthetic test',
                      'checked_as_of': '2026-10-10', 'constraints': [], 'sources': [], 'claims': [],
                      'candidates': [{'id': c, 'name': c, 'baseline': c == 'A', 'summary': 'synthetic',
                                      'hard_constraints': []} for c in ('A', 'B')],
                      'comparison': [{'candidate_id': c, 'criterion': 'efficiency', 'finding': 'unmeasured',
                                      'basis': 'unknown', 'claim_ids': []} for c in ('A', 'B')],
                      'experiments': [], 'decision': {'status': 'provisional', 'candidate_id': 'A',
                       'rationale': 'No measured effect', 'claim_ids': [], 'unresolved': ['unmeasured'],
                       'revisit_when': ['runtime measurements requested']}}
        self.design = {'status': 'proposed', 'reason': 'design', 'dossier_json': json.dumps(self.draft), 'sources': []}
        self.assets = {'status': 'proposed', 'reason': 'no PoC requested', 'files': [], 'experiments': []}
        self.review = {'status': 'reviewed', 'reason': 'design documented', 'issues': [],
                       'checks': [{'check_id': 'R1', 'result': 'unknown', 'reason': 'synthetic design fixture', 'evidence_ids': []}],
                       'code_evidence': [], 'dossier_json': json.dumps(self.draft), 'sources': [],
                       'reference_implementations': [], 'complexity_ok': True, 'complexity_reason': 'No runtime change'}

    def drive(self, fn):
        with patch.object(h, 'checked_role', side_effect=fn):
            h.loop(self.state, self.workspace, self.run)

    def test_completed_design_is_reused_after_asset_timeout(self):
        called = []
        def first(role, *args):
            called.append(role)
            if role == 'producer-design': return copy.deepcopy(self.design)
            raise rt.Blocked('Codex producer-assets exceeded execution limit')
        with self.assertRaises(rt.Blocked): self.drive(first)
        self.assertEqual(self.state['phase'], 'experiment_assets')
        saved = (self.run/'state.json').read_bytes()
        self.assertIn(b'design_sha256', saved)
        def resumed(role, *args):
            called.append(role)
            return copy.deepcopy(self.assets if role == 'producer-assets' else self.review)
        self.drive(resumed)
        self.assertEqual(called.count('producer-design'), 1)
        self.assertEqual(self.state['status'], 'research_complete')
        self.assertEqual(self.state['evaluation_summary']['status'], 'unmeasured')

    def test_completed_assets_are_reused_after_execution_interruption(self):
        called = []
        def roles(role, *args):
            called.append(role)
            return copy.deepcopy({'producer-design': self.design, 'producer-assets': self.assets,
                                  'reviewer': self.review}[role])
        with patch.object(h, 'experiments', side_effect=rt.Cancelled('interrupt')):
            with self.assertRaises(rt.Cancelled): self.drive(roles)
        # Resume execution advances to a fresh iteration; validated stages transfer.
        self.state['producer_checkpoints']['2'] = copy.deepcopy(self.state['producer_checkpoints']['1'])
        self.state['iteration'] = 2
        self.drive(roles)
        self.assertEqual(called.count('producer-assets'), 1)
        self.assertEqual(called.count('producer-design'), 1)

    def test_pending_review_does_not_execute_again(self):
        self.state['phase'] = 'pending_review'
        with patch.object(h, 'experiments') as ex, patch.object(h, 'backend_checks') as checks:
            self.drive(lambda role, *args: copy.deepcopy(self.review))
        ex.assert_not_called(); checks.assert_not_called()

    def test_invalid_assets_are_not_saved_as_valid_checkpoint(self):
        broken = copy.deepcopy(self.assets)
        broken['experiments'] = [{'id': 'E1', 'command': 'python3 comparison.py', 'check_ids': ['unknown'],
                                 'input_files': [], 'artifact_paths': [], 'timeout_seconds': 1}]
        with self.assertRaisesRegex(rt.Blocked, 'known criteria'):
            self.drive(lambda role, *args: copy.deepcopy(self.design if role == 'producer-design' else broken))
        self.assertNotIn('assets', self.state['producer_checkpoints']['1'])

    def test_large_role_prompt_uses_stdin_and_avoids_duplicate_design(self):
        self.state['config'].update(allow_network=False)
        self.state['proposal_design'] = copy.deepcopy(self.design)
        self.state['proposal'] = {**copy.deepcopy(self.design), **copy.deepcopy(self.assets)}
        marker = '長い比較設計' * 30000
        self.state['proposal']['dossier_json'] = marker
        self.state['proposal_design']['dossier_json'] = marker
        prompt = h.role_prompt('reviewer', self.state)
        self.assertEqual(prompt.count(marker), 1)
        def complete(argv, **kw):
            self.assertEqual(argv[-2:], ['--', '-'])
            self.assertNotIn(marker, ' '.join(argv))
            self.assertEqual(kw['input_text'], prompt)
            output = Path(argv[argv.index('--output-last-message')+1])
            output.write_text(json.dumps(self.assets))
            paths = {}
            for name in ('stdout', 'stderr'):
                p = kw['directory']/(name+'.log'); p.write_text('fixture'); paths[name] = str(p)
            return {'paths': paths, 'duration_seconds': 0, 'exit_code': 0,
                    'timed_out': False, 'truncated': False, 'started_at': rt.now(), 'finished_at': rt.now()}
        with patch.object(h, 'capture', side_effect=complete):
            self.assertEqual(h.run_role('reviewer', h.ASSETS, self.state, self.workspace, self.run), self.assets)

    def test_capture_delivers_large_utf8_stdin_to_real_child(self):
        payload = '比較設計と期待値\n' * 30000
        result = rt.capture([sys.executable, '-c',
                             'import sys,hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())'],
                            cwd=self.project, env=os.environ.copy(), directory=self.run/'stdin-smoke',
                            timeout=5, label='large-stdin', input_text=payload)
        import hashlib
        self.assertEqual(result['exit_code'], 0)
        self.assertFalse(result['timed_out'])
        actual = Path(result['paths']['stdout']).read_text().strip()
        self.assertEqual(actual, hashlib.sha256(payload.encode('utf-8')).hexdigest())

    def test_nested_design_and_review_json_get_one_format_repair(self):
        for role, schema, value, validator in (('producer-design', h.DESIGN, self.design, h.design_format),
                                                ('reviewer', h.REVIEW, self.review, h.review_format)):
            with self.subTest(role=role):
                broken = {**value, 'dossier_json': 'not JSON'}
                with patch.object(h, 'run_role', side_effect=[broken, copy.deepcopy(value)]) as run:
                    h.checked_role(role, schema, self.state, self.workspace, self.run, validator)
                self.assertEqual(run.call_count, 2)
                self.assertEqual(self.state['evidence'], {})

    def test_invalid_planner_json_is_repaired_before_checkpoint(self):
        self.state.pop('plan'); self.state.pop('evaluation_contract'); self.state.pop('evaluation_contract_sha256')
        self.state['config']['test_commands'] = []
        plan = {'goal': 'design', 'baseline': 'A', 'domain': 'research', 'queries': [],
                'criteria': [{'id': 'R1', 'title': 'design', 'kind': 'research', 'required': False, 'acceptance': 'documented'}],
                'test_commands': [], 'evaluation_json': '{'}
        fixed = copy.deepcopy(plan); fixed['evaluation_json'] = json.dumps(contract('design'))
        fixed['evaluation_json'] = json.dumps({**json.loads(fixed['evaluation_json']), 'metrics': []})
        with patch.object(h, 'run_role', side_effect=[plan, fixed]) as run:
            h.checked_role('planner', h.PLAN_V2, self.state, self.workspace, self.run, h.plan_candidate)
        self.assertEqual(run.call_count, 2); self.assertTrue(self.state['plan_validated'])
        self.assertNotEqual(self.state['plan']['evaluation_json'], '{')
        self.state.pop('plan'); self.state.pop('evaluation_contract'); self.state.pop('evaluation_contract_sha256')
        with patch.object(h, 'run_role', return_value=plan):
            with self.assertRaises(rt.Blocked):
                h.checked_role('planner', h.PLAN_V2, self.state, self.workspace, self.run, h.plan_candidate)
        self.assertNotIn('plan', self.state)


if __name__ == '__main__': unittest.main()
