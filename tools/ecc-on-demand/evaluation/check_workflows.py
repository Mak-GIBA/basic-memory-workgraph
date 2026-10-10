#!/usr/bin/env python3
"""Offline integrity and final-output grading; never resample a model/MCP."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
from check_captures import same_json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


STUDIES = ('reasoning-explicit-format', 'documentation', 'implementation-executed',
           'parallel', 'cloudflare', 'playwright-independent-state',
           'chrome-independent-state', 'information')


def check(root):
    for entry in json.loads((root/'manifest.json').read_text()):
        path=root/entry['path']
        assert not path.is_symlink() and path.is_file(), entry['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256'], entry['path']
    summary={}
    for study in STUDIES:
        folder=root/study
        contract=json.loads((folder/'contract.json').read_text())
        result=json.loads((folder/'results.json').read_text());ch=digest(contract)
        assert result['contract_sha256']==ch, study
        rows=result['rows'];assert len(rows)==(16 if study=='information' else 4), study
        seen=set();counts={}
        for row in rows:
            assert row['contract_sha256']==ch and row['exit_code']==0 and row['error'] is None, study
            assert row['elapsed_seconds']>0
            identity=(row['candidate'], row['trial'], row.get('case'))
            assert identity not in seen;seen.add(identity)
            calls=[c for c in row['tool_calls'] if c.get('type')=='mcp_tool_call']
            if study=='information':
                assert not row['tool_calls'] and not row['tool_error']
                assert row['case'] in contract['cases']
                assert row['response_bytes']==len(row['current_response'].encode())
                if row['candidate']=='native':assert row['current_response']==contract['document']
                if row['case']!='prior-context-retained':assert row['prior_context_bytes']==0
                correct=int(same_json(row['outputs'].get('fields'),contract['expected']));total=1
            else:
                target={'reasoning-explicit-format':'sequential-thinking','documentation':'context7',
                    'implementation-executed':'context7','parallel':'parallel','cloudflare':'cloudflare',
                    'playwright-independent-state':'playwright','chrome-independent-state':'chrome'}[study]
                if row['candidate']=='native':assert not any(c.get('server')==target for c in calls)
                else:
                    assert any(c.get('server')==target and c.get('status')=='completed' and not c.get('error') for c in calls)
                    if study=='documentation' or study=='implementation-executed':
                        assert {'resolve-library-id','query-docs'} <= {c['tool'] for c in calls}
                if study=='implementation-executed':
                    code=(folder/row['grader_receipt']).parent/'implementation.py'
                    receipt=json.loads((folder/row['grader_receipt']).read_text())
                    assert code.read_text()==row['outputs']['implementation']
                    assert digest(code.read_text())==receipt['implementation_sha256']
                    assert receipt['exit_code']==0 and row['grader_error'] is None
                    assert json.loads(receipt['stdout'])==row['actual_behavior']
                    correct=sum(same_json(a,b) for a,b in zip(row['actual_behavior'],contract['expected']))
                    total=len(contract['expected']);assert len(row['actual_behavior'])==total
                else:
                    assert set(row['outputs'])=={t['id'] for t in contract['tasks']}
                    grades={t['id']:int(same_json(row['outputs'][t['id']],t['expected'])) for t in contract['tasks']}
                    if 'independent-state' in study:
                        assert row['browser_tool_records']
                        for t in contract['tasks']:
                            key='orders' if t['id']=='checkout' else 'diagnoses'
                            grades[t['id']] &= int(t['expected'] in row['server_observations'][key])
                    assert grades==row['grades'];correct=sum(grades.values());total=len(grades)
            assert (correct,total)==(row['correct'],row['total']), study
            counter=counts.setdefault(row['candidate'],{'correct':0,'total':0,'seconds':[]})
            counter['correct']+=correct;counter['total']+=total;counter['seconds'].append(row['elapsed_seconds'])
        if study!='information':assert len({r['prompt_sha256'] for r in rows})==1
        assert len(counts)==2 and 'native' in counts
        summary[study]={name:{'correct':c['correct'],'total':c['total'],
            'mean_seconds':round(mean(c['seconds']),4)} for name,c in counts.items()}
        if study=='information':
            summary[study]['cases']={case:{name:{'correct':sum(r['correct'] for r in rows if r['case']==case and r['candidate']==name),
                'total':2,'response_bytes':[r['response_bytes'] for r in rows if r['case']==case and r['candidate']==name]}
                for name in counts} for case in contract['cases']}
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent/'workflows')
    a=p.parse_args();print(json.dumps(check(a.root),ensure_ascii=False,indent=2))
