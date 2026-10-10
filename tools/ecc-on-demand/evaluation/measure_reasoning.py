#!/usr/bin/env python3
"""Explicit paired Codex/MCP experiment; never called by the installer or tests.

Normal Codex authentication is used. Only synthetic tasks are supplied. The final
answers, usage and invocation metadata are retained, not private reasoning logs.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import tempfile
import time
import tomllib


def task_set():
    posterior = round(10000 * (.01 * .95) / (.01 * .95 + .99 * .05))
    choices = []
    for permutation in itertools.permutations('ABCDE'):
        pos = {x: permutation.index(x) for x in permutation}
        if pos['C'] < pos['A'] and pos['D'] == pos['B'] + 1 and pos['E'] == 2 and pos['A'] > pos['E']:
            choices.append(''.join(permutation))
    return [
        {'id': 'critical-path', 'input': '同時実行数は無制限。A=4分、B=3分(A後)、C=6分(A後)、D=2分(BとC後)、E=5分(B後)、F=1分(DとE後)。開始0、待機なし。全作業の完了時刻を整数の分で答える。', 'expected': 13},
        {'id': 'duplicate-test', 'input': '有病率1%、感度95%、偽陽性率5%。1回の検査結果が陽性だった。その同じ結果が誤って2件として複製保存された。2回の独立検査ではない。この情報での疾病確率をbasis points(1%=100bp)にして四捨五入した整数で答える。', 'expected': posterior},
        {'id': 'deadline-boundary', 'input': '初回試行開始1000ms、絶対期限1700ms。全試行は瞬時に失敗する。再試行待機100,200,400msの順。試行は開始時刻が期限より厳密に小さい場合だけ許可。実際に開始する全試行の時刻を整数配列で答える。', 'expected': [1000, 1100, 1300]},
        {'id': 'order-constraints', 'input': 'A,B,C,D,Eを各1回並べる。CはAより前。DはBの直後。Eは3番目。AはEより後。条件を満たす全配列を5文字文字列の配列にして辞書順に答える。', 'expected': sorted(choices)},
        {'id': 'null-join', 'input': 'users(id):1,2,3。events(user_id,amount):(1,10),(1,NULL),(2,0)。SELECT COUNT(*), COUNT(e.amount), COUNT(DISTINCT u.id), SUM(e.amount) FROM users u LEFT JOIN events e ON u.id=e.user_id の4値を整数配列で答える。SQLのNULL規則に従う。', 'expected': [4, 2, 3, 10]},
        {'id': 'conditional-retry', 'input': '再試行許可は「(HTTP statusが429または503) かつ idempotent=true かつ attempt<3」。ケース順:(503,true,2),(503,false,0),(429,true,3),(500,true,0),(429,true,1)。許可結果をboolean配列で答える。', 'expected': [True, False, False, False, True]},
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--repetitions', type=int, default=2, choices=[1, 2, 3])
    parser.add_argument('--server-script', type=Path, help='Use the already installed pinned server with node; avoids package download during timed trials')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cfg = tomllib.loads((Path.home()/'.codex/config.toml').read_text())
    model, effort = cfg['model'], cfg.get('model_reasoning_effort', 'medium')
    tasks = task_set()
    contract = {'purpose': 'Compare actual final reasoning answers with/without Sequential Thinking',
                'tasks': tasks, 'model': model, 'effort': effort, 'repetitions': args.repetitions,
                'primary_metric': 'Exact JSON final-answer accuracy, every task and failure retained',
                'secondary_metrics': ['end-to-end wall seconds including startup/model/tools', 'reported input/output tokens'],
                'adoption_rule': 'For default adoption require at least one additional correct task without regressions across repeats and <=10% mean latency increase. Ties do not support default adoption.',
                'limitations': 'Six synthetic tasks, two balanced batch trials by default, not a population estimate; no human work-time measurement.'}
    if args.server_script:
        package = json.loads((args.server_script.resolve().parents[1]/'package.json').read_text())
        assert package['name']=='@modelcontextprotocol/server-sequential-thinking' and package['version']=='2026.8.31'
    contract['server_launch'] = 'node, already installed 2026.8.31' if args.server_script else 'npx pinned 2026.8.31, includes cache lookup'
    encoded = json.dumps(contract, ensure_ascii=False, sort_keys=True).encode()
    contract_hash = hashlib.sha256(encoded).hexdigest()
    (args.out/'reasoning-contract.json').write_text(json.dumps(contract, ensure_ascii=False, indent=2)+'\n')
    schema = {'type': 'object', 'properties': {'answers': {'type': 'array', 'items': {
        'type': 'object', 'properties': {'id': {'type': 'string'}, 'answer': {'type': 'string'}},
        'required': ['id', 'answer'], 'additionalProperties': False}}},
        'required': ['answers'], 'additionalProperties': False}
    prompt = ('以下の6問の最終答えだけをJSON形式で返してください。answerは答えのJSONを文字列にしたものです。'
              '問題の文脈以外の資料は不要です。shell、web、ファイル読取、subagentは使用しないでください。'
              'sequential-thinkingが使用可能なら、検算項目の短い要約を2〜4回記録してから最終答えを返してください。'
              '詳細な思考過程は出力不要です。使用できない場合はそのまま答えてください。\n'
              +json.dumps([{k: t[k] for k in ['id', 'input']} for t in tasks], ensure_ascii=False))
    rows = []
    with tempfile.TemporaryDirectory(prefix='ecc-reasoning-model-') as temporary:
        scratch = Path(temporary)
        (scratch/'schema.json').write_text(json.dumps(schema))
        for repetition in range(args.repetitions):
            order = ['native', 'sequential-thinking'] if repetition % 2 == 0 else ['sequential-thinking', 'native']
            for name in order:
                output = scratch/'final.json'; output.unlink(missing_ok=True)
                argv = ['codex', 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral',
                        '--skip-git-repo-check', '--sandbox', 'read-only', '--model', model,
                        '-c', 'model_reasoning_effort='+json.dumps(effort), '--json',
                        '--output-schema', str(scratch/'schema.json'), '--output-last-message', str(output)]
                if name == 'sequential-thinking':
                    command = 'node' if args.server_script else 'npx'
                    server_args = [str(args.server_script.resolve())] if args.server_script else ['-y', '@modelcontextprotocol/server-sequential-thinking@2026.8.31']
                    argv += ['-c', 'mcp_servers.sequential-thinking.command='+json.dumps(command),
                             '-c', 'mcp_servers.sequential-thinking.args='+json.dumps(server_args),
                             '-c', 'mcp_servers.sequential-thinking.startup_timeout_sec=60']
                argv += ['-']
                start = time.monotonic()
                try:
                    completed = subprocess.run(argv, input=prompt, text=True, capture_output=True, cwd=scratch, timeout=360)
                    events = []
                    for line in completed.stdout.splitlines():
                        try: events.append(json.loads(line))
                        except ValueError: pass
                    calls = [e['item'] for e in events if e.get('type')=='item.completed'
                             and e.get('item', {}).get('type') not in {'agent_message', 'reasoning'}]
                    call_metadata = [{k: call[k] for k in ['type', 'server', 'tool', 'status', 'error'] if k in call} for call in calls]
                    usage = next((e.get('usage') for e in reversed(events) if e.get('type')=='turn.completed'), None)
                    answers = json.loads(output.read_text())['answers'] if output.exists() and completed.returncode==0 else []
                    actual = {}
                    for answer in answers:
                        actual[answer['id']] = json.loads(answer['answer'])
                    invalid_tools = [call for call in calls if call.get('type')!='mcp_tool_call' or call.get('server')!='sequential-thinking']
                    error = 'Unexpected tool invocation' if invalid_tools else None if completed.returncode==0 else 'Codex execution failed'
                    exposed = any(call.get('server')=='sequential-thinking' and call.get('status')=='completed' for call in calls)
                    if name=='sequential-thinking' and not exposed: error = error or 'Sequential Thinking was not successfully used'
                    row = {'candidate': name, 'trial': repetition+1, 'outputs': actual, 'usage': usage,
                           'tool_calls': call_metadata, 'exit_code': completed.returncode, 'error': error}
                except subprocess.TimeoutExpired:
                    row = {'candidate': name, 'trial': repetition+1, 'outputs': {}, 'usage': None,
                           'tool_calls': [], 'exit_code': None, 'error': '360-second model execution timeout'}
                row.update(elapsed_seconds=round(time.monotonic()-start, 3),
                           checked_at=datetime.now(timezone.utc).isoformat(), contract_sha256=contract_hash,
                           prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
                row['correct'] = sum(t['id'] in row['outputs'] and row['outputs'][t['id']]==t['expected'] for t in tasks)
                row['treatment_valid'] = row['error'] is None
                row['total'] = len(tasks)
                rows.append(row)
                (args.out/'reasoning-results.json').write_text(json.dumps({'contract_sha256': contract_hash, 'rows': rows}, ensure_ascii=False, indent=2)+'\n')
                print(json.dumps({k: row[k] for k in ['candidate', 'trial', 'correct', 'total', 'elapsed_seconds', 'error']}) , flush=True)


if __name__ == '__main__':
    main()
