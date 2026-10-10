#!/usr/bin/env python3
"""Opt-in Context7/official-search comparison, grading executed generated code."""
import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import tomllib
from measure_workflows import call, digest


def grade(code, root):
    try:
        tree=ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                modules=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or '']
                if any(m!='pydantic' for m in modules): raise ValueError('Only pydantic imports are needed')
            if isinstance(node,ast.Name) and node.id in ('open','eval','exec','__import__','compile','globals','locals'):
                raise ValueError('Forbidden unnecessary capability')
            if isinstance(node,ast.Attribute) and node.attr.startswith('__'): raise ValueError('Forbidden dunder access')
        (root/'implementation.py').write_text(code)
        (root/'grade.py').write_text('''import json
from implementation import Product
outputs=[]
for data in [{}, {"count":"4"}, {"count":0}, {"count":-1}]:
    try:
        item=Product.model_validate(data)
        outputs.append({"accepted":True,"value":item.count})
    except Exception:
        outputs.append({"accepted":False})
print(json.dumps(outputs))
''')
        help_text=subprocess.run(['codex','sandbox','--help'],text=True,capture_output=True,check=True).stdout
        suffix=['linux'] if 'Commands:' in help_text and 'linux' in help_text else []
        argv=['codex','-c','sandbox_mode="read-only"','-c','sandbox_workspace_write.network_access=false',
              'sandbox',*suffix,'--','python3','-B','grade.py']
        result=subprocess.run(argv,cwd=root,text=True,capture_output=True,timeout=30,
                              env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        (root/'grader-receipt.json').write_text(json.dumps({'command':argv,'exit_code':result.returncode,
            'stdout':result.stdout,'stderr':result.stderr,'implementation_sha256':digest(code)},ensure_ascii=False,indent=2)+'\n')
        if result.returncode: return [],'generated code failed execution: '+result.stderr[-300:]
        return json.loads(result.stdout),None
    except (SyntaxError,ValueError,subprocess.TimeoutExpired) as exc:
        return [],type(exc).__name__+': '+str(exc)[:150]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--deps',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    cfg=tomllib.loads((Path.home()/'.codex/config.toml').read_text());model=cfg['model'];effort=cfg.get('model_reasoning_effort','medium')
    expected=[{'accepted':False},{'accepted':True,'value':4},{'accepted':False},{'accepted':False}]
    question='Pydantic v2の公式文書を探して、Product(BaseModel)というクラスのPythonコードを返す。countはint、1以上、default=0。省略時もdefaultを検証してrejectする。count="4"は通常の型変換で4として受理する。モジュールはpydanticだけをimportし、クラス定義と必要なfield設定だけを書く。answerはコードそのものをJSON文字列にし、sourcesは参照した公式URL。id="implementation"。コードを実行するのは親の独立grader。'
    contract={'model':model,'effort':effort,'question':question,'expected':expected,
              'test_inputs':[{}, {'count':'4'}, {'count':0}, {'count':-1}],
              'controls':['same task/model/effort/sandbox','unknown official URL and library ID','balanced native/MCP then MCP/native order'],
              'primary':'actual generated Python code behavior in an offline read-only sandbox',
              'secondary':'end-to-end model/tool time and actual MCP use',
              'adoption_rule':'additional correct behaviors without regression; ties support no code-accuracy improvement claim',
              'limitations':['one library and four boundary cases, repeated twice','no production maintainability or human-time claim']}
    ch=digest(contract);(a.out/'contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
    rows=[]
    server={'command':'node','args':[str(a.deps.resolve()/'@upstash/context7-mcp/dist/index.js')]}
    with tempfile.TemporaryDirectory(prefix='ecc-code-model-') as temp:
        root=Path(temp)
        for trial in range(2):
            for treatment in ([False,True] if trial==0 else [True,False]):
                prompt=question+' MCPが利用可能ならlibrary解決と該当文書取得を実際に行う。ない場合は通常の公式web探索。外部mutation、subagent、インストールは禁止。'
                row=call(prompt,server if treatment else None,'context7',model,effort,root,360,raw_answer_ids=('implementation',))
                code=row['outputs'].get('implementation','');code=code if isinstance(code,str) else ''
                actual,error=grade(code,root)
                row.update(candidate='context7' if treatment else 'native',trial=trial+1,
                           actual_behavior=actual,grader_error=error,contract_sha256=ch,
                           correct=sum(digest(x)==digest(y) for x,y in zip(actual,expected)),total=len(expected))
                rows.append(row);(a.out/'results.json').write_text(json.dumps({'contract_sha256':ch,'rows':rows},ensure_ascii=False,indent=2)+'\n')
                print(json.dumps({k:row[k] for k in ('candidate','trial','correct','total','elapsed_seconds','error','grader_error')}),flush=True)


if __name__=='__main__':main()
