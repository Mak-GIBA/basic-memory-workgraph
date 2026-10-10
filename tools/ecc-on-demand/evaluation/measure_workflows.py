#!/usr/bin/env python3
"""Opt-in real-model paired trials. Never run by installers or ordinary tests.

Inputs/graders are frozen before calls. Keep final outputs, calls and wall time;
do not store hidden reasoning. Independent scenarios are not pooled rankings.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import functools
import hashlib
import http.server
import itertools
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import tomllib


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def reasoning():
    jobs = [(0, 3, 5), (1, 4, 8), (4, 6, 5), (5, 7, 10), (7, 9, 7), (8, 11, 11), (10, 12, 8), (12, 14, 12)]
    feasible = []
    for flags in itertools.product([0, 1], repeat=len(jobs)):
        chosen = [i for i, f in enumerate(flags) if f]
        if all(jobs[a][1] + 1 <= jobs[b][0] for a, b in zip(chosen, chosen[1:])):
            feasible.append((sum(jobs[i][2] for i in chosen), chosen))
    best = max(score for score, _ in feasible)
    edges = [('S','A',3),('S','B',2),('A','C',4),('A','D',2),('B','C',5),('B','D',3),
             ('C','E',1),('D','E',3),('D','F',4),('E','T',4),('F','T',3)]
    paths = []
    def walk(node, cost, path):
        if node == 'T': paths.append((cost, ''.join(path))); return
        for a, b, w in edges:
            if a == node: walk(b, cost+w, path+[b])
    walk('S', 0, ['S']); shortest = min(c for c, _ in paths)
    return [
      {'id':'interval-cooldown', 'input':'仕事は(start,end,profit)='+json.dumps(jobs)+
       '。仕事のindexは0始まり。次の仕事は前のend+1以上のstartだけ許可する。利益最大値と、それを達成する全index配列を辞書順で{profit:int, schedules:list}として答える。',
       'expected':{'profit':best,'schedules':sorted(s for p,s in feasible if p == best)}},
      {'id':'equal-shortest-paths','input':'有向非循環グラフの辺(from,to,cost)='+json.dumps(edges)+
       '。SからTの最小costと、それを達成する全path文字列を辞書順で{cost:int,paths:list}として答える。pathは頂点名を直接連結し矢印・区切り文字を入れない（例:SABT）。',
       'expected':{'cost':shortest,'paths':sorted(p for c,p in paths if c == shortest)}},
      {'id':'shared-budget','input':'絶対期限1000ms。試行は開始時刻が期限より厳密に小さいときだけ開始可。開始0。各試行失敗まで180ms。次の開始前に100,200,400msの順で待つ。試行自体は期限を超えても完了する。開始時刻の全配列を答える。','expected':[0,280,660]},
      {'id':'idempotency-race','input':'状態はbalance=100, seen={}。apply(key,delta)はキー未見ならbalance+=delta,seenに追加、既見なら無変更。最初のk1,-30は成功したが応答を喪失。再送k1,-30、k2,+15、k3,-50、再送k2,+15の順で実行。最後のbalanceとseenのキー辞書順を{balance:int,keys:list}で答える。','expected':{'balance':35,'keys':['k1','k2','k3']}},
    ]


def scenario(name, root, deps):
    if name == 'reasoning':
        return reasoning(), {'command':'node','args':[str(deps/'@modelcontextprotocol/server-sequential-thinking/dist/index.js')],
                            'env':{'DISABLE_THOUGHT_LOGGING':'true'}}, 'sequential-thinking', ''
    if name == 'documentation':
        tasks = [
          {'id':'pydantic-default','input':'公式文書の場所を探し、Pydantic v2でdefault値もfield_validatorと型検証の対象にする設定名と、既定でdefaultが検証されるかを{setting:str,default_validated:bool}で答える。','expected':{'setting':'validate_default','default_validated':False}},
          {'id':'httpx-pool','input':'HTTPXでPoolTimeoutが意味する待ち対象を探す。接続poolからの接続取得ならpool_acquire、レスポンス全体の期限ならtotal_responseで答える。','expected':'pool_acquire'},
          {'id':'tenacity-stop','input':'Tenacityのstop_before_delayとstop_after_delayを調べる。次のwaitを含めると最大時間を超える試行を開始前に止める方の識別子を答える。','expected':'stop_before_delay'},
        ]
        return tasks, {'command':'node','args':[str(deps/'@upstash/context7-mcp/dist/index.js')]}, 'context7', '最初にlibrary解決から行い、該当文書を取得してください。URLやlibrary IDは事前に与えていません。'
    if name in ('parallel','cloudflare'):
        tasks = [
          {'id':'python-replace','input':'Pythonのos.replaceの原子的置換保証は成功時に条件付きか、常に別filesystemでも成功するか。公式文書を探し{atomic_on_success:bool,cross_filesystem_guaranteed:bool}で答える。','expected':{'atomic_on_success':True,'cross_filesystem_guaranteed':False}},
          {'id':'durable-object-alarm','input':'Cloudflare Durable Objectsのalarmは各Objectに同時に設定できる数と、失敗時配送がat-least-onceかexactly-onceか。公式文書を探し{alarms:int,delivery:str}で答える。','expected':{'alarms':1,'delivery':'at-least-once'}},
        ]
        if name == 'cloudflare':
            tasks = tasks[1:]
        return tasks, {'url':'https://search.parallel.ai/mcp' if name == 'parallel' else 'https://docs.mcp.cloudflare.com/mcp'}, name, ''
    if name in ('playwright','chrome'):
        tasks = [
          {'id':'checkout','input':'表示された画面からcoupon SAVE10を適用し、商品2個を注文する。表示totalとconfirmationを{total:str,confirmation:str}で答える。画面操作を完了した結果のみ。','expected':{'total':'306','confirmation':'order-2-SAVE10'}},
          {'id':'diagnosis','input':'診断画面を開き、画面のfailureに対応するHTTP statusと、consoleに出たerror codeを{status:int,code:str}で答える。console/networkの実際の記録を調べる。','expected':{'status':503,'code':'E_CHECKOUT_RETRY'}},
        ]
        cfg = {'command':'node','args':[str(deps/'@playwright/mcp/cli.js'),'--headless','--isolated','--executable-path','/usr/bin/google-chrome']} if name == 'playwright' else {
              'command':'node','args':[str(deps/'chrome-devtools-mcp/build/src/bin/chrome-devtools-mcp.js'),'--headless','--isolated','--no-usage-statistics','--no-performance-crux']}
        return tasks, cfg, name, 'UI課題はクリック・入力・スナップショットで進め、診断は実console/networkで確認してください。fixtureソースの直接読取で答えてはいけません。'
    raise ValueError(name)


SCHEMA = {'type':'object','properties':{'answers':{'type':'array','items':{'type':'object',
          'properties':{'id':{'type':'string'},'answer':{'type':'string'},'sources':{'type':'array','items':{'type':'string'}}},
          'required':['id','answer','sources'],'additionalProperties':False}}},'required':['answers'],'additionalProperties':False}


def call(prompt, cfg, name, model, effort, root, timeout, *, browser=False, raw_answer_ids=()):
    output = root/'final.json'; output.unlink(missing_ok=True)
    (root/'schema.json').write_text(json.dumps(SCHEMA))
    argv = ['codex','exec','--ignore-user-config','--ignore-rules','--ephemeral','--skip-git-repo-check',
            '--sandbox','workspace-write' if browser else 'read-only','--model',model,'-c','model_reasoning_effort='+json.dumps(effort),
            '-c','web_search="live"','--json','--output-schema',str(root/'schema.json'),'--output-last-message',str(output)]
    for key,value in (cfg or {}).items():
        if key == 'env':
            for env_key, env_value in value.items(): argv += ['-c',f'mcp_servers.{name}.env.{env_key}='+json.dumps(env_value)]
        else:
            argv += ['-c',f'mcp_servers.{name}.{key}='+json.dumps(value)]
    if cfg: argv += ['-c',f'mcp_servers.{name}.startup_timeout_sec=60']
    if browser:
        argv += ['-c','sandbox_workspace_write.network_access=true']
    argv += ['-']
    start = time.monotonic(); events = []
    try:
        completed = subprocess.run(argv,input=prompt,text=True,capture_output=True,cwd=root,timeout=timeout)
        for line in completed.stdout.splitlines():
            try: events.append(json.loads(line))
            except ValueError: pass
        calls = [e['item'] for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type') not in ('agent_message','reasoning')]
        answers = json.loads(output.read_text())['answers'] if completed.returncode==0 and output.exists() else []
        row = {'outputs':{a['id']:a['answer'] if a['id'] in raw_answer_ids else json.loads(a['answer']) for a in answers},
               'sources':{a['id']:a['sources'] for a in answers}, 'exit_code':completed.returncode,
               'error':None if completed.returncode==0 else 'model process failed',
               'tool_calls':[{k:c[k] for k in ('type','server','tool','status','error') if k in c} for c in calls],
               'usage':next((e.get('usage') for e in reversed(events) if e.get('type')=='turn.completed'),None)}
        if browser:
            # Public toy fixture only. Keep operational evidence, never reasoning.
            row['browser_tool_records']=[{k:c[k] for k in
                ('type','server','tool','status','error','arguments','result','command','aggregated_output') if k in c}
                for c in calls if c.get('type') in ('mcp_tool_call','command_execution')]
    except (subprocess.TimeoutExpired,ValueError) as error:
        row = {'outputs':{},'sources':{},'exit_code':None,'error':type(error).__name__, 'tool_calls':[],'usage':None}
    row.update(elapsed_seconds=round(time.monotonic()-start,3),prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),checked_at=datetime.now(timezone.utc).isoformat())
    if cfg and not any(c.get('type')=='mcp_tool_call' and c.get('server')==name and c.get('status')=='completed' for c in row['tool_calls']):
        row['error'] = row['error'] or 'treatment was not successfully used'
    return row


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scenario',required=True,choices=['reasoning','documentation','parallel','cloudflare','playwright','chrome'])
    p.add_argument('--deps',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--repetitions',type=int,choices=[1,2],default=2);p.add_argument('--timeout',type=int,default=360)
    a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    config=tomllib.loads((Path.home()/'.codex/config.toml').read_text()); model=config['model'];effort=config.get('model_reasoning_effort','medium')
    with tempfile.TemporaryDirectory(prefix='ecc-workflow-') as temp:
        root=Path(temp); tasks,cfg,name,extra=scenario(a.scenario,root,a.deps.resolve())
        url=''; server=None; owned_browser=None
        if a.scenario in ('playwright','chrome'):
            observed={'orders':[],'diagnoses':[]}
            html='''<!doctype html><title>Workflow fixture</title><main id="app"><button id="start">Start order</button></main><script>
            document.querySelector('#start').onclick=()=>{document.querySelector('#app').innerHTML='<label>Quantity <input id="qty" type="number"></label><label>Coupon <input id="coupon"></label><button id="review">Review</button>';
            document.querySelector('#review').onclick=()=>{let q=Number(document.querySelector('#qty').value),c=document.querySelector('#coupon').value;if(q<1||c!=='SAVE10'){alert('invalid');return}document.querySelector('#app').innerHTML='<output id="total">'+(q*170*.9)+'</output><button id="submit">Confirm</button>';document.querySelector('#submit').onclick=async()=>{let r=await fetch('/api/order',{method:'POST',body:JSON.stringify({quantity:q,coupon:c})}),order=await r.json();document.querySelector('#app').innerHTML='<output id="confirmation">'+order.confirmation+'</output>'}}};
            if(location.hash==='#diagnosis'){document.querySelector('#app').innerHTML='<output>failure</output>';fetch('/api/failure').then(r=>{console.error('E_CHECKOUT_RETRY',r.status);fetch('/api/diagnosis',{method:'POST',body:JSON.stringify({status:r.status,code:'E_CHECKOUT_RETRY'})})})}
            </script>'''
            class Handler(http.server.BaseHTTPRequestHandler):
                def do_POST(self):
                    try:
                        data=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
                        if self.path=='/api/order':
                            if data!={'quantity':2,'coupon':'SAVE10'}:raise ValueError('invalid order')
                            output={'total':'306','confirmation':'order-2-SAVE10'};observed['orders'].append(output)
                        elif self.path=='/api/diagnosis':
                            output=data;observed['diagnoses'].append(data)
                        else:raise ValueError('unknown path')
                        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(output).encode())
                    except (ValueError,TypeError):self.send_response(400);self.end_headers()
                def do_GET(self):
                    self.send_response(503 if self.path.startswith('/api/failure') else 200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(b'failure' if self.path.startswith('/api/failure') else html.encode())
                def log_message(self,*_args): pass
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}/'
            profile=root/'browser-profile';profile.mkdir()
            browser_start=time.monotonic()
            owned_browser=subprocess.Popen(['/usr/bin/google-chrome','--headless','--no-sandbox','--disable-gpu',
                '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+str(profile)],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            deadline=time.monotonic()+30
            while not (profile/'DevToolsActivePort').exists():
                if time.monotonic()>deadline or owned_browser.poll() is not None:raise RuntimeError('owned browser did not become ready')
                time.sleep(.05)
            port=(profile/'DevToolsActivePort').read_text().splitlines()[0];cdp='http://127.0.0.1:'+port
            browser_startup_seconds=round(time.monotonic()-browser_start,3)
            cfg['args']=[str(deps_path) for deps_path in cfg['args'][:1]]+(['--cdp-endpoint',cdp] if name=='playwright' else ['--browser-url',cdp,'--no-usage-statistics','--no-performance-crux'])
            cfg['default_tools_approval_mode']='approve'
            cfg['enabled_tools']=(['browser_navigate','browser_snapshot','browser_click','browser_fill_form','browser_network_requests','browser_console_messages','browser_tabs','browser_wait_for'] if name=='playwright' else ['new_page','navigate_page','take_snapshot','click','fill','fill_form','list_network_requests','list_console_messages','get_network_request','get_console_message','list_pages','select_page','wait_for'])
            # Native has the same browser executable/runtime, with direct API access.
            (root/'native-browser.txt').write_text('Use node with '+str(a.deps.resolve()/'playwright')+'; connect chromium.connectOverCDP('+json.dumps(cdp)+') to the already owned headless browser. Create a new context/page, use UI locators and console/request/response listeners. Close the page/context when done, do not close the shared browser. Do not read source code.\n')
        contract={'scenario':a.scenario,'tasks':tasks,'model':model,'effort':effort,'repetitions':a.repetitions,
                  'controls':['same tasks/model/effort/permissions','isolated new model context each condition','balanced A/B then B/A order','same public network/local fixture and installed browser'],
                  'primary':'exact JSON final task outcome; errors retained','secondary':'end-to-end wall seconds incl model/tool startup, reported usage and successful actual tool use',
                  'adoption_rule':'At least one additional correct outcome without regression and no more than 10% mean wall-time increase supports default adoption. A tie supports only task-specific use when concrete additional capability is evidenced.',
                  'limitations':['small fixed task set, no statistical significance claim','source links inspected separately; exact matching alone does not establish citation entailment','no human work-time or billed cost measurement'],
                  'server_config':cfg,'browser_scope':'For browser studies only: same owned CDP browser; startup outside model wall time, fresh page by navigation; ephemeral per-server allowlisted tools approved only in this fixture invocation. User settings unchanged.' if server else None}
        if server:
            contract['primary']='Exact final answer AND independent server order/diagnosis state. Browser operation records retained for verification.'
        ch=digest(contract);(a.out/'contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
        rows=[]
        prompt='次の課題の最終成果を答える。answerはJSONを文字列にしたもの。sourceには実際に使用した公式文書URLを入れる。最終回答だけでよく詳細思考は不要。'
        prompt+='MCPがあれば課題に対応するものを実際に使用する。なければ通常のweb/shell/直接APIで同じ課題を実施する。外部mutation、subagent、個人ファイル、インストールは禁止。'+extra
        if a.scenario=='reasoning': prompt+='sequential-thinkingがあれば検算要約を2〜4回記録し、詳細思考を出力しない。'
        if url: prompt+='対象URLは'+url+'。診断は同URLの#diagnosis。基準側はnative-browser.txtに記載した同じブラウザAPIを使用できる。'
        prompt+='\n'+json.dumps([{k:t[k] for k in ('id','input')} for t in tasks],ensure_ascii=False)
        try:
            for trial in range(a.repetitions):
                for treatment in ([False,True] if trial%2==0 else [True,False]):
                    if server:
                        observed['orders'].clear();observed['diagnoses'].clear()
                    row=call(prompt,cfg if treatment else None,name,model,effort,root,a.timeout,browser=bool(server))
                    if server:row['shared_browser_startup_seconds']=browser_startup_seconds
                    row.update(candidate=name if treatment else 'native',trial=trial+1,contract_sha256=ch)
                    row['grades']={t['id']:int(digest(row['outputs'].get(t['id']))==digest(t['expected'])) for t in tasks}
                    if server:
                        row['server_observations']=json.loads(json.dumps(observed))
                        for task in tasks:
                            key='orders' if task['id']=='checkout' else 'diagnoses'
                            row['grades'][task['id']] &= int(task['expected'] in row['server_observations'][key])
                    row['correct']=sum(row['grades'].values());row['total']=len(tasks);rows.append(row)
                    (a.out/'results.json').write_text(json.dumps({'contract_sha256':ch,'rows':rows},ensure_ascii=False,indent=2)+'\n')
                    print(json.dumps({k:row[k] for k in ('candidate','trial','correct','total','elapsed_seconds','error')}),flush=True)
        finally:
            if server: server.shutdown();server.server_close()
            if owned_browser:
                import signal
                try:os.killpg(owned_browser.pid,signal.SIGTERM);owned_browser.wait(timeout=5)
                except ProcessLookupError:pass
                except subprocess.TimeoutExpired:os.killpg(owned_browser.pid,signal.SIGKILL);owned_browser.wait()


if __name__=='__main__':main()
