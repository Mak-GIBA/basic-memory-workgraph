#!/usr/bin/env python3
"""Check authored examples; this is NOT a controlled LLM effectiveness evaluation."""
from pathlib import Path
import argparse, importlib.util, json, sys

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path)
    a=p.parse_args()
    root=Path(__file__).resolve().parent
    check=root.parent/'assets/scripts/check.py'
    if not check.exists(): check=root.parent/'scripts/check.py'
    spec=importlib.util.spec_from_file_location('example_check',check)
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    data=json.loads((root/'writing-examples.json').read_text(encoding='utf-8'))
    outcomes=[]
    for case in data['examples']:
        missing=[s for s in case['must_keep'] if s not in case['after']]
        findings=mod.local_lint(case['after'],case['genre'])
        outcomes.append({'id':case['id'],'missing_required_content':missing,
                         'before_boundary_candidates':len(mod.local_lint(case['before'],case['genre'])),
                         'after_boundary_candidates':len(findings),
                         'protected_changes_to_review':mod.compare_anchors(case['before'],case['after']),
                         'outline':mod.outline(case['after']),
                         'mechanical_constraints_pass':not missing and not findings})
    result={'scope':data['kind'],'independent_llm_ab':False,'semantic_quality_score':None,
            'mechanical_constraint_passes':sum(x['mechanical_constraints_pass'] for x in outcomes),
            'total':len(outcomes),'results':outcomes}
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text,encoding='utf-8')
    print(text)
    return 0 if all(x['mechanical_constraints_pass'] for x in outcomes) else 1
if __name__=='__main__':raise SystemExit(main())
