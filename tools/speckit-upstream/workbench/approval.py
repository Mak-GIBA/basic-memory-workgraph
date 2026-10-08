"""Human review packets and hash-bound approval records for upstream documents."""
from __future__ import annotations
import datetime, json, re
from pathlib import Path
from .common import WorkbenchError, atomic_write, inside, json_text, load_project, project_lock, sha
from .trace import inspect
from .layout import internal
from .approval_core import (
    LEDGER_PATH, NON_APPROVAL_TYPES, HASH_VERSION, READINESS_CATEGORIES,
    approval_states, dependency_hashes, hash_version, item_hash, load_events, semantic_payload
)


APPROVAL_FINDING_CODES={
    'LEGACY_APPROVAL_UNBOUND','STALE_APPROVAL','STALE_DEPENDENCY_APPROVAL',
    'APPROVAL_METADATA_MISMATCH','APPROVAL_STATUS_MISMATCH','APPROVAL_REVOKED',
    'APPROVAL_MISSING','APPROVAL_INVALID'
}


def _assert_reviewable(result:dict)->None:
    blocking=[f for f in result.get('findings',[]) if f.get('severity')=='error' and f.get('code') not in APPROVAL_FINDING_CODES]
    if blocking:
        sample='; '.join(f"{f.get('code')}:{f.get('item')}" for f in blocking[:5])
        raise WorkbenchError('構造エラーがあるためレビュー/承認を固定できません。先に修正してください: '+sample)

REVIEW_ID_RE=re.compile(r'^rev-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{10}$')
PROFILE_CHECKPOINTS={
    'small': [
        ('scope', {'goal','stakeholder','need','capability','story','business_rule','requirement','quality','interface','data','operation','constraint'}),
        ('solution', {'design','decision','change','verification'}),
    ],
    'normal': [
        ('intent', {'goal','stakeholder','need','capability','story','business_rule'}),
        ('requirements', {'requirement','quality','interface','data','operation','constraint'}),
        ('solution', {'design','decision','change','verification'}),
    ],
    'critical': [
        ('purpose', {'goal','stakeholder','need','capability'}),
        ('stories', {'story','business_rule'}),
        ('requirements', {'requirement','quality','interface','data','operation','constraint'}),
        ('design', {'design','decision','change'}),
        ('verification', {'verification'}),
    ],
}
ALL_CHECKPOINTS={name:types for rows in PROFILE_CHECKPOINTS.values() for name,types in rows}
ALL_CHECKPOINTS['all']=set().union(*(types for _,types in PROFILE_CHECKPOINTS['critical']))


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def profile(root:Path)->str:
    value=load_project(root).get('approval_profile','normal')
    if value not in PROFILE_CHECKPOINTS:
        raise WorkbenchError('approval_profileが不正です')
    return value


def approval_plan(root:Path)->dict:
    result=inspect(root,'draft');byid={r['id']:r for r in result['items']};states=approval_states(root,byid)
    rows=[]
    for name,types in PROFILE_CHECKPOINTS[profile(root)]:
        ids=[r['id'] for r in result['items'] if r.get('status')!='retired' and r.get('type') in types]
        pending=[i for i in ids if states.get(i,{}).get('state')!='valid']
        categories=[k for k,t in READINESS_CATEGORIES.items() if t & types]
        missing=[k for k in categories if not result['coverage'][k]['satisfied']]
        exempted={k:result['coverage'][k]['exemptions'] for k in categories if result['coverage'][k]['exemptions']}
        rows.append({'checkpoint':name,'ids':ids,'pending':pending,'missing_categories':missing,
                     'exempted_categories':exempted,
                     'complete':not missing and not pending and bool(ids or exempted)})
    return {'profile':profile(root),'checkpoints':rows,'system':result['system']}


