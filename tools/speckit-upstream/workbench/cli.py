from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
from . import VERSION
from .common import *
from .project_ops import attach,prompt,add_item,register_doc,MODES,CORE_SKILLS
from .trace import inspect,save_report,TYPES
from .workflow import flow,run_gate,verify_gate
from .command_skills import COMMANDS
from .approval import approval_plan, create_review, latest_review, approve, revoke, set_profile


def doctor(root:Path|None)->int:
    problems=0
    print('SpecKit Workbench '+VERSION+' / Python '+sys.version.split()[0])
    for name in ['specify','codex']:
        p=executable(name)
        if not p:print('[MISSING] '+name);problems+=1
        else:
            print('[FOUND] '+name+' '+p)
            if name=='specify':
                try:print(checked([p,'version']).strip())
                except WorkbenchError as exc:print('[ERROR] '+str(exc));problems+=1
    l=locations();print('Global skill: '+str(l['skill']/'SKILL.md'))
    if not (l['skill']/'SKILL.md').is_file():print('[MISSING] global Skill');problems+=1
    for name in COMMANDS:
        path=l['skill'].parent/name/'SKILL.md'
        if not path.is_file():print('[MISSING] $'+name);problems+=1
        else:print('[OK] $'+name)
    if root:
        try:
            c=load_project(root);print('Project: '+str(root));print('System: '+c['system']);print('Docs: '+c['docs_dir'])
            for s in CORE_SKILLS:
                print(('[OK] ' if (root/'.agents/skills'/s/'SKILL.md').is_file() else '[NOTICE] 未配置 ')+s)
            print('Bug: '+('installed' if (root/'.agents/skills/speckit-bug-assess/SKILL.md').is_file() else '未配置（既存環境では公式extension add bugを別途確認）'))
        except WorkbenchError as exc:print('[NOTICE] '+str(exc))
    print('これは配置・CLI起動の診断です。Codex内でのSkill利用・仕様品質・アプリ動作の合格判定ではありません。')
    return 1 if problems else 0


