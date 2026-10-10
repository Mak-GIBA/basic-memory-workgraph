#!/usr/bin/env python3
"""Explicit final-answer comparison: known official documents versus Context7.

Two fixed API questions, normal Codex authentication, no model tool calls. This
does not measure documentation discovery when the official URLs are unknown.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import tomllib
import urllib.request


def main():
    root = Path(__file__).parent/'evidence'
    questions = [
        {'id': 'requests-timeout', 'input': 'Requestsのtimeout=(3.05,27)はconnect/readの設定か。また、このread timeoutは全レスポンスのダウンロードを27秒以内に完了させる期限か。{"connect_read_pair":boolean,"total_download_deadline":boolean}で答える。', 'expected': {'connect_read_pair': True, 'total_download_deadline': False}},
        {'id': 'pydantic-before', 'input': 'Pydantic v2の@field_validator(...,mode="before")は型変換前の生入力を受け取るか。また返した値には通常の型検証が引き続き適用されるか。{"raw_input":boolean,"type_validation_after":boolean}で答える。', 'expected': {'raw_input': True, 'type_validation_after': True}},
    ]
    urls = ['https://raw.githubusercontent.com/psf/requests/main/docs/user/advanced.rst',
            'https://raw.githubusercontent.com/pydantic/pydantic/main/docs/concepts/validators.md']
    native_docs, native_seconds = [], 0
    for url, marker in zip(urls, ['Timeouts', '* ***Before* validators**']):
        start = time.monotonic()
        request = urllib.request.Request(url, headers={'User-Agent': 'ecc-effectiveness-check/1.0'})
        with urllib.request.urlopen(request, timeout=30) as response: text = response.read(1024*1024).decode()
        pos = text.find(marker)
        if pos < 0: pos = text.lower().find('before validators') if 'validators' in url else -1
        assert pos >= 0, (url, marker)
        excerpt = text[pos:pos+9000]
        native_seconds += time.monotonic()-start
        native_docs.append('Source: '+url+'\n'+excerpt)
    public = json.loads((root/'tools-results.json').read_text())['public_retrieval']
    context_rows = [r for r in public if r['candidate']=='context7']
    assert len(context_rows)==2 and not any(r['tool_error'] for r in context_rows)
    context_docs = [r['response'] for r in context_rows]
    config = tomllib.loads((Path.home()/'.codex/config.toml').read_text())
    model, effort = config['model'], config.get('model_reasoning_effort', 'medium')
    contract = {'tasks': questions, 'model': model, 'effort': effort, 'primary': 'Exact final JSON answers',
                'controls': 'Same questions, expected answers, model and effort. Only supplied documentation differs.',
                'scope': 'Known official URLs, one batch per condition. No claim about unknown-URL discovery or population accuracy.',
                'sources': urls, 'native_document_retrieval_seconds': native_seconds,
                'context7_retrieval_seconds': sum(r['elapsed_seconds'] for r in context_rows)}
    (root/'documentation-contract.json').write_text(json.dumps(contract, ensure_ascii=False, indent=2)+'\n')
    rows = []
    schema = {'type': 'object', 'properties': {'answers': {'type': 'array', 'items': {'type': 'object',
              'properties': {'id': {'type': 'string'}, 'answer': {'type': 'string'}},
              'required': ['id', 'answer'], 'additionalProperties': False}}}, 'required': ['answers'], 'additionalProperties': False}
    with tempfile.TemporaryDirectory(prefix='ecc-doc-answers-') as temporary:
        scratch = Path(temporary); (scratch/'schema.json').write_text(json.dumps(schema))
        for name, documents in [('official-docs', native_docs), ('context7', context_docs)]:
            prompt = '提供資料だけを参考に次の2問の最終答えを返してください。answerは答えのJSONを文字列にしてください。ツール、shell、web、subagentは使わないでください。\n'
            prompt += json.dumps({'questions': [{k:q[k] for k in ['id','input']} for q in questions], 'documents': documents}, ensure_ascii=False)
            output = scratch/'final.json'; output.unlink(missing_ok=True)
            start=time.monotonic()
            completed=subprocess.run(['codex','exec','--ignore-user-config','--ignore-rules','--ephemeral','--skip-git-repo-check',
                '--sandbox','read-only','--model',model,'-c','model_reasoning_effort='+json.dumps(effort),'--json',
                '--output-schema',str(scratch/'schema.json'),'--output-last-message',str(output),'-'],
                input=prompt,text=True,capture_output=True,cwd=scratch,timeout=360)
            events=[]
            for line in completed.stdout.splitlines():
                try:events.append(json.loads(line))
                except ValueError:pass
            calls=[e.get('item',{}).get('type') for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type') not in ['agent_message','reasoning']]
            assert completed.returncode==0 and not calls
            answers={r['id']:json.loads(r['answer']) for r in json.loads(output.read_text())['answers']}
            row={'candidate':name,'outputs':answers,'model_seconds':round(time.monotonic()-start,3),
                 'usage':next(e['usage'] for e in reversed(events) if e.get('type')=='turn.completed'),
                 'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'tool_calls':calls,'checked_at':datetime.now(timezone.utc).isoformat()}
            row['correct']=sum(answers.get(q['id'])==q['expected'] for q in questions);row['total']=len(questions)
            rows.append(row)
            (root/'documentation-results.json').write_text(json.dumps({'rows':rows,'documents':dict(zip(['official-docs','context7'],[native_docs,context_docs]))},ensure_ascii=False,indent=2)+'\n')
            print(json.dumps({k:row[k] for k in ['candidate','correct','total','model_seconds']}),flush=True)


if __name__=='__main__':main()
