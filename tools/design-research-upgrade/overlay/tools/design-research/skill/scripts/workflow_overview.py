#!/usr/bin/env python3
"""Read-only, file-backed status of requirements -> research -> design handoff.

This does not run a research harness or claim scientific validity. It helps a
single Codex-facing Skill determine which stage is already recorded and which
workstreams are eligible under a frozen requirements plan.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

from codex_interface import project_path, safe, runs, public, read
from research_workstreams import load_plan, digest, execution_waves

DEFAULT_PLAN = '.specify/workbench/research-plan.json'


def overview(root: Path, plan_name: str=DEFAULT_PLAN) -> dict:
    root=project_path(root)
    plan_path=safe(root,plan_name)
    rows,warnings=runs(root)
    result={'inspection_only':True,'project':str(root),'plan':plan_name,
            'workflow_stage':'unplanned','workstreams':[],
            'ready_to_research':[],'next_action':'Check requirements and scope',
            'warnings':list(warnings),'past_runs':[public(row) for row in rows]}
    if not plan_path.exists():
        # The requirements may live under a non-default docs_dir. Do not guess
        # a canonical document when no frozen plan identifies it.
        result['workflow_stage']='needs_plan' if (root/'docs/upstream/requirements.md').is_file() else 'standalone'
        result['next_action']=('Decompose requirements into core logic before full-system research'
                               if result['workflow_stage']=='needs_plan'
                               else 'Standalone research or inspect existing run; choose upstream for whole-system requirements')
        return result
    try:
        plan=load_plan(root,plan_name)
    except (ValueError,OSError,TypeError,KeyError) as exc:
        result['workflow_stage']='plan_invalid'
        result['next_action']='Review and re-freeze the existing plan; do not dispatch research'
        result['warnings'].append(str(exc))
        return result
    source_hash=digest(read(root,plan_name))
    result['execution_waves']=execution_waves(plan)
    result['requirements_file']=plan['requirements']['path']
    result['requirements_sha256']=plan['requirements']['sha256']
    matches={}
    for task in plan['workstreams']:
        key=task['id']
        matches[key]=[r for r in rows if r['reassess_eligible']
                 and r['_state'].get('workstream_context',{}).get('workstream_id') == key
                 and r['_state'].get('workstream_context',{}).get('plan_sha256') == source_hash]
    completed={key for key,found in matches.items() if len(found)==1}
    ambiguous={key for key,found in matches.items() if len(found)>1}
    waiting={key for key,found in matches.items() if not found}
    for task in plan['workstreams']:
        key=task['id'];deps=set(task['depends_on'])
        state='complete' if key in completed else ('ambiguous' if key in ambiguous else ('ready' if deps<=completed else 'blocked_by_dependency'))
        result['workstreams'].append({'id':key,'title':task['title'],
                                     'status':state,'depends_on':task['depends_on'],
                                     'matches':[public(v) for v in matches[key]]})
        if state=='ready':result['ready_to_research'].append(key)
    if ambiguous:
        result['workflow_stage']='needs_run_selection'
        result['next_action']='Identify the exact completed run per ambiguous workstream; do not guess by recency'
    elif not waiting:
        result['workflow_stage']='integration_pending'
        result['next_action']='Read individual reports; verify whole-system constraints and integrate the design.md'
    elif any(t['status']=='ready' for t in result['workstreams']):
        result['workflow_stage']='research_in_progress'
        result['next_action']='Research ready workstreams in permitted session(s), respecting existing project lock'
    else:
        result['workflow_stage']='research_blocked'
        result['next_action']='Resolve dependency completion or plan/run mismatch'
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',default='.')
    p.add_argument('--plan',default=DEFAULT_PLAN)
    a=p.parse_args(argv)
    try:
        result=overview(Path(a.project),a.plan)
    except (OSError,TypeError,ValueError,KeyError) as exc:
        result={'inspection_only':True,'workflow_stage':'blocked','warnings':[str(exc)],'workstreams':[]}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 2 if result['workflow_stage'] in {'blocked','plan_invalid','needs_run_selection'} else 0

if __name__=='__main__':raise SystemExit(main())
