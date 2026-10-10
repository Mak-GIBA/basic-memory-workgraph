#!/usr/bin/env python3
"""Regrade captured measurements offline; does not resample models or MCPs."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean


def same_json(actual, expected):
    # Distinguish booleans from numeric answers and preserve array ordering.
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(same_json(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(same_json(a, b) for a, b in zip(actual, expected))
    return actual == expected


def check(root):
    def read(name):
        return json.loads((root / name).read_text())

    for record in read('capture-manifest.json'):
        path = root / record['path']
        assert path.is_file() and not path.is_symlink(), record['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'], record['path']
    tasks = read('task-manifest.json')
    frozen = []
    for filename, key, prefix in (
            ('reasoning-contract.json', 'tasks', 'reasoning'),
            ('documentation-contract.json', 'tasks', 'documentation'),
            ('tools-contract.json', 'file_tasks', 'file'),
            ('tools-contract.json', 'browser_tasks', 'browser')):
        for task in read('evidence/' + filename)[key]:
            frozen.append({'id': prefix + '/' + task['id'], 'input': task['input'], 'expected': task['expected']})
    assert tasks == frozen
    labels = {t['id']: t for t in tasks}
    assert len(labels) == len(tasks) == 14
    trials, summary = [], {}

    def add(group, task_id, trial, candidate, output):
        key = group + '/' + task_id
        assert key in labels, key
        trials.append({'task_id': key, 'trial_id': str(trial),
                       'candidate_id': candidate, 'output': output})

    reasoning = read('evidence/reasoning-results.json')
    contract = read('evidence/reasoning-contract.json')
    digest = hashlib.sha256(json.dumps(contract, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    assert reasoning['contract_sha256'] == digest
    assert len(reasoning['rows']) == 4
    assert len({r['prompt_sha256'] for r in reasoning['rows']}) == 1
    for row in reasoning['rows']:
        assert row['candidate'] in ('native', 'sequential-thinking')
        assert row['contract_sha256'] == digest
        assert row['exit_code'] == 0 and row['error'] is None and row['treatment_valid']
        candidate = 'A' if row['candidate'] == 'native' else 'B'
        calls = row['tool_calls']
        if candidate == 'A':
            assert not calls
        else:
            assert calls and all(c['server'] == 'sequential-thinking' and c['status'] == 'completed' and not c.get('error') for c in calls)
        assert set(row['outputs']) == {t['id'] for t in contract['tasks']}
        for task in contract['tasks']:
            assert labels['reasoning/' + task['id']]['expected'] == task['expected']
            add('reasoning', task['id'], row['trial'], candidate, row['outputs'][task['id']])
    summary['reasoning_mean_seconds'] = {
        name: mean(r['elapsed_seconds'] for r in reasoning['rows'] if r['candidate'] == name)
        for name in ('native', 'sequential-thinking')}

    documentation = read('evidence/documentation-results.json')
    doc_contract = read('evidence/documentation-contract.json')
    assert len(documentation['rows']) == 2
    for row in documentation['rows']:
        assert row['candidate'] in ('official-docs', 'context7')
        assert not row['tool_calls']
        prompt = '提供資料だけを参考に次の2問の最終答えを返してください。answerは答えのJSONを文字列にしてください。ツール、shell、web、subagentは使わないでください。\n'
        prompt += json.dumps({'questions': [{k: t[k] for k in ('id', 'input')} for t in doc_contract['tasks']],
                              'documents': documentation['documents'][row['candidate']]}, ensure_ascii=False)
        assert hashlib.sha256(prompt.encode()).hexdigest() == row['prompt_sha256']
        candidate = 'A' if row['candidate'] == 'official-docs' else 'B'
        assert set(row['outputs']) == {t['id'] for t in doc_contract['tasks']}
        for task in doc_contract['tasks']:
            assert labels['documentation/' + task['id']]['expected'] == task['expected']
            add('documentation', task['id'], 1, candidate, row['outputs'][task['id']])

    matches = []
    for path in [root / 'evidence/tools-results.json', *sorted((root / 'evidence/pilot').glob('*results.json'))]:
        retrieval = [r for r in json.loads(path.read_text()).get('public_retrieval', []) if r['candidate'] == 'context7']
        if [r['response'] for r in retrieval] == documentation['documents']['context7']:
            assert not any(r['tool_error'] for r in retrieval)
            assert sum(r['elapsed_seconds'] for r in retrieval) == doc_contract['context7_retrieval_seconds']
            matches.append(str(path.relative_to(root)))
    assert matches, 'The documentation input must match a retained Context7 retrieval'
    summary['documentation_retrieval_capture'] = matches

    tool_contract = read('evidence/tools-contract.json')
    tool_results = read('evidence/tools-results.json')
    tool_digest = hashlib.sha256(json.dumps(tool_contract, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    assert tool_results['contract_sha256'] == tool_digest
    supplementary = []
    for row in tool_results['rows']:
        assert row['candidate'] in ('native', 'token-optimizer', 'native-browser', 'playwright', 'chrome-devtools')
        assert not row.get('tool_error', False)
        if row['candidate'] == 'chrome-devtools':
            supplementary.append(row)
            continue
        group = 'file' if row['candidate'] in ('native', 'token-optimizer') else 'browser'
        candidate = 'A' if row['candidate'] in ('native', 'native-browser') else 'B'
        add(group, row['task_id'], row['trial'], candidate, row['output'])
    assert len(supplementary) == 4
    summary['chrome_devtools'] = {'correct': sum(same_json(r['output'], labels['browser/' + r['task_id']]['expected']) for r in supplementary), 'total': len(supplementary)}

    pairs = {}
    for row in trials:
        pair = pairs.setdefault((row['task_id'], row['trial_id']), {})
        assert row['candidate_id'] not in pair
        pair[row['candidate_id']] = row
    assert len(pairs) == 26 and all(set(pair) == {'A', 'B'} for pair in pairs.values())
    assert {key[0] for key in pairs} == set(labels)
    for group in ('reasoning', 'documentation', 'file', 'browser'):
        summary[group] = {}
        for candidate in ('A', 'B'):
            rows = [r for r in trials if r['candidate_id'] == candidate and r['task_id'].startswith(group + '/')]
            summary[group][candidate] = {
                'correct': sum(same_json(r['output'], labels[r['task_id']]['expected']) for r in rows),
                'total': len(rows)}
    return {'scope': 'Offline integrity check and regrading of actual captured outputs, not resampling',
            'tasks': tasks, 'trials': trials, 'summary': summary}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = check(args.root)
    if args.out:
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))
