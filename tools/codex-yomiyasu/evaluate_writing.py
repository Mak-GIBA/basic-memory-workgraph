#!/usr/bin/env python3
"""Historical 1.1.0/1.2.0 paired writing evaluation; explicit paid-model use.
Fixtures are preserved separately from current install assets. Never run by install or --self-test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import tomllib

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT/'evaluation-v130'


def run(prompt, schema, output, workspace, model, effort):
    schema_path=workspace/'schema.json'
    schema_path.write_text(json.dumps(schema,ensure_ascii=False))
    argv=['codex','exec','--ignore-user-config','--ignore-rules','--ephemeral',
          '--skip-git-repo-check','--sandbox','read-only','--model',model,
          '-c','model_reasoning_effort='+json.dumps(effort), '--json',
          '--output-schema',str(schema_path),'--output-last-message',str(output),'-']
    start=time.monotonic()
    result=subprocess.run(argv,input=prompt,cwd=workspace,text=True,capture_output=True,timeout=480)
    if result.returncode:
        raise RuntimeError('Codex execution failed: '+result.stderr[-1600:])
    if not output.is_file():
        raise RuntimeError('Codex returned no output artifact')
    events=[]
    for line in result.stdout.splitlines():
        try: events.append(json.loads(line))
        except ValueError: pass
    calls=[x.get('item',{}).get('type') for x in events if x.get('type')=='item.completed'
           and x.get('item',{}).get('type') not in {'agent_message','reasoning'}]
    if calls:
        raise RuntimeError('Evaluation used tools rather than only the supplied guides: '+repr(calls))
    data=json.loads(output.read_text())
    usage=next((x.get('usage') for x in reversed(events) if x.get('type')=='turn.completed'),None)
    return data, {'elapsed_seconds':round(time.monotonic()-start,2),'usage':usage,'tool_calls':calls,
                  'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--model')
    parser.add_argument('--effort')
    parser.add_argument('--judge-only',action='store_true')
    parser.add_argument('--upstream-dir',type=Path,default=Path.home()/'.agents/skills/yomiyasu/upstream')
    args=parser.parse_args()
    config_path=Path.home()/'.codex/config.toml'
    config=tomllib.loads(config_path.read_text()) if config_path.exists() else {}
    model=args.model or config.get('model')
    effort=args.effort or config.get('model_reasoning_effort','medium')
    if not model:parser.error('Specify --model or configure the default Codex model')
    cases=json.loads((BASELINE/'tests/evaluation_cases.json').read_text())
    args.out.mkdir(parents=True,exist_ok=True)
    schema={'type':'object','properties':{'cases':{'type':'array','items':{'type':'object',
            'properties':{'id':{'type':'string'},'text':{'type':'string'}},'required':['id','text'],'additionalProperties':False}}},
            'required':['cases'],'additionalProperties':False}
    shared='ローカルファイル・ツールを使わず、この入力内のガイドだけを使ってください。参照資料はこの入力に展開済みです。\n'
    guides=[BASELINE/'assets/references/usage-policy.md',args.upstream_dir/'SKILL.upstream.md',
            args.upstream_dir/'references/domains/tech.md',args.upstream_dir/'references/domains/business.md']
    guide_text='\n'.join('【'+p.name+'】\n'+p.read_text() for p in guides)
    request='\n次の架空の原稿4件を指定読者向けに編集してください。事実・結論・数値・条件・断定の強さ・コード・表を保持し、新しい事実を加えないでください。各idと修正本文だけをJSONで返してください。\n'
    inputs=json.dumps([{'id':c['id'],'audience':c['audience'],'text':c['text']} for c in cases['cases']],ensure_ascii=False)
    with tempfile.TemporaryDirectory(prefix='paragraph-writing-eval-') as temp:
        workspace=Path(temp)
        results={}
        metadata={'model':model,'effort':effort,'runs_per_condition':1,
                  'cases_sha256':hashlib.sha256((BASELINE/'tests/evaluation_cases.json').read_bytes()).hexdigest(),
                  'guide_sha256':{str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else 'upstream/'+str(p.relative_to(args.upstream_dir)):
                                  hashlib.sha256(p.read_bytes()).hexdigest() for p in guides},
                  'invocation':'provided guide text, explicit application; not implicit selection',
                  'cli_version':subprocess.check_output(['codex','--version'],text=True).strip()}
        if not args.judge_only:
            baseline=(BASELINE/'tests/baseline-yomiyasu.md').read_text()
            additions=(BASELINE/'assets/paragraph-writing/SKILL.md').read_text()+'\n'+(BASELINE/'assets/paragraph-writing/references/examples.md').read_text()
            for name,entry,extra in [('yomiyasu',baseline,''),
                                     ('combined',(BASELINE/'assets/SKILL.md').read_text(),additions)]:
                print('Generating '+name,flush=True)
                prompt=shared+'【入口Skill】\n'+entry+'\n'+guide_text+'\n'+extra+request+inputs
                data,measurement=run(prompt,schema,workspace/(name+'.json'),workspace,model,effort)
                ids=[c['id'] for c in data['cases']]
                if len(ids)!=len(set(ids)) or set(ids)!={c['id'] for c in cases['cases']}:
                    raise RuntimeError('Missing or duplicate evaluation case')
                results[name]=data
                (args.out/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
                metadata[name]=measurement
                (args.out/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
        else:
            results={name:json.loads((args.out/(name+'.json')).read_text()) for name in ['yomiyasu','combined']}
        # Swap label order across cases; the evaluator does not receive skill names or guides.
        pairs=[]
        for i,case in enumerate(cases['cases']):
            order=['yomiyasu','combined'] if i%2==0 else ['combined','yomiyasu']
            pairs.append({**case,'variants':{label:next(x['text'] for x in results[name]['cases'] if x['id']==case['id'])
                                          for label,name in zip(['X','Y'],order)}})
        grade_schema={'type':'object','properties':{'cases':{'type':'array','items':{'type':'object',
            'properties':{'id':{'type':'string'},'variants':{'type':'array','items':{'type':'object','properties':{
                'label':{'type':'string','enum':['X','Y']},'mixed_topics':{'type':'integer','minimum':0},'unsupported_connections':{'type':'integer','minimum':0},
                'expected_structure_met':{'type':'boolean'},'fact_changes':{'type':'array','items':{'type':'string'}},
                'evidence':{'type':'string'}},'required':['label','mixed_topics','unsupported_connections','expected_structure_met','fact_changes','evidence'],
                'additionalProperties':False}}},'required':['id','variants'],'additionalProperties':False}}},'required':['cases'],'additionalProperties':False}
        judge_prompt=shared+'編集はせず、原文と各修正文を独立に評価してください。同じ因果・条件・例証に属する内容は一つの論点と数えます。'
        judge_prompt+=' 主題が混在し読みにくい段落の件数、原文で支えられない接続・論証の件数、事前指定の構成条件、各事実の意味保持を調べてください。'
        judge_prompt+=' fact_changesには脱落・捏造・否定/条件/推量/責任主体の変更だけを具体的に列挙してください。語順や意味を保つ言い換えは変更に数えません。'
        judge_prompt+='件数と判定には実際の本文に基づく根拠を添えてください。\n'+json.dumps(pairs,ensure_ascii=False)
        print('Reviewing anonymous output pairs',flush=True)
        judged,measurement=run(judge_prompt,grade_schema,workspace/'judged.json',workspace,model,effort)
        (args.out/'judged.json').write_text(json.dumps(judged,ensure_ascii=False,indent=2)+'\n')
        measurement.update(model=model,effort=effort)
        (args.out/'judge-metadata.json').write_text(json.dumps(measurement,ensure_ascii=False,indent=2)+'\n')
        print('Saved output pairs and anonymous review to '+str(args.out),flush=True)


if __name__=='__main__':main()
