from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = os.environ.get('CODEX_INTERFACE_SOURCE_ROOT')
SCRIPTS = (Path(SOURCE) if SOURCE else ROOT/'overlay')/'tools/design-research/skill/scripts'
sys.path.insert(0, str(SCRIPTS))
import evaluation_contract as ec
import harness as h
import runtime as rt
from evidence import add_record


def contract(purpose='effectiveness'):
    return {'purpose': purpose, 'baseline_id': 'A', 'candidate_ids': ['A', 'B'],
            'tasks': [{'id': 'T1', 'input': 1700, 'expected': True},
                      {'id': 'T2', 'input': 1701, 'expected': False}],
            'dataset': 'Two boundary inputs', 'controls': ['Same inputs, runtime and budget'],
            'budget': 'One deterministic local run', 'limitations': 'Boundary cases only',
            'metrics': [{'id': 'accuracy', 'criterion_id': 'R1', 'primary': True,
                         'kind': 'exact_match', 'unit': 'fraction', 'direction': 'higher',
                         'aggregation': 'mean', 'acceptance_delta': 0.25,
                         'grading': 'Final output compared with independent expected output',
                         'outcome_scope': 'final_outcome'}]}


class EffectivenessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root/'project'; self.project.mkdir()
        self.workspace = self.project/'docs/design-research/demo'; self.workspace.mkdir(parents=True)
        self.run = self.workspace/'runs/run1'; self.run.mkdir(parents=True)
        self.state = {'evaluation_contract_version': 1, 'iteration': 1, 'evidence': {},
                      'run_id': 'run1', 'sources': {}, 'phase': 'planning',
                      'config': {'evaluation_purpose': 'auto', 'phase_timeout': 60,
                                 'project': str(self.project), 'mode': 'research'},
                      'expected_source': {'head': '', 'files': {}},
                      'plan': {'criteria': [{'id': 'R1', 'kind': 'runtime', 'required': True}],
                               'evaluation_json': json.dumps(contract())}}
        ec.freeze(self.state)

    def dossier(self):
        return {'candidates': [{'id': 'A', 'baseline': True}, {'id': 'B', 'baseline': False}],
                'decision': {'status': 'provisional', 'candidate_id': 'B'}}

    def result(self, repeats=1):
        path = self.run/'results.json'
        tasks = [{'id': 'T1', 'input': 1700, 'expected': True},
                 {'id': 'T2', 'input': 1701, 'expected': False}]
        trials = [{'task_id': t['id'], 'trial_id': str(repeat), 'candidate_id': c,
                   'output': True if c == 'A' else t['expected']}
                  for repeat in range(repeats) for t in tasks for c in ('A', 'B')]
        data = {'contract_sha256': self.state['evaluation_contract_sha256'],
                'tasks': tasks, 'trials': trials}
        path.write_text(json.dumps(data))
        key = add_record(self.state, self.workspace, path, kind='artifact',
                         description='actual outcomes', experiment_id='E1')
        record = self.state['evidence'][key]
        receipt = self.run/'receipt.json'
        receipt.write_text(json.dumps({'artifacts': [{'path': record['path'], 'sha256': record['sha256']}]}))
        add_record(self.state, self.workspace, receipt, kind='experiment', experiment_id='E1',
                   description='execution', exit_code=0, timed_out=False, truncated=False)
        dossier = self.dossier()
        dossier['evaluation_result'] = {'contract_sha256': self.state['evaluation_contract_sha256'],
                                        'artifact_paths': [record['path']]}
        return dossier, data, path, key

    def rewrite(self, data, path, key):
        path.write_text(json.dumps(data)); self.state['evidence'][key]['sha256'] = rt.sha256(path)
        # Test fixture simulates a different actual execution, not modifying a published run.
        receipt = self.run/'receipt.json'; receipt.write_text(json.dumps({'artifacts': [{
            'path': self.state['evidence'][key]['path'], 'sha256': rt.sha256(path)}]}))
        next(r for r in self.state['evidence'].values() if r['kind'] == 'experiment')['sha256'] = rt.sha256(receipt)

    def test_unmeasured_effectiveness_cannot_complete(self):
        with self.assertRaisesRegex(rt.Blocked, 'unmeasured'): ec.evaluate(self.dossier(), self.state, self.workspace)

    def test_parent_grades_before_review_and_missing_binding_cannot_hide_results(self):
        d, _, _, _ = self.result()
        summary = ec.checkpoint_results(self.state, self.workspace)
        self.assertEqual(summary['status'], 'measured')
        self.assertFalse(self.state['evaluation_review_bound'])
        report = '\n'.join(ec.sections(self.state))
        self.assertIn('確認は未完了', report)
        self.assertIn('実行した具体例', report)
        self.assertNotIn('主要効果は未測定です', report)
        with self.assertRaisesRegex(rt.Blocked, 'independent review'):
            ec.evaluate(self.dossier(), self.state, self.workspace)
        self.assertEqual(self.state['evaluation_summary'], summary)
        self.assertEqual(ec.evaluate(d, self.state, self.workspace)['status'], 'measured')
        self.assertTrue(self.state['evaluation_review_bound'])

    def test_parent_checkpoint_rejects_modified_contract_and_stale_results(self):
        _, data, path, key = self.result()
        self.state['iteration'] += 1
        self.assertIsNone(ec.checkpoint_results(self.state, self.workspace))
        self.state['iteration'] -= 1
        data['contract_sha256'] = 'wrong'
        self.rewrite(data, path, key)
        with self.assertRaisesRegex(rt.Blocked, 'frozen contract'):
            ec.checkpoint_results(self.state, self.workspace)

    def test_design_can_finish_unmeasured_and_cannot_propose_measured_benefit(self):
        self.state['plan']['evaluation_json'] = json.dumps(contract('design'))
        self.state.pop('evaluation_contract_sha256'); ec.freeze(self.state)
        self.assertEqual(ec.evaluate(self.dossier(), self.state, self.workspace)['status'], 'unmeasured')
        d = self.dossier(); d['decision']['status'] = 'proposed'
        with self.assertRaisesRegex(rt.Blocked, 'provisional'): ec.evaluate(d, self.state, self.workspace)

    def test_explicit_purpose_cannot_be_downgraded(self):
        self.state['config']['evaluation_purpose'] = 'effectiveness'
        self.state['plan']['evaluation_json'] = json.dumps(contract('design'))
        with self.assertRaisesRegex(rt.Blocked, 'purpose'): ec.freeze(self.state)

    def test_bookkeeping_primary_metric_rejected(self):
        c = contract(); c['metrics'][0]['outcome_scope'] = 'tool_response'
        self.state['plan']['evaluation_json'] = json.dumps(c)
        with self.assertRaisesRegex(rt.Blocked, 'final task outcomes'): ec.freeze(self.state)

    def test_threshold_cannot_change_after_execution(self):
        c = contract(); c['metrics'][0]['acceptance_delta'] = 0
        self.state['plan']['evaluation_json'] = json.dumps(c)
        with self.assertRaisesRegex(rt.Blocked, 'changed'): ec.freeze(self.state)

    def test_grades_are_recomputed_and_repeats_are_not_distinct_tasks(self):
        d, _, _, _ = self.result(5)
        s = ec.evaluate(d, self.state, self.workspace)
        self.assertEqual((s['distinct_tasks'], s['paired_trials']), (2, 10))
        c = s['metrics'][0]['comparisons'][0]
        self.assertEqual((c['baseline'], c['candidate'], c['delta']), (.5, 1, .5))
        text = '\n'.join(ec.sections(self.state))
        self.assertIn('1701', text); self.assertIn('true', text); self.assertIn('false', text)
        self.assertIn(self.state['evidence']['EV-00001']['path'], text)

    def test_negative_or_equal_measurement_is_valid_research(self):
        d, data, path, key = self.result()
        for trial in data['trials']: trial['output'] = True
        self.rewrite(data, path, key)
        self.assertEqual(ec.evaluate(d, self.state, self.workspace)['status'], 'measured')
        d['decision']['status'] = 'proposed'
        with self.assertRaisesRegex(rt.Blocked, 'thresholds'): ec.evaluate(d, self.state, self.workspace)
        d['decision']['candidate_id'] = 'A'
        self.assertEqual(ec.evaluate(d, self.state, self.workspace)['status'], 'measured')

    def test_missing_pair_fails(self):
        d, data, path, key = self.result(); data['trials'].pop(); self.rewrite(data, path, key)
        with self.assertRaisesRegex(rt.Blocked, 'all candidates'): ec.evaluate(d, self.state, self.workspace)

    def test_result_cannot_change_frozen_inputs_or_labels(self):
        for key in ('input', 'expected'):
            with self.subTest(key=key):
                self.state['evidence'] = {}
                d, data, path, record = self.result()
                data['tasks'][0][key] = 'changed'; self.rewrite(data, path, record)
                with self.assertRaisesRegex(rt.Blocked, 'frozen evaluation'): ec.evaluate(d, self.state, self.workspace)

    def test_later_repetition_failure_is_shown_in_report(self):
        d, data, path, key = self.result(2)
        for trial in data['trials']:
            if trial['trial_id'] == '0': trial['output'] = next(t['expected'] for t in data['tasks'] if t['id'] == trial['task_id'])
        self.rewrite(data, path, key); ec.evaluate(d, self.state, self.workspace)
        text = '\n'.join(ec.sections(self.state))
        self.assertIn('試行 1', text); self.assertIn('1701', text)

    def test_old_summary_is_not_current_measurement(self):
        d, _, _, _ = self.result(); ec.evaluate(d, self.state, self.workspace)
        self.state['iteration'] = 2
        text = '\n'.join(ec.sections(self.state))
        self.assertIn('未測定', text); self.assertNotIn('条件を満たす', text)

    def test_scalar_and_numeric_error_grade_actual_values(self):
        for kind in ('absolute_error', 'scalar'):
            with self.subTest(kind=kind):
                self.state['evidence'] = {}; self.state.pop('evaluation_contract_sha256')
                c = contract(); c['tasks'] = [{'id': 'T1', 'input': 1, 'expected': 3},
                                             {'id': 'T2', 'input': 2, 'expected': 5}]
                c['metrics'][0].update(kind=kind, direction='lower')
                self.state['plan']['evaluation_json'] = json.dumps(c); ec.freeze(self.state)
                d, data, path, key = self.result(); data['tasks'] = copy.deepcopy(c['tasks'])
                for trial in data['trials']:
                    expected = next(t['expected'] for t in c['tasks'] if t['id'] == trial['task_id'])
                    trial.update(output=expected + (1 if trial['candidate_id'] == 'A' else 0),
                                 values={'accuracy': 1 if trial['candidate_id'] == 'A' else 0},
                                 grading_evidence='fixture: absolute error on final output')
                self.rewrite(data, path, key)
                comparison = ec.evaluate(d, self.state, self.workspace)['metrics'][0]['comparisons'][0]
                self.assertEqual(comparison['delta'], 1)

    def test_role_timeout_has_diagnostic_receipt_without_test_success(self):
        self.state['config'].update(slug='demo', allow_network=False)
        self.state['expected_source'] = rt.fingerprint(self.project, self.workspace)
        def stopped(argv, **kw):
            paths = {}
            for name in ('stdout', 'stderr'):
                p = kw['directory']/(name+'.log'); p.write_text('stopped role'); paths[name] = str(p)
            return {'paths': paths, 'duration_seconds': 60, 'exit_code': -15,
                    'timed_out': True, 'truncated': False, 'started_at': rt.now(), 'finished_at': rt.now()}
        with patch.object(h, 'capture', side_effect=stopped):
            with self.assertRaisesRegex(rt.Blocked, '制限時間'):
                h.run_role('producer-assets', h.ASSETS, self.state, self.workspace, self.run)
        role = self.state['roles'][0]
        receipt = json.loads((self.workspace/role['receipt']).read_text())
        self.assertTrue(receipt['timed_out']); self.assertEqual(receipt['duration_seconds'], 60)
        self.assertFalse(any(r['kind'] in {'test', 'experiment'} for r in self.state['evidence'].values()))

    def test_actual_format_retry_uses_remaining_time(self):
        self.state['config'].update(slug='demo', allow_network=False, phase_timeout=1)
        self.state['expected_source'] = rt.fingerprint(self.project, self.workspace)
        budgets = []
        def complete(argv, **kw):
            budgets.append(kw['timeout'])
            output = Path(argv[argv.index('--output-last-message')+1])
            if len(budgets) == 1:
                time.sleep(.04); output.write_text('not JSON')
            else:
                output.write_text(json.dumps({'status': 'proposed', 'reason': 'correct format', 'files': [], 'experiments': []}))
            paths = {}
            for name in ('stdout','stderr'):
                p = kw['directory']/(name+'.log'); p.write_text('fixture output'); paths[name] = str(p)
            return {'paths': paths, 'duration_seconds': .04, 'exit_code': 0, 'timed_out': False,
                    'truncated': False, 'started_at': rt.now(), 'finished_at': rt.now()}
        with patch.object(h, 'capture', side_effect=complete):
            h.checked_role('producer-assets', h.ASSETS, self.state, self.workspace, self.run)
        self.assertEqual(len(budgets), 2); self.assertLess(budgets[1], budgets[0] - .03)

    def test_output_must_be_final_not_only_claimed_score(self):
        d, data, path, key = self.result(); data['trials'][0].pop('output'); self.rewrite(data, path, key)
        with self.assertRaisesRegex(rt.Blocked, 'final output'): ec.evaluate(d, self.state, self.workspace)

    def test_old_iteration_receipt_rejected(self):
        d, _, _, _ = self.result(); self.state['iteration'] = 2
        with self.assertRaisesRegex(rt.Blocked, 'current'): ec.evaluate(d, self.state, self.workspace)

    def test_result_without_exporting_receipt_rejected(self):
        d, _, _, _ = self.result(); self.state['evidence'].pop('EV-00002')
        with self.assertRaisesRegex(rt.Blocked, 'exporting receipt'): ec.evaluate(d, self.state, self.workspace)

    def test_real_local_execution_exports_final_outputs_and_receipt(self):
        scratch = self.root/'scratch'; scratch.mkdir()
        c = self.state['evaluation_contract']
        code = "import json\n" + 'tasks = ' + repr(c['tasks']) + '\n'
        code += 'methods = {"A": lambda value: value <= 1701, "B": lambda value: value <= 1700}\n'
        code += 'trials = [{"task_id": t["id"], "trial_id": "1", "candidate_id": cid, "output": fn(t["input"])} for t in tasks for cid, fn in methods.items()]\n'
        code += 'with open("results.json", "w") as f: json.dump({"contract_sha256": ' + repr(self.state['evaluation_contract_sha256']) + ', "tasks": tasks, "trials": trials}, f)\n'
        (scratch/'compare.py').write_text(code)
        # The model/sandbox boundary is substituted for portability; Python actually runs.
        with patch.object(h, 'sandbox_command', side_effect=lambda mode, network, argv: argv):
            receipt_id = h.execute_check('python3 compare.py', ['R1'], self.state, self.workspace,
                         self.run/'executed', scratch, rt.test_environment(scratch),
                         experiment_id='E1', timeout=5, artifact_paths=['results.json'])
        receipt = json.loads((self.workspace/self.state['evidence'][receipt_id]['path']).read_text())
        d = self.dossier(); d['evaluation_result'] = {
            'contract_sha256': self.state['evaluation_contract_sha256'],
            'artifact_paths': [receipt['artifacts'][0]['path']]}
        summary = ec.evaluate(d, self.state, self.workspace)
        self.assertEqual(summary['metrics'][0]['comparisons'][0]['delta'], .5)
        report = '\n'.join(ec.sections(self.state))
        self.assertIn('1701', report); self.assertIn('true', report); self.assertIn('false', report)

    def test_tampered_result_rejected(self):
        d, _, path, _ = self.result(); path.write_text('{}')
        with self.assertRaisesRegex(rt.Blocked, 'changed'): ec.evaluate(d, self.state, self.workspace)

    def test_legacy_contract_unchanged(self):
        self.state.pop('evaluation_contract_version')
        self.assertIsNone(ec.evaluate({}, self.state, self.workspace))

    def test_preflight_missing_runtime_and_symlink_dependency(self):
        with self.assertRaisesRegex(rt.Blocked, 'runtime'): rt.preflight_commands(self.project, [{'command': 'unavailable_runtime_240 x'}])
        (self.project/'.venv').symlink_to(self.root/'elsewhere')
        with self.assertRaisesRegex(rt.Blocked, 'symlink'): rt.preflight_commands(self.project, [{'command': 'python3 test.py'}])
        self.assertEqual(rt.preflight_commands(self.project, [])['status'], 'ready')

    def test_preflight_handles_builtins_and_multiline_shell_without_execution(self):
        commands = [{'command': ': && touch SHOULD_NOT_EXIST'},
                    {'command': "python3 - <<'PY'\ntext = chr(39)\nprint(text)\nPY"}]
        self.assertEqual(rt.preflight_commands(self.project, commands)['status'], 'ready')
        self.assertFalse((self.project/'SHOULD_NOT_EXIST').exists())
        with self.assertRaisesRegex(rt.Blocked, 'syntax'):
            rt.preflight_commands(self.project, [{'command': 'python3 -c "unterminated'}])

    def test_format_repair_is_once_with_remaining_budget(self):
        failures = [rt.Blocked('Invalid structured output at $'), {'status': 'proposed'}]
        with patch.object(h, 'run_role', side_effect=failures) as run:
            self.assertEqual(h.checked_role('producer-assets', h.ASSETS, self.state, self.workspace, self.run)['status'], 'proposed')
        self.assertEqual(run.call_count, 2); self.assertNotIn('repair_context', self.state)
        with patch.object(h, 'run_role', side_effect=rt.Blocked('Invalid structured output at $')) as run:
            with self.assertRaises(rt.Blocked): h.checked_role('producer-assets', h.ASSETS, self.state, self.workspace, self.run)
        self.assertEqual(run.call_count, 2)

    def test_timeout_and_false_runtime_pass_are_not_format_repairs(self):
        for error in ('Codex reviewer failed or exceeded its execution/output limit', 'Runtime pass needs a current successful execution'):
            with patch.object(h, 'run_role', side_effect=rt.Blocked(error)) as run:
                with self.assertRaises(rt.Blocked): h.checked_role('reviewer', h.REVIEW, self.state, self.workspace, self.run)
            self.assertEqual(run.call_count, 1)

    def test_locator_and_history_checked_before_any_evidence_capture(self):
        path = self.project/'source.py'; path.write_text('line\n'*251)
        self.state['expected_source']['files']['source.py'] = 'fixture'
        v = {'dossier_json': '', 'issues': [], 'code_evidence': [{'path': 'source.py', 'line_start': 1, 'line_end': 248}]}
        with self.assertRaisesRegex(rt.Blocked, '<= 200'): h.review_format(v, self.state)
        v['code_evidence'][0]['line_end'] = 20; h.review_format(v, self.state)
        v['issues'] = [{'id': 'old-other-run', 'status': 'resolved'}]
        with self.assertRaisesRegex(rt.Blocked, 'initial'): h.review_format(v, self.state)
        self.assertEqual(self.state['evidence'], {})


if __name__ == '__main__': unittest.main()
