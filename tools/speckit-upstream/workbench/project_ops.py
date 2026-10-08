from __future__ import annotations
import json, re, shutil, tempfile
from pathlib import Path
from . import VERSION
from .common import *
from .layout import COMPACT, compact, destination

ROOT=Path(__file__).resolve().parents[1]
MODES=['new','existing','change','bug','refactor']
CORE_SKILLS=['speckit-constitution','speckit-specify','speckit-plan','speckit-tasks','speckit-analyze']


def specify_path()->str:
    p=executable('specify')
    if not p:raise WorkbenchError('specifyがありません。グローバルinstallerを --apply で実行してください')
    return p


def official_plan(root:Path,apply:bool,with_bug:bool)->tuple[dict[str,bytes],set[str]]:
    """New SpecKit only: render in isolation, import only allowed absent files."""
    if (root/'.specify/templates').is_dir():
        missing=[name for name in CORE_SKILLS if not (root/'.agents/skills'/name/'SKILL.md').is_file()]
        if missing:
            raise WorkbenchError('既存SpecKitは変更しません。Codex統合が不足: '+', '.join(missing)+
                                 '\n既存のspecify integration statusを確認し、必要なら公式integration install codexをレビューして実行してください。\n文書のみ追加する場合は --docs-only を指定できます。')
        print('[REUSE] 既存の .specify とCodex公式Skillを保持')
        if not (root/'.specify/presets/upstream-trace').exists():
            print('[NOTICE] append presetは既存環境に未導入。共通Skillは利用できます。Presetは配置済みassets/presetをレビューして公式 preset add --dev <path> で任意導入。')
        if with_bug and not (root/'.agents/skills/speckit-bug-assess/SKILL.md').is_file():
            print('[NOTICE] 既存環境にbug Skillなし。公式 specify extension add bug は別途レビューして実行してください。')
        return {},set()
    if (root/'.specify').exists():
        unknown=[p for p in (root/'.specify').iterdir() if p.name not in {'workbench.json','workbench'}]
        if unknown:
            raise WorkbenchError('未判定の既存 .specify を初期化しません。内容を確認するか --docs-only を使用してください')
    if not apply:
        print('[PLAN] specify initを空の一時ディレクトリで実行し、.specify/とspeckit-* Skillのみ追加予定')
        if with_bug:print('[PLAN] 同梱のbug extensionを一時ディレクトリで導入予定')
        print('[PLAN] upstream-trace append presetを一時ディレクトリで登録予定')
        return {},set()
    exe=specify_path()
    help_text=checked([exe,'init','--help'])
    for option in ['--integration','--non-interactive','--script','--ignore-agent-tools']:
        if option not in help_text:raise WorkbenchError(f'specify initが{option}に未対応。自動更新せず停止します')
    if with_bug and '--extension' not in help_text:raise WorkbenchError('このspecifyは --extension 未対応。対応版を確認してください')
    with tempfile.TemporaryDirectory(prefix='speckit-wb-') as d:
        staging=Path(d)
        argv=[exe,'init','--here','--integration','codex','--script','sh','--non-interactive','--ignore-agent-tools']
        if with_bug:argv+=['--extension','bug']
        print('[RUN] '+shlex.join(argv)+' (isolated staging)')
        result=checked(argv,staging,120)
        checked([exe,'preset','add','--dev',str(ROOT/'assets/preset')],staging,120)
        expected=CORE_SKILLS+(['speckit-bug-assess','speckit-bug-fix','speckit-bug-test'] if with_bug else [])
        for name in expected:
            if not (staging/'.agents/skills'/name/'SKILL.md').is_file():
                raise WorkbenchError(f'公式生成物を確認できません: {name}\n'+result[-3000:])
        if not (staging/'.specify/templates/spec-template.md').is_file():
            raise WorkbenchError('公式spec-templateが生成されませんでした')
        outputs={};modes=set()
        for p in sorted(staging.rglob('*')):
            if p.is_symlink():raise WorkbenchError('一時生成物にsymlinkがあります。安全のため停止')
            if not p.is_file():continue
            rel=p.relative_to(staging).as_posix();parts=Path(rel).parts
            allowed=parts[0]=='.specify' or (len(parts)>3 and parts[:2]==('.agents','skills') and parts[2].startswith('speckit-'))
            if not allowed:
                print('[IGNORE upstream file] '+rel);continue
            if p.stat().st_size>3_000_000:raise WorkbenchError('想定外の大きな生成物: '+rel)
            content=p.read_bytes()
            if str(staging).encode() in content:
                raise WorkbenchError('一時パスに依存する公式生成物を検出。自動転送を停止: '+rel)
            outputs[rel]=content
            if p.stat().st_mode&0o111:modes.add(rel)
        return outputs,modes


