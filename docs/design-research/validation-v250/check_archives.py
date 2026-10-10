#!/usr/bin/env python3
"""Verify saved real outputs offline; do not call models or replay commands."""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT.parents[2] / 'tools/design-research-upgrade/overlay/tools/design-research/skill/scripts'
sys.path.insert(0, str(SCRIPTS))
from evidence import assert_records
from evaluation_contract import evaluate
from execution_units import digest


def check():
    result = {}
    for name, expected in (('algorithm', 'research_complete'), ('literature', 'research_complete'), ('fix', 'passed')):
        workspace = ROOT / name
        manifest = json.loads((workspace / 'archive-manifest.json').read_text())
        for row in manifest:
            path = workspace / row['path']
            assert not path.is_symlink() and path.is_file()
            assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256'], row['path']
        paths = list(workspace.glob('runs/*/state.json'))
        assert len(paths) == 1
        state = json.loads(paths[0].read_text())
        assert state['status'] == expected and state['execution_contract_version'] == 2
        for unit in state['units'].values():
            assert not unit['required'] or unit['status'] == 'complete'
            if unit['status'] == 'complete':
                assert digest(unit['input']) == unit['input_sha256']
                assert digest(unit['result']) == unit['result_sha256']
                assert unit['config_sha256'] == digest(state['config'])
                assert unit['source_sha256'] == digest(unit['input']['source'])
        original_workspace = Path(state['workspace'])
        for original, expected_hash in state.get('unit_inputs', {}).items():
            path = workspace / Path(original).relative_to(original_workspace)
            assert not path.is_symlink() and path.is_file()
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash
        assert_records(state, workspace)
        records = [r for r in state['evidence'].values() if r['kind'] in ('test', 'experiment')]
        info = {'status': expected, 'units': len(state['units']),
                'executions': len(records), 'execution_exit_codes': [r['exit_code'] for r in records]}
        invocations = [json.loads(p.read_text()) for p in workspace.glob('runs/*/*/invocation.json')]
        role_receipts = [json.loads(p.read_text()) for p in workspace.glob('runs/*/*/receipt.json')]
        role_receipts = [r for r in role_receipts if 'role' in r]
        assert invocations and all(i['prompt_bytes'] <= 16 * 1024 for i in invocations)
        info['model_execution'] = {
            'invocations': len(invocations),
            'max_initial_prompt_bytes': max(i['prompt_bytes'] for i in invocations),
            'timed_out_receipts': sum(r['timed_out'] for r in role_receipts),
            'max_successful_role_seconds': max(r['duration_seconds'] for r in role_receipts
                                               if r['exit_code'] == 0 and not r['timed_out']),
            'configured_role_timeouts_seconds': sorted({r['configured_timeout_seconds'] for r in role_receipts}),
            'scope': 'Role receipts include development failures and resumptions; not an effectiveness comparison.'}
        if name != 'fix':
            graded = evaluate(state['dossier'], copy.deepcopy(state), workspace)
            assert graded == state['evaluation_summary']
            info['evaluation'] = graded
        result[name] = info
    return result


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, indent=2))