def _resolve_checkpoint(root:Path,name:str)->tuple[str,set[str]]:
    p=profile(root)
    if name=='next':
        plan=approval_plan(root)
        for row in plan['checkpoints']:
            if row['pending']:
                return row['checkpoint'],ALL_CHECKPOINTS[row['checkpoint']]
            if not row['complete']:
                raise WorkbenchError('未作成の上流項目があります: '+row['checkpoint']+' / '+', '.join(row['missing_categories'])+'。追加またはneed/storyの適用除外を明示承認してから再実行してください')
        raise WorkbenchError('このapproval profileで再レビューが必要な項目はありません')
    if name not in ALL_CHECKPOINTS:
        raise WorkbenchError('checkpointが不正です: '+name)
    # Named checkpoints are allowed even if not part of the selected profile for explicit review.
    return name,ALL_CHECKPOINTS[name]


def _review_dir(root:Path)->Path:
    c=load_project(root)
    return inside(root,internal(c,'governance/reviews','reviews'))


def _packet_markdown(packet:dict)->str:
    out=[f"# Upstream Review — {packet['review_id']}",'',
         f"- System: `{packet['system']}`",f"- Approval profile: `{packet['profile']}`",
         f"- Checkpoint: `{packet['checkpoint']}`",f"- Created: `{packet['created_at']}`",'',
         '> この資料はレビュー対象のスナップショットです。ここに含まれること自体は承認を意味しません。','']
    for item in packet['items']:
        out += [f"## {item['id']} — {item['title']}",'',
                f"- type: `{item['type']}` / status: `{item['status']}` / basis: `{item['basis']}`",
                f"- approval state: `{item['approval_state']}`",f"- source: `{item['file']}:{item['line']}`",
                f"- content hash: `{item['item_hash']}`"]
        if item.get('acceptance'):out.append('- acceptance: '+str(item['acceptance']))
        if item.get('expected'):out.append('- expected: '+str(item['expected']))
        if item.get('sources'):out.append('- evidence: '+'; '.join(map(str,item['sources'])))
        if item.get('links'):
            out.append('- links: '+json.dumps(item['links'],ensure_ascii=False,sort_keys=True))
        out += ['','### Structured item snapshot','',
                '````json',json.dumps(item['semantic'],ensure_ascii=False,indent=2),'````','']
    out += ['## Bound Markdown context','',
            '以下は、対象項目と一緒に承認する該当する節の本文と文書全体の共通条件です（upstreamブロック外）。',
            '節の本文を変更するとその節の項目、共通条件を変更すると文書内の全項目を再確認します。節のない旧形式は文書全体を固定します。','']
    for path,doc in packet.get('documents',{}).items():
        fence='`'*max(4,1+max((len(m.group()) for m in re.finditer(r'`+',doc['prose'])),default=0))
        out += ['### '+path,'',f'- prose sha256: `{doc["prose_sha256"]}`','',fence+'text',doc['prose'],fence,'']
    out += ['## Approval instruction','',
            '承認する場合は、承認するIDを明示してください。全部を承認する場合も「全部承認」と明示してください。',
            '未回答・沈黙・次の話題への移動を承認として扱わないでください。','']
    return '\n'.join(out)