def attach(root:Path,system:str,mode:str,docs_dir:str,apply:bool,docs_only:bool=False,with_bug:bool=True,approval_profile:str='normal')->None:
    system_id(system)
    if mode not in MODES:raise WorkbenchError('未対応mode')
    if approval_profile not in {'small','normal','critical'}:raise WorkbenchError('approval-profileはsmall/normal/critical')
    inside(root,docs_dir)
    if not docs_dir.startswith('docs/') or '..' in Path(docs_dir).parts:
        raise WorkbenchError('docs-dirはdocs/配下にしてください')
    cfg_path=inside(root,'.specify/workbench.json')
    if cfg_path.exists():
        c=load_project(root)
        if c['system']!=system or c['docs_dir']!=docs_dir:
            raise WorkbenchError('既存のsystem/docs-dirと異なります。別システムとして自動変更しません')
        print('[SKIP] Workbench導入済み。既存資料・初期モード・approval profileは保持します')
        print('今後の作業モードは prompt --mode ... で切り替えられます')
        return
    official,execs=({},set()) if docs_only else official_plan(root,apply,with_bug)
    manifest=json.loads((ROOT/'assets/templates/manifest.json').read_text())
    files=dict(official)
    for target,template in manifest.items():
        rel=target.replace('@DOCS@',docs_dir)
        text=(ROOT/'assets/templates'/template).read_text(encoding='utf-8')
        text=text.replace('@SYSTEM@',system).replace('@MODE@',mode).replace('@DOCS@',docs_dir)
        files[rel]=text.encode()
    c={'schema_version':1,'workbench_version':VERSION,'system':system,'initial_mode':mode,'docs_dir':docs_dir,
       'extra_docs':[],'required_docs':[k.replace('@DOCS@',docs_dir) for k in manifest if k.startswith('@DOCS@/')], 'specify_mode':'docs-only' if docs_only else 'official',
       'approval_profile':approval_profile,'document_layout':COMPACT,
       'note':'文書の内容と承認は人・Codexが根拠に基づき作成する。アプリ変更の承認ではない。'}
    files['.specify/workbench.json']=json_text(c).encode()
    # No app source, AGENTS.md, host hooks, model/MCP config, or git operations.
    if apply:
        with project_lock(root):add_files(root,files,True,execs)
    else:add_files(root,files,False,execs)
    print('文書雛形の配置'+('完了' if apply else '予定')+'。仕様の策定・承認・実装はまだ行っていません。')


def prompt(root:Path,mode:str)->str:
    if mode not in MODES:raise WorkbenchError('未対応mode')
    c=load_project(root)
    common=(ROOT/'assets/prompts/common.md').read_text()
    specific=(ROOT/'assets/prompts'/f'{mode}.md').read_text()
    layout=c.get('document_layout','legacy')
    return f'$speckit-workbench\n\n対象: {root}\nシステムID: {c["system"]}\n文書: {c["docs_dir"]}\n形式: {layout}\n\n'+common+'\n'+specific


def add_item(root:Path,kind:str,key:str,title:str,parents:list[str],filename:str|None,apply:bool)->None:
    from .trace import TYPES,REQS,inspect
    c=load_project(root);identifier(key)
    if kind not in TYPES:raise WorkbenchError('未対応type')
    if not key.startswith(c['system']+'-'):raise WorkbenchError('system IDをIDの接頭辞にしてください')
    existing=inspect(root)
    if any(i.get('id')==key for i in existing['items']):raise WorkbenchError('既存ID。元文書を更新してください: '+key)
    for p in parents:
        identifier(p)
        if p not in {i['id'] for i in existing['items']}:raise WorkbenchError('上位IDが未定義: '+p)
    row={'id':key,'type':kind,'system':c['system'],'title':title,'status':'draft','basis':'proposed',
         'owner':'TBD','sources':[],'links':{'derives_from':parents} if parents else {}}
    if kind in REQS|{'story','goal'}:row['acceptance']='TBD: 条件・測定方法・期待結果を決める'
    if kind=='verification':row.update(method='test',expected='TBD',result='not_run',result_evidence=[])
    text=f'\n## {key} {title}\n\n```upstream\n'+json_text(row)+'```\n\n'
    text+='本文: TBD — 根拠を確認して記載。ユーザーの合意・テスト成功を推測しない。\n'
    rel=filename or c['docs_dir']+'/'+(destination(kind) if compact(c) else 'items/'+key+'.md')
    prior_rows=[r for r in existing['items'] if r['_file']==rel]
    legacy_context=bool(prior_rows) and all(r.get('_section') is None for r in prior_rows)
    if compact(c) and not legacy_context:
        text='\n<!-- upstream:section '+key+' -->\n'+text+'<!-- /upstream:section -->\n'
    if not rel.endswith('.md'):raise WorkbenchError('Markdownを指定してください')
    allowed=rel.startswith(c['docs_dir']+'/') or rel.startswith('specs/') or rel.startswith('.specify/bugs/') or rel in c.get('extra_docs',[])
    if not allowed:raise WorkbenchError('文書の探索対象内の.mdを指定してください')
    p=inside(root,rel);old=p.read_bytes() if p.exists() else b''
    print('[APPEND] '+rel)
    if apply:
        if old:
            backup=inside(root,c['docs_dir']+'/.backups/'+p.name+'.'+sha(old)[:16]+'.bak')
            if not backup.exists():atomic_write(backup,old)
        atomic_write(p,old+text.encode())


def register_doc(root:Path,filename:str,apply:bool)->None:
    c=load_project(root);p=inside(root,filename)
    if not p.is_file() or p.suffix!='.md':raise WorkbenchError('既存Markdown文書を指定してください')
    if filename in c['extra_docs']:print('[SKIP] 登録済み');return
    print('[REGISTER] '+filename+' (文書本文は変更しません)')
    if apply:
        c['extra_docs'].append(filename)
        atomic_write(inside(root,'.specify/workbench.json'),json_text(c).encode())
