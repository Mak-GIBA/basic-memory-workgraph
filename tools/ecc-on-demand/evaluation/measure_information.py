#!/usr/bin/env python3
"""Opt-in Token Optimizer information retention measured by actual model answers.

Prior context is supplied explicitly, not claimed to be a live conversation.
"""
import argparse
import asyncio
import json
from pathlib import Path
import tempfile
import tomllib
from measure_tools import MCP, body
from measure_workflows import call, digest


async def main(a):
    a.out.mkdir(parents=True,exist_ok=True)
    cfg=tomllib.loads((Path.home()/'.codex/config.toml').read_text());model=cfg['model'];effort=cfg.get('model_reasoning_effort','medium')
    cases=['first-read','prior-context-retained','new-context-shared-cache','new-context-force-full']
    expected={'retry_limit':7,'max_count':2439,'request_id':'req-6f93c1','error':'E_CACHE_CONTEXT_29','guard':'explicit_gate_b4'}
    document='\n'.join('background_'+str(i)+'=public synthetic unchanged context' for i in range(500))+'\n'+'\n'.join(k+'='+str(v) for k,v in expected.items())+'\n'
    contract={'model':model,'effort':effort,'expected':expected,'document':document,'document_sha256':digest(document),'cases':cases,'repetitions':2,
              'primary':'actual model final five-field answer, exact JSON matching',
              'controls':['same question/document/model/effort','same prior body supplied to both conditions only for prior-context-retained','server restarted with same isolated cache for new context','no tools in answer model'],
              'secondary':'actual returned UTF-8 bytes, reported model usage, model wall seconds',
              'limitations':['explicitly seeded prior context, not a live long conversation','one synthetic document, not billed-cost or population reasoning accuracy','scoped @ooples/token-optimizer-mcp 7.4.3 only; not ECC unscoped package']}
    ch=digest(contract);(a.out/'contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='ecc-information-model-') as temp:
        root=Path(temp);file=root/'document.txt';file.write_text(document)
        for trial in range(2):
            home=root/('cache-'+str(trial));command=['node',str(a.deps.resolve()/'@ooples/token-optimizer-mcp/dist/server/index.js')]
            mcp=await MCP(command,home,root).start();prior=''
            try:
                for case in cases:
                    if case=='new-context-shared-cache':
                        await mcp.close();mcp=await MCP(command,home,root).start();prior=''
                    params={'path':str(file),'maxSize':200000}
                    if case=='new-context-force-full':params['diffMode']=False
                    result=await mcp.call('smart_read',params);content=body(result)
                    ref=result.get('_meta',{}).get('tokenOptimizer',{}).get('disclosureRef')
                    if ref:content+='\n'+body(await mcp.call('expand',{'ref':ref,'reason':'Need exact synthetic evaluation fields'}))
                    context=prior if case=='prior-context-retained' else ''
                    for treatment in ([False,True] if trial==0 else [True,False]):
                        current=content if treatment else document
                        prompt='提供内容からretry_limit(int),max_count(int),request_id(str),error(str),guard(str)の5値を抽出して答える。全5値が確認できなければ推測せず{}と答える。id="fields",answerはJSON文字列,sources=[]。ツール・web・shellは使用しない。\n'+json.dumps({'prior_context':context,'current_read':current},ensure_ascii=False)
                        row=await asyncio.to_thread(call,prompt,None,'token-optimizer',model,effort,root,360)
                        row.update(case=case,trial=trial+1,candidate='token-optimizer' if treatment else 'native',
                            contract_sha256=ch,current_response=current,response_bytes=len(current.encode()),prior_context_bytes=len(context.encode()),
                            tool_error=bool(result.get('isError')) if treatment else False,
                            actual_read_calls=['smart_read']+(['expand'] if ref else []) if treatment else ['full-read'])
                        row['correct']=int(digest(row['outputs'].get('fields'))==digest(expected));row['total']=1
                        if row['tool_calls']:row['error']='answer model used an unexpected tool'
                        rows.append(row);(a.out/'results.json').write_text(json.dumps({'contract_sha256':ch,'rows':rows},ensure_ascii=False,indent=2)+'\n')
                        print(json.dumps({k:row[k] for k in ('candidate','case','trial','correct','response_bytes','elapsed_seconds','error')}),flush=True)
                    if case=='first-read':prior=content
            finally:await mcp.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--deps',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    asyncio.run(main(p.parse_args()))
