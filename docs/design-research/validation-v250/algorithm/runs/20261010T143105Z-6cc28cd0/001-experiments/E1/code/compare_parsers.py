import argparse
import json
from pathlib import Path

CONTRACT_SHA256 = '22d3d5e226cfe37254cf287b0b7eb306c5a5245261d35d4e5c315fb918c89622'
FROZEN_TASKS = [
    {'id': 't0', 'input': 'true', 'expected': True},
    {'id': 't1', 'input': 'FALSE', 'expected': False},
    {'id': 't2', 'input': ' true ', 'expected': True},
    {'id': 't3', 'input': '\tfalse\n', 'expected': False},
    {'id': 't4', 'input': 'yes', 'expected': 'invalid'},
    {'id': 't5', 'input': '', 'expected': 'invalid'},
    {'id': 't6', 'input': '1', 'expected': 'invalid'},
]


def validate(token):
    if token == 'true':
        return True
    if token == 'false':
        return False
    return 'invalid'


def parse_a(value):
    return validate(value.lower())


def parse_b(value):
    return validate(value.strip(' \t\n\r\v\f').lower())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    tasks = json.loads(Path(args.input).read_text(encoding='utf-8'))
    canonical = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)
    if canonical(tasks) != canonical(FROZEN_TASKS):
        raise ValueError('Input fixture differs from frozen tasks; execution refused')

    trials = []
    failures = []
    correct = {'A': 0, 'B': 0}
    for task in tasks:
        for candidate_id, function in [('A', parse_a), ('B', parse_b)]:
            record = {'task_id': task['id'], 'trial_id': '1', 'candidate_id': candidate_id}
            try:
                actual = function(task['input'])
                record['output'] = actual
                matched = type(actual) is type(task['expected']) and actual == task['expected']
                record['exact_match'] = matched
                correct[candidate_id] += int(matched)
            except Exception as exc:
                error = {'type': type(exc).__name__, 'message': str(exc)}
                record['execution_error'] = error
                failures.append({'task_id': task['id'], 'candidate_id': candidate_id, 'error': error})
            trials.append(record)

    complete = not failures
    scores = {candidate: count / len(tasks) for candidate, count in correct.items()} if complete else None
    result = {
        'contract_sha256': CONTRACT_SHA256,
        'tasks': tasks,
        'trials': trials,
        'complete': complete,
        'failures': failures,
        'accuracy': scores,
        'paired_difference': scores['B'] - scores['A'] if complete else None,
        'limitations': 'Seven deterministic fixture tasks only; latency, memory and non-ASCII whitespace are unmeasured.',
    }
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False) + '\n', encoding='utf-8')
    return 0 if complete else 1


if __name__ == '__main__':
    raise SystemExit(main())