def main(argv=None)->int:
    p=argparse.ArgumentParser(description='SpecKitに目的→要求→設計→検証の文書運用を追加。設定変更は --apply のときだけ。')
    p.add_argument('--version',action='version',version=VERSION)
    sub=p.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('migrate',help='旧上流文書を3文書へ統合（既定は内容付きプレビュー）')
    q.add_argument('--project',default='.')
    q.add_argument('--include-doc',action='append',default=[],help='明示的に移行する追加の上流Markdown')
    q.add_argument('--apply',action='store_true')
    for name in ['doctor','paths']:
        q=sub.add_parser(name);q.add_argument('--project')
    sub.add_parser('commands',help='Codexで使える定型Skillを一覧表示')
    q=sub.add_parser('flow',help='選んだ作業モードの固定手順を表示。モデルは起動しない')
    q.add_argument('--project',default='.');q.add_argument('--mode',choices=MODES+['check'],required=True)
    q=sub.add_parser('gate',help='上流文書のready構造検査。アプリの動作確認ではない')
    q.add_argument('--project',default='.')
    g=q.add_mutually_exclusive_group();g.add_argument('--write',action='store_true');g.add_argument('--verify',action='store_true')
    q.add_argument('--json',action='store_true')
    q=sub.add_parser('attach',help='各プロジェクトを初回準備（既定はdry-run）')
    q.add_argument('--project',required=True);q.add_argument('--system',required=True);q.add_argument('--mode',choices=MODES,default='existing')
    q.add_argument('--docs-dir',default='docs/upstream');q.add_argument('--approval-profile',choices=['small','normal','critical'],default='normal');q.add_argument('--apply',action='store_true')
    q.add_argument('--docs-only',action='store_true');q.add_argument('--without-bug',action='store_true')
    q=sub.add_parser('prompt');q.add_argument('--project',default='.');q.add_argument('--mode',choices=MODES,default='existing')
    q=sub.add_parser('approval-profile',help='承認チェックポイントの粒度を変更（既定dry-run）')
    q.add_argument('--project',default='.');q.add_argument('--set',choices=['small','normal','critical']);q.add_argument('--apply',action='store_true')
    q=sub.add_parser('approval-plan',help='このプロジェクトの承認チェックポイントと未承認項目を表示')
    q.add_argument('--project',default='.');q.add_argument('--json',action='store_true')
    q=sub.add_parser('review',help='hash-bound review packetを作成。承認はしない')
    q.add_argument('--project',default='.');q.add_argument('--checkpoint',default='next')
    q.add_argument('--latest',action='store_true');q.add_argument('--write',action='store_true');q.add_argument('--json',action='store_true')
    q=sub.add_parser('approve',help='保存済みreviewの特定IDだけを明示承認として記録')
    q.add_argument('--project',default='.');q.add_argument('--review',required=True);q.add_argument('--id',action='append',default=[])
    q.add_argument('--all-reviewed',action='store_true');q.add_argument('--by',required=True);q.add_argument('--reference',required=True);q.add_argument('--apply',action='store_true')
    q=sub.add_parser('revoke-approval',help='誤承認・撤回を記録し対象をproposedへ戻す')
    q.add_argument('--project',default='.');q.add_argument('--id',action='append',required=True);q.add_argument('--by',required=True);q.add_argument('--reference',required=True);q.add_argument('--apply',action='store_true')
    for name in ['check','trace']:
        q=sub.add_parser(name);q.add_argument('--project',default='.');q.add_argument('--phase',choices=['draft','ready'],default='draft')
        q.add_argument('--json',action='store_true')
        if name=='trace':q.add_argument('--write',action='store_true',help='生成専用のindex/matrixを更新する')
    q=sub.add_parser('item');q.add_argument('--project',default='.');q.add_argument('--type',choices=sorted(TYPES),required=True)
    q.add_argument('--id',required=True);q.add_argument('--title',required=True);q.add_argument('--parent',action='append',default=[])
    q.add_argument('--file');q.add_argument('--apply',action='store_true')
    q=sub.add_parser('register-doc');q.add_argument('--project',default='.');q.add_argument('--file',required=True);q.add_argument('--apply',action='store_true')
    q=sub.add_parser('uninstall');q.add_argument('--apply',action='store_true')
    a=p.parse_args(argv)
    try:
        root=project(a.project) if getattr(a,'project',None) else None
        if a.cmd=='migrate':
            from .migration import migrate
            import signal
            def interrupted(signum,frame):
                raise WorkbenchError('移行を中断しました。適用途中の変更は復元します')
            previous=signal.signal(signal.SIGTERM,interrupted)
            try:
                print(json_text(migrate(root,a.apply,a.include_doc)));return 0
            finally:
                signal.signal(signal.SIGTERM,previous)
        if a.cmd=='commands':
            for name,(_,desc) in COMMANDS.items():print('$'+name+' : '+desc)
            return 0
        if a.cmd=='flow':print(flow(root,a.mode));return 0
        if a.cmd=='gate':
            result=verify_gate(root) if a.verify else run_gate(root,a.write)
            if a.json:print(json_text(result))
            else:
                print(result['verdict']+f" | errors={result['errors']}, warnings={result['warnings']}")
                print('snapshot: '+result['fingerprint'])
                for f in result['findings']:print(f"[{f['severity']}] {f['code']} {f['item']}: {f['message']}")
                print(result['scope'])
            return 0 if result['passed'] else 1
        if a.cmd=='doctor':return doctor(root)
        if a.cmd=='paths':
            out={k:str(v) for k,v in locations().items()}
            if root:out['project']={'root':str(root),**load_project(root)}
            print(json_text(out))
        elif a.cmd=='attach':attach(root,a.system,a.mode,a.docs_dir,a.apply,a.docs_only,not a.without_bug,a.approval_profile)
        elif a.cmd=='prompt':print(prompt(root,a.mode))
        elif a.cmd=='approval-profile':
            if a.set:data=set_profile(root,a.set,a.apply);print(json_text(data))
            else:print(load_project(root).get('approval_profile','normal'))
        elif a.cmd=='approval-plan':
            data=approval_plan(root)
            if a.json:print(json_text(data))
            else:
                print('approval profile: '+data['profile'])
                for row in data['checkpoints']:
                    print(f"- {row['checkpoint']}: {'complete' if row['complete'] else 'review required'} | pending={', '.join(row['pending']) if row['pending'] else '-'}")
        elif a.cmd=='review':
            data=latest_review(root) if a.latest else create_review(root,a.checkpoint,a.write)
            if a.json:print(json_text(data))
            else:
                print('review_id: '+data['review_id']);print('checkpoint: '+data['checkpoint']);print('profile: '+data['profile'])
                for row in data['items']:print(f"- {row['id']} [{row['approval_state']}] {row['title']} hash={row['item_hash'][:12]}")
                if data.get('saved_markdown'):print('review packet: '+data['saved_markdown'])
                print('この出力はレビュー対象の固定化であり、承認ではありません。')
        elif a.cmd=='approve':
            data=approve(root,a.review,a.id,a.by,a.reference,a.apply,a.all_reviewed);print(json_text(data))
        elif a.cmd=='revoke-approval':
            data=revoke(root,a.id,a.by,a.reference,a.apply);print(json_text(data))
        elif a.cmd in {'check','trace'}:
            result=inspect(root,a.phase)
            if getattr(a,'write',False):save_report(root,result)
            if a.json:print(json_text(result))
            else:
                print(result['verdict']+f" | items={len(result['items'])}, errors={result['errors']}, warnings={result['warnings']}")
                for f in result['findings']:print(f"[{f['severity']}] {f['code']} {f['item']}: {f['message']}")
                print(result['scope'])
            return 1 if result['errors'] else 0
        elif a.cmd=='item':add_item(root,a.type,a.id,a.title,a.parent,a.file,a.apply)
        elif a.cmd=='register-doc':register_doc(root,a.file,a.apply)
        elif a.cmd=='uninstall':
            from .installer import uninstall
            uninstall(a.apply)
    except (WorkbenchError,OSError,ValueError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 2
    return 0
