#!/usr/bin/env python3
"""Candidate-detection benchmark only; not an LLM writing-quality experiment."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, sys, tempfile

def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec);sys.modules[name]=obj;spec.loader.exec_module(obj)
    return obj

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--split',choices=['development','holdout','all'],default='all')
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    root=Path(__file__).resolve().parent
    check=root.parent/'assets/scripts/check.py'
    if not check.exists():check=root.parent/'scripts/check.py'
    old=module('boundary_old',root/'baselines/check_meta_v1.py');new=module('boundary_new',check)
    raw=(root/'boundary-cases.jsonl').read_bytes()
    cases=[json.loads(x) for x in raw.decode().splitlines() if x]
    cases=[c for c in cases if args.split=='all' or c['split']==args.split]
    result={'task':'binary audience-boundary candidate detection','dataset_sha256':hashlib.sha256(raw).hexdigest(),
            'scope':'synthetic fixtures; code execution, not Codex generations or independently labeled human data',
            'split':args.split,'cases':len(cases),'detectors':{}}
    for name in ('previous_audience_boundary','proposal'):
        counts=dict(tp=0,fp=0,tn=0,fn=0); details=[]
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/'input.md'
            for c in cases:
                file.write_text(c['text'],encoding='utf-8')
                hits=old.inspect(file) if name=='previous_audience_boundary' else new.local_lint(c['text'],c['genre'])
                pred=bool(hits);key=('tp' if pred else 'fn') if c['expected'] else ('fp' if pred else 'tn')
                counts[key]+=1
                details.append({'id':c['id'],'expected':c['expected'],'predicted':pred,'correct':pred==c['expected'],
                                'rules':[(getattr(h,'issue',None) or h['rule']) for h in hits]})
        precision=counts['tp']/(counts['tp']+counts['fp']) if counts['tp']+counts['fp'] else None
        recall=counts['tp']/(counts['tp']+counts['fn']) if counts['tp']+counts['fn'] else None
        f1=2*precision*recall/(precision+recall) if precision and recall else 0.0
        result['detectors'][name]={**counts,'precision':precision,'recall':recall,'f1':f1,'details':details}
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text,encoding='utf-8')
    print(text)
if __name__=='__main__':main()
