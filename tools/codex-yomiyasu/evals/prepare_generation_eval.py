#!/usr/bin/env python3
"""Prepare balanced writing prompts and blank review forms. No LLM invocation.
This tests fully supplied instructions, not native skill discovery or activation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import random

MAX_BYTES = 2_000_000


def read(path: Path) -> str:
    for p in [path, *path.parents]:
        if p.is_symlink():
            raise ValueError('symlink is not allowed: '+str(p))
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('Missing or oversized text: '+str(path))
    return path.read_text(encoding='utf-8')


def collect(root: Path, relatives: list[str]) -> tuple[str, dict]:
    sections, hashes = [], {}
    for rel in relatives:
        text = read(root/rel)
        hashes[rel] = hashlib.sha256(text.encode()).hexdigest()
        sections.append('### Instruction source: '+rel+'\n\n'+text)
    return '\n\n'.join(sections), hashes


def prepare(tasks: list[dict], upstream: Path, baseline: Path, proposal: Path,
            out: Path, repeats: int = 1, seed: int = 20261011) -> dict:
    if not 1 <= repeats <= 10:
        raise ValueError('repeats must be between 1 and 10')
    for p in [out, *out.parents]:
        if p.is_symlink():
            raise ValueError('Output symlinks are not allowed')
    if out.exists():
        raise ValueError('Use a new output directory')
    if not tasks or len(tasks) > 100:
        raise ValueError('Expected 1..100 tasks')
    # All arms receive exactly the same upstream text. No new instruction source
    # is fetched by this script and expected answers are never put in prompts.
    up_paths = ['SKILL.upstream.md'] + [p.relative_to(upstream).as_posix() for p in sorted((upstream/'references').rglob('*.md'))]
    common, up_hashes = collect(upstream, up_paths)
    old_paths = ['SKILL.md', 'paragraph-writing/SKILL.md', 'japanese-direct-writing/SKILL.md']
    old_paths += [p.relative_to(baseline).as_posix() for p in sorted(baseline.rglob('*.md'))
                  if p.relative_to(baseline).as_posix() not in old_paths
                  and 'references' in p.relative_to(baseline).parts and 'upstream' not in p.relative_to(baseline).parts
                  and p.name not in {'sources.md','AGENTS_APPEND.md'}]
    new_paths = ['SKILL.md', 'references/paragraphs.md', 'references/audience.md',
                 'references/directness.md', 'references/review.md']
    old, old_hashes = collect(baseline, old_paths)
    new, new_hashes = collect(proposal, new_paths)
    arms = {'upstream_only': common, 'existing_three_skills': old+'\n\n'+common,
            'proposal': new+'\n\n'+common}
    jobs = []
    for task in tasks:
        if not isinstance(task.get('id'), str) or not task['id'].isalnum():
            raise ValueError('Task id must be alphanumeric')
        for rep in range(1, repeats+1):
            for arm, rules in arms.items():
                prompt = ('次の規則を用いて末尾の執筆課題に回答してください。規則の参照資料は同じプロンプト内に展開済みです。'
                          'この比較は文章生成だけが対象です。ツール呼び出し、ファイル操作、外部検索は行わず、完成稿だけを出力してください。\n\n'
                          +rules+'\n\n## 今回の執筆課題\n\n'+task['instruction']+'\n\n'+task['input']+'\n')
                jobs.append({'task_id': task['id'], 'repeat': rep, 'arm': arm, 'prompt': prompt})
    random.Random(seed).shuffle(jobs)
    out.mkdir(parents=True)
    ratings = []
    for i, job in enumerate(jobs, 1):
        code = 'J'+str(i).zfill(4)
        name = 'prompts/'+code+'.md'
        p=out/name;p.parent.mkdir(exist_ok=True)
        text = job.pop('prompt');p.write_text(text,encoding='utf-8')
        job.update(job_id=code,prompt_file=name,prompt_sha256=hashlib.sha256(text.encode()).hexdigest(),
                   input_characters=len(text),output_file='outputs/'+code+'.md',status='NOT_RUN')
        ratings.append({'job_id':code,'meaning_error':None,'author_metadata_left':None,
                        'paragraph_unity_0_4':None,'evidence_connection_0_4':None,'coherence_0_4':None,
                        'japanese_naturalness_0_4':None,'reader_fit_0_4':None,'reviewer':None,'notes':None})
    (out/'outputs').mkdir()
    result={'status':'PREPARED_NOT_RUN','experiment':'fully supplied instruction comparison; not native skill activation',
            'seed':seed,'repeats':repeats,'tasks':len(tasks),'jobs':jobs,
            'source_sha256':{'upstream':up_hashes,'baseline':old_hashes,'proposal':new_hashes},
            'model':None,'reasoning_effort':None,'codex_version':None,'environment_isolation_verified':False}
    (out/'manifest.private.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'ratings.blank.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in ratings),encoding='utf-8')
    return result


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--upstream-dir',type=Path,required=True,help='Installed yomiyasu/upstream directory')
    p.add_argument('--baseline-assets',type=Path,required=True,help='Original v1.3.0 tools/codex-yomiyasu/assets')
    base=Path(__file__).resolve().parent.parent
    default_assets=base/'assets' if (base/'assets').is_dir() else base
    p.add_argument('--proposal-assets',type=Path,default=default_assets)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--repeats',type=int,default=1)
    p.add_argument('--seed',type=int,default=20261011)
    args=p.parse_args()
    try:
        tasks=json.loads(read(Path(__file__).resolve().parent/'generation-tasks.json'))['tasks']
        r=prepare(tasks,args.upstream_dir,args.baseline_assets,args.proposal_assets,args.out,args.repeats,args.seed)
        print(json.dumps({'status':r['status'],'jobs':len(r['jobs']),'directory':str(args.out)},ensure_ascii=False))
        return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'ERROR','error':str(exc)},ensure_ascii=False))
        return 2

if __name__=='__main__':raise SystemExit(main())