def create_review(root:Path,checkpoint:str='next',write:bool=False)->dict:
    result=inspect(root,'draft');_assert_reviewable(result);byid={r['id']:r for r in result['items']};states=approval_states(root,byid)
    resolved,types=_resolve_checkpoint(root,checkpoint)
    selected=[]
    for row in result['items']:
        if row.get('status')=='retired' or row.get('type') not in types:continue
        selected.append({
            'id':row['id'],'type':row.get('type'),'title':row.get('title'),'status':row.get('status'),
            'basis':row.get('basis'),'file':row['_file'],'line':row['_line'],'item_hash':item_hash(row),
            'dependency_hashes':dependency_hashes(row,byid),'approval_state':states.get(row['id'],{}).get('state','missing'),
            'sources':row.get('sources',[]),'links':row.get('links',{}),
            'acceptance':row.get('acceptance'),'expected':row.get('expected'),
            'semantic':semantic_payload(row),'prose_sha256':row.get('_prose_sha256'),
            'hash_version':hash_version(row),'section':row.get('_section'),
        })
    if not selected:raise WorkbenchError('このcheckpointにレビュー対象の項目がありません')
    created=_now();seed=json.dumps([(x['id'],x['item_hash'],x['dependency_hashes']) for x in selected],sort_keys=True,separators=(',',':')).encode()
    rid='rev-'+created.strftime('%Y%m%dT%H%M%SZ')+'-'+sha(seed)[:10]
    packet={'schema_version':1,'generator':'speckit-workbench-review','review_id':rid,
            'system':result['system'],'profile':profile(root),'checkpoint':resolved,
            'created_at':created.isoformat(),'hash_version':HASH_VERSION,'items':selected,
            'documents':{r['_file']+('#'+r['_section'] if r.get('_section') else ''):
                         {'prose':r['_document_prose'],'prose_sha256':r['_prose_sha256'],
                          'shared_prose_sha256':r.get('_shared_prose_sha256')}
                         for r in result['items'] if r['id'] in {x['id'] for x in selected}},
            'limitations':['レビュー資料であり承認そのものではない。','ユーザー本人性の認証は行わない。']}
    packet['review_fingerprint']=sha(json.dumps(packet,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
    if write:
        base=_review_dir(root);json_path=base/(rid+'.json');md_path=base/(rid+'.md')
        with project_lock(root):
            if json_path.exists() or md_path.exists():raise WorkbenchError('同じreview IDが既にあります。再実行してください')
            atomic_write(json_path,json_text(packet).encode())
            atomic_write(md_path,_packet_markdown(packet).encode())
        packet['saved_json']=json_path.relative_to(root).as_posix();packet['saved_markdown']=md_path.relative_to(root).as_posix()
    return packet


def list_reviews(root:Path)->list[dict]:
    base=_review_dir(root)
    if not base.exists():return []
    rows=[]
    for p in sorted(base.glob('rev-*.json')):
        try:obj=json.loads(p.read_text(encoding='utf-8'))
        except ValueError:continue
        if isinstance(obj,dict) and obj.get('generator')=='speckit-workbench-review':rows.append(obj)
    return rows


def latest_review(root:Path)->dict:
    rows=list_reviews(root)
    if not rows:raise WorkbenchError('保存済みreviewがありません。$upstream-reviewで作成してください')
    return sorted(rows,key=lambda x:x.get('created_at',''))[-1]


def load_review(root:Path,review_id:str)->dict:
    if not REVIEW_ID_RE.fullmatch(review_id):raise WorkbenchError('review IDが不正です')
    path=_review_dir(root)/(review_id+'.json')
    if not path.exists():
        path=inside(root,load_project(root)['docs_dir']+'/governance/reviews/'+review_id+'.json')
    if not path.is_file():raise WorkbenchError('reviewが見つかりません: '+review_id)
    try:obj=json.loads(path.read_text(encoding='utf-8'))
    except ValueError as exc:raise WorkbenchError('review JSONが壊れています') from exc
    if not isinstance(obj,dict) or obj.get('generator')!='speckit-workbench-review':raise WorkbenchError('review形式が不正です')
    return obj


def _replace_items(root:Path, updates:dict[str,dict])->dict[Path,bytes]:
    """Return complete new file contents for the upstream blocks being updated."""
    result=inspect(root,'draft');found={r['id']:r for r in result['items']}
    missing=set(updates)-set(found)
    if missing:raise WorkbenchError('更新対象IDがありません: '+', '.join(sorted(missing)))
    grouped:dict[Path,dict[str,dict]]={}
    for key,obj in updates.items():
        p=inside(root,found[key]['_file']);grouped.setdefault(p,{})[key]=obj
    outputs={}
    pattern=re.compile(r'```upstream\s*\n(.*?)\n```',re.S)
    for path,items in grouped.items():
        text=path.read_text(encoding='utf-8');seen=set()
        def repl(match):
            try:obj=json.loads(match.group(1))
            except ValueError:return match.group(0)
            key=obj.get('id') if isinstance(obj,dict) else None
            if key not in items:return match.group(0)
            seen.add(key)
            return '```upstream\n'+json.dumps(items[key],ensure_ascii=False,indent=2)+'\n```'
        new=pattern.sub(repl,text)
        if seen!=set(items):raise WorkbenchError('承認対象のupstream blockを一意に更新できません: '+str(path))
        outputs[path]=new.encode()
    return outputs


def _write_summary(root:Path)->bytes:
    result=inspect(root,'draft');byid={r['id']:r for r in result['items']};states=approval_states(root,byid)
    out=['<!-- Generated by speckit-workbench -->','# Upstream Approvals','',
         '> 承認記録はローカルのワークフロー証跡であり、本人性を暗号学的に証明するものではありません。','',
         '| ID | Type | Document status | Approval validity | Last review | Approved by | Reference |','|---|---|---|---|---|---|---|']
    for key in sorted(byid):
        row=byid[key];state=states.get(key,{});event=state.get('event') or {}
        vals=[key,row.get('type',''),row.get('status',''),state.get('state','missing'),event.get('review_id',''),event.get('by',''),event.get('reference','')]
        out.append('| '+' | '.join(str(v).replace('|','\\|').replace('\n',' ') for v in vals)+' |')
    out.append('')
    return ('\n'.join(out)).encode()


def approve(root:Path,review_id:str,ids:list[str],by:str,reference:str,apply:bool=False,all_reviewed:bool=False)->dict:
    if not by.strip() or not reference.strip():raise WorkbenchError('--by と --reference は必須です')
    packet=load_review(root,review_id)
    if packet.get('hash_version')!=HASH_VERSION:
        raise WorkbenchError('STALE_REVIEW: 旧版のレビューは本文を固定していません。$upstream-reviewを再実行してください')
    reviewed={x['id']:x for x in packet['items']}
    if all_reviewed:
        if ids:raise WorkbenchError('--all-reviewed と --id は同時に使えません')
        ids=list(reviewed)
    if not ids:raise WorkbenchError('承認する --id を指定してください。全部なら --all-reviewed を明示してください')
    if len(set(ids))!=len(ids):raise WorkbenchError('重複したIDがあります')
    unknown=[i for i in ids if i not in reviewed]
    if unknown:raise WorkbenchError('このreviewにないIDです: '+', '.join(unknown))
    result=inspect(root,'draft');_assert_reviewable(result);byid={r['id']:r for r in result['items']}
    now=_now();updates={}
    # First verify the exact pre-approval review snapshot. Approval may then change
    # lifecycle metadata (status and proposed->agreed basis), but never unreviewed content.
    for key in ids:
        if key not in byid:raise WorkbenchError('現在の文書からIDが消えています: '+key)
        row=byid[key];saved=reviewed[key];cur_hash=item_hash(row);cur_deps=dependency_hashes(row,byid)
        if cur_hash!=saved.get('item_hash') or cur_deps!=saved.get('dependency_hashes'):
            raise WorkbenchError(f'STALE_REVIEW: {key} はレビュー後に変更されています。$upstream-reviewを再実行してください')
        if row.get('type') in NON_APPROVAL_TYPES:raise WorkbenchError('この種別は承認対象外です: '+key)
        new={k:v for k,v in row.items() if not k.startswith('_')}
        new['status']='approved'
        if new.get('basis')=='proposed':new['basis']='agreed'
        updates[key]=new
    # Keep parser-derived prose bindings while calculating post-approval hashes.
    # Only the authored JSON fields are written back by _replace_items.
    future_byid={k:dict(row) for k,row in byid.items()}
    for key,new in updates.items():
        future_byid[key].update(new)
    events=[]
    for key in ids:
        post_hash=item_hash(future_byid[key]);post_deps=dependency_hashes(future_byid[key],future_byid)
        updates[key]['approval']={'by':by,'reference':reference,'date':now.date().isoformat(),
                                  'review_id':review_id,'content_hash':post_hash,'hash_version':hash_version(future_byid[key])}
        events.append({'schema_version':1,'event':'approve','id':key,'review_id':review_id,
                       'checkpoint':packet.get('checkpoint'),'profile':packet.get('profile'),
                       'review_item_hash':reviewed[key].get('item_hash'),'item_hash':post_hash,'hash_version':hash_version(future_byid[key]),
                       'dependency_hashes':post_deps,'by':by,'reference':reference,
                       'date':now.date().isoformat(),'recorded_at':now.isoformat()})
    print('[APPROVE] review='+review_id+' ids='+', '.join(ids))
    for key in ids:print('  '+key+' '+reviewed[key]['item_hash'][:12])
    if not apply:
        print('DRY RUN: 文書・approval ledgerは変更していません。適用は --apply。')
        return {'applied':False,'review_id':review_id,'ids':ids}
    replacements=_replace_items(root,updates)
    ledger=inside(root,LEDGER_PATH);summary=inside(root,internal(load_project(root),'governance/approvals.md','approval-summary.md'))
    targets=set(replacements)|{ledger,summary};old={p:(p.read_bytes() if p.exists() else None) for p in targets}
    try:
        with project_lock(root):
            for p,data in replacements.items():atomic_write(p,data)
            prior=ledger.read_bytes() if ledger.exists() else b''
            addition=''.join(json.dumps(e,ensure_ascii=False,sort_keys=True)+'\n' for e in events).encode()
            atomic_write(ledger,prior+addition)
            atomic_write(summary,_write_summary(root))
        verified=inspect(root,'draft');states=approval_states(root,{r['id']:r for r in verified['items']})
        bad={k:states.get(k,{}).get('state') for k in ids if states.get(k,{}).get('state')!='valid'}
        if bad:raise WorkbenchError('承認記録の自己検査に失敗: '+json.dumps(bad,ensure_ascii=False))
    except Exception:
        for p,data in old.items():
            if data is None:p.unlink(missing_ok=True)
            else:atomic_write(p,data)
        raise
    return {'applied':True,'review_id':review_id,'ids':ids,'ledger':LEDGER_PATH,
            'summary':summary.relative_to(root).as_posix()}


def revoke(root:Path,ids:list[str],by:str,reference:str,apply:bool=False)->dict:
    if not ids or not by.strip() or not reference.strip():raise WorkbenchError('--id, --by, --reference が必要です')
    result=inspect(root,'draft');byid={r['id']:r for r in result['items']};updates={};now=_now();events=[]
    for key in ids:
        if key not in byid:raise WorkbenchError('IDがありません: '+key)
        row=byid[key];new={k:v for k,v in row.items() if not k.startswith('_')};new['status']='proposed';new.pop('approval',None);updates[key]=new
        events.append({'schema_version':1,'event':'revoke','id':key,'by':by,'reference':reference,'date':now.date().isoformat(),'recorded_at':now.isoformat()})
    print('[REVOKE] '+', '.join(ids))
    if not apply:print('DRY RUN: 変更していません。適用は --apply。');return {'applied':False,'ids':ids}
    replacements=_replace_items(root,updates);ledger=inside(root,LEDGER_PATH);summary=inside(root,internal(load_project(root),'governance/approvals.md','approval-summary.md'))
    with project_lock(root):
        for p,data in replacements.items():atomic_write(p,data)
        prior=ledger.read_bytes() if ledger.exists() else b''
        atomic_write(ledger,prior+''.join(json.dumps(e,ensure_ascii=False,sort_keys=True)+'\n' for e in events).encode())
        atomic_write(summary,_write_summary(root))
    return {'applied':True,'ids':ids}


def set_profile(root:Path,value:str,apply:bool=False)->dict:
    if value not in PROFILE_CHECKPOINTS:raise WorkbenchError('profileはsmall/normal/critical')
    path=inside(root,'.specify/workbench.json');c=load_project(root);old=c.get('approval_profile','normal')
    print(f'[APPROVAL PROFILE] {old} -> {value}')
    if apply:
        c['approval_profile']=value
        atomic_write(path,json_text(c).encode())
    else:print('DRY RUN: 変更していません。適用は --apply。')
    return {'old':old,'new':value,'applied':apply}
