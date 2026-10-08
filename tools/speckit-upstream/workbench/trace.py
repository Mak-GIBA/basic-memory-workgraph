"""Validate a documented JSON-in-Markdown trace convention, not semantic truth."""
from __future__ import annotations
import json, re
from collections import defaultdict
from pathlib import Path
from .common import WorkbenchError, atomic_write, inside, json_text, load_project, sha, identifier
from .approval_core import approval_states, coverage_status, EXEMPTIBLE_CATEGORIES
from .layout import compact

REQS={'requirement','quality','interface','data','operation','constraint'}
TYPES={'goal','stakeholder','need','capability','story','business_rule',*REQS,
       'design','decision','verification','issue','change','evidence','risk'}
LINKS={'derives_from','addresses','belongs_to','satisfies','verifies','changes',
       'conflicts_with','supersedes','depends_on','supports'}
STATUSES={'draft','proposed','approved','retired'}
BASES={'observed','agreed','proposed','unknown'}
PLACEHOLDER=re.compile(r'\b(TBD|TODO|TBC)\b|要記入|未記入|未決定|要確認',re.I)


def documents(root: Path, config: dict) -> list[Path]:
    files=set()
    for rel in [config['docs_dir'],'specs','.specify/bugs']:
        base=inside(root,rel)
        if base.exists():
            for p in base.rglob('*'):
                if p.is_symlink():
                    raise WorkbenchError(f'文書ツリーのsymlinkは走査しません: {p}')
                if p.is_file() and p.suffix=='.md' and 'traceability' not in p.relative_to(base).parts:
                    files.add(p)
    for rel in config.get('extra_docs',[]):
        p=inside(root,rel)
        if not p.is_file(): raise WorkbenchError(f'登録文書がありません: {p}')
        files.add(p)
    return sorted(files)


def parse_file(root:Path,path:Path,scoped:bool|None=None)->tuple[list[dict],list[dict]]:
    if scoped is None:
        cfg=inside(root,'.specify/workbench.json')
        scoped=cfg.is_file() and compact(load_project(root))
    if path.stat().st_size>2_000_000: raise WorkbenchError(f'文書が2MBを超えます。分割してください: {path}')
    try: text=path.read_text(encoding='utf-8')
    except UnicodeError as exc: raise WorkbenchError(f'UTF-8で保存してください: {path}') from exc
    items=[]; findings=[]; rel=path.relative_to(root).as_posix(); lines=text.splitlines()
    start=None; buf=[]; prose=[]; sections={}; scope=None; saw_scope=False
    for n,line in enumerate(lines,1):
        if start is None:
            opening=re.fullmatch(r'<!-- upstream:section ([A-Za-z0-9][A-Za-z0-9_-]{0,100}) -->',line.strip())
            closing=line.strip()=='<!-- /upstream:section -->'
            if scoped and (opening or closing or 'upstream:section' in line):
                saw_scope=True
                if opening and scope is None and opening[1] not in sections:
                    scope=opening[1];sections[scope]=[]
                elif closing and scope is not None:
                    scope=None
                else:
                    findings.append({'severity':'error','code':'INVALID_SCOPE','item':rel,
                                     'message':f'{n}行: 節の重複・入れ子・不正な開始/終了があります'})
                continue
            if line.strip()=='```upstream': start=n;buf=[]
            else: (prose if scope is None else sections[scope]).append(line)
        elif line.strip()=='```':
            try:
                obj=json.loads('\n'.join(buf))
                if not isinstance(obj,dict): raise ValueError('objectが必要')
                obj=dict(obj);obj['_file']=rel;obj['_line']=start;obj['_file_sha256']=sha(path.read_bytes())
                obj['_section']=scope
                items.append(obj)
            except ValueError as exc:
                findings.append({'severity':'error','code':'INVALID_JSON','item':rel,
                                 'message':f'{start}行: {exc}'})
            start=None
        else: buf.append(line)
    if start is not None:
        findings.append({'severity':'error','code':'UNCLOSED_BLOCK','item':rel,'message':f'{start}行のupstreamブロックが閉じられていません'})
    # Shared ordinary prose belongs to every item defined in this document.
    # JSON-only edits remain item-scoped; unrelated files are not bound here.
    if scope is not None:
        findings.append({'severity':'error','code':'INVALID_SCOPE','item':rel,'message':'節が閉じられていません'})
    document_prose='\n'.join(prose)
    prose_hash=sha(document_prose.encode('utf-8'))
    # Appending a scoped item adds separator newlines outside the scope. They
    # must not change the shared conditions of previously approved items.
    shared_prose=document_prose.strip('\n')
    shared_hash=sha(shared_prose.encode('utf-8'))
    for item in items:
        if saw_scope and item['_section'] is None:
            findings.append({'severity':'error','code':'INVALID_SCOPE','item':rel,
                             'message':f"{item['_line']}行: 項目は明示した節内に置いてください"})
        if item['_section'] is not None:
            section_prose='\n'.join(sections[item['_section']])
            item['_shared_prose']=shared_prose
            item['_shared_prose_sha256']=shared_hash
            item['_section_prose']=section_prose
            item['_document_prose']=shared_prose+'\n\n'+section_prose
            item['_prose_sha256']=sha(section_prose.encode('utf-8'))
        else:
            item['_document_prose']=document_prose
            item['_prose_sha256']=prose_hash
    return items,findings


def has_document_content(text:str)->bool:
    """Reject empty/header-only/template shells; not a semantic quality grade."""
    text=re.sub(r'\A\ufeff?---[ \t]*\n.*?\n---[ \t]*(?:\n|$)', '', text, flags=re.S)
    text=re.sub(r'<!--[\s\S]*?-->', '', text)
    text=re.sub(r'(?ms)^[ \t]*```upstream[ \t]*\n.*?^[ \t]*```[ \t]*$', '', text)
    lines=text.splitlines()
    for i,line in enumerate(lines):
        value=line.strip()
        if (not value or re.match(r'^#{1,6}(?:[ \t]+|$)', value)
                or re.fullmatch(r'(?:[-*_][ \t]*){3,}', value)
                or re.fullmatch(r'[`~]{3,}[^ \t]*',value)):
            continue
        # A Markdown table's header and delimiter are not content rows.
        if '|' in value:
            separator=lambda x: bool(re.fullmatch(r'[|: \t-]+',x.strip()) and '-' in x)
            if separator(value) or (i+1<len(lines) and separator(lines[i+1])):
                continue
        # Empty bullets, checkboxes, punctuation or an empty table cell do not count.
        if not any(c.isalnum() for c in value):
            continue
        return True
    return False


def inspect(root:Path,phase:str='draft')->dict:
    config=load_project(root);items=[];findings=[];scanned=[]
    def note(code:str,key:str,msg:str,required=False,always=False):
        findings.append({'severity':'error' if always or (required and phase=='ready') else 'warning',
                         'code':code,'item':key,'message':msg})
    for rel in config.get('required_docs',[]):
        target=inside(root,rel)
        if not target.is_file():
            note('MISSING_DOCUMENT',rel,'必要な文書がありません。既存資料へ統合する場合は管理対象を明示的に調整してください',required=True)
        elif target.stat().st_size>2_000_000:
            note('DOCUMENT_TOO_LARGE',rel,'文書を分割してください',always=True)
        else:
            try: text=target.read_text(encoding='utf-8')
            except UnicodeError as exc: raise WorkbenchError(f'UTF-8で保存してください: {target}') from exc
            if not has_document_content(text):
                note('EMPTY_DOCUMENT',rel,'必須文書が空、見出しのみ、またはメタデータだけです。本文または適用除外の具体的理由を記載してください',required=True)
            if re.search(r'\b(TBD|TODO|TBC)\b|【要記入】|【未記入】',text,re.I):
                note('DOCUMENT_TBD',rel,'必要な文書に未記入・未決定の雛形が残っています',required=True)
    for p in documents(root,config):
        rows,err=parse_file(root,p,compact(config));items+=rows;findings+=err;scanned.append(str(p.relative_to(root)))
    if not items: note('NO_ITEMS','project','雛形だけです。目的・要求・設計等の項目を作成してください',always=True)
    byid={};valid=[]
    for row in items:
        key=row.get('id','')
        try: identifier(key)
        except (WorkbenchError,TypeError):
            note('BAD_ID',str(key),f"不正なID: {row['_file']}:{row['_line']}",always=True);continue
        if key in byid:
            note('DUPLICATE_ID',key,'IDが複数の文書で定義されています',always=True);continue
        byid[key]=row;valid.append(row)
        for field in ['type','system','status','basis']:
            if not isinstance(row.get(field),str):
                note('BAD_FIELD',key,f'{field}は文字列が必要',always=True);row[field]=''
        if not isinstance(row.get('result','not_run'),str):
            note('BAD_RESULT',key,'resultは文字列が必要',always=True);row['result']=''
        ev=row.get('result_evidence',[])
        if not isinstance(ev,list) or any(not isinstance(x,str) for x in ev):
            note('BAD_RESULT_EVIDENCE',key,'result_evidenceは文字列配列が必要',always=True);row['result_evidence']=[]
        if row.get('type') not in TYPES: note('BAD_TYPE',key,'未対応のtype',always=True)
        if row.get('system')!=config['system']: note('WRONG_SYSTEM',key,'対象システムが一致しません',always=True)
        if not key.startswith(config['system']+'-'): note('ID_PREFIX',key,'IDはsystem IDから始めてください',always=True)
        if row.get('status') not in STATUSES: note('BAD_STATUS',key,'statusが不正',always=True)
        if row.get('basis') not in BASES: note('BAD_BASIS',key,'observed/agreed/proposed/unknownを明示',always=True)
        for k in ['title','owner']:
            if not isinstance(row.get(k),str) or not row[k].strip() or PLACEHOLDER.search(row[k]):
                note('MISSING_'+k.upper(),key,f'{k}を具体化してください',required=True)
        sources=row.get('sources')
        if not isinstance(sources,list) or any(not isinstance(x,str) for x in sources):
            note('BAD_SOURCES',key,'sourcesは参照文字列の配列',always=True)
        elif not sources or any(PLACEHOLDER.search(x) for x in sources):
            note('NO_SOURCE',key,'根拠・出典を確認してください',required=True)
        if 'readiness_exemptions' in row:
            ex=row['readiness_exemptions']
            if (row.get('type')!='goal' or not isinstance(ex,dict)
                    or any(k not in EXEMPTIBLE_CATEGORIES or not isinstance(v,str)
                           or not v.strip() or PLACEHOLDER.search(v) for k,v in ex.items())):
                note('BAD_READINESS_EXEMPTION',key,'need/storyの省略理由のみ、goalのreadiness_exemptionsへ具体的に記載できます',always=True)
        links=row.get('links')
        if not isinstance(links,dict): note('BAD_LINKS',key,'linksはobject',always=True);row['links']={}
        else:
            for relation,targets in list(links.items()):
                if relation not in LINKS or not isinstance(targets,list) or any(not isinstance(t,str) for t in targets):
                    note('BAD_RELATION',key,f'不正な関係: {relation}',always=True);row['links'][relation]=[]
        # Hash-bound approval validity is checked after all items and links are known.
        if row.get('status')!='approved' and row.get('status')!='retired' and row.get('type') not in {'evidence','issue','risk'}:
            note('NOT_APPROVED',key,'ready段階では人の合意をhash-bound approvalとして記録してください',required=True)
        if row.get('type') in REQS|{'story','goal'}:
            value=row.get('acceptance','')
            if not isinstance(value,str) or not value.strip() or PLACEHOLDER.search(value):
                note('NO_ACCEPTANCE',key,'受入条件・測定方法・合格条件を具体化してください',required=True)
        if row.get('type') in REQS and row.get('basis') in {'observed','unknown'}:
            note('ASIS_NOT_REQUIREMENT',key,'観測した現状と、合意する規範的要件を分けてください',required=True)
        if row.get('type')=='verification':
            if row.get('method') not in {'test','analysis','inspection','demonstration'}:
                note('NO_METHOD',key,'verification methodを明示',required=True)
            if not row.get('expected') or PLACEHOLDER.search(str(row.get('expected'))):
                note('NO_EXPECTED',key,'判定条件を明示',required=True)
            if row.get('result') not in {'not_run','pass','fail','partial'}:
                note('BAD_RESULT',key,'resultはnot_run/pass/fail/partial',always=True)
            if row.get('result')=='pass' and not row.get('result_evidence'):
                note('NO_RESULT_EVIDENCE',key,'PASSには実行証跡への参照が必要。結果の真偽はこの検査では保証しません',always=True)
    # Evaluate approval records only after all items have been parsed, so content hashes
    # and dependency hashes can be checked against the current document set.
    byid={row['id']:row for row in valid}
    states=approval_states(root,byid)
    for row in valid:
        if row.get('status')!='approved':
            continue
        state=states.get(row['id'],{}).get('state')
        if state=='valid':
            continue
        code={
            'legacy_unbound':'LEGACY_APPROVAL_UNBOUND',
            'stale_content':'STALE_APPROVAL',
            'stale_dependency':'STALE_DEPENDENCY_APPROVAL',
            'metadata_mismatch':'APPROVAL_METADATA_MISMATCH',
            'status_mismatch':'APPROVAL_STATUS_MISMATCH',
            'revoked':'APPROVAL_REVOKED',
            'missing':'APPROVAL_MISSING',
        }.get(state,'APPROVAL_INVALID')
        reason=states.get(row['id'],{}).get('reason','approval record is invalid')
        note(code,row['id'],reason+'。$upstream-reviewで再レビューし、明示承認後に$upstream-approveを実行してください',always=True)

    coverage=coverage_status(byid,states)
    for category,entry in coverage.items():
        if not entry['satisfied']:
            note('MISSING_CATEGORY',category,'必要な上流カテゴリがありません: '+category+'。既存項目を参照し、未作成と明示的な適用除外を区別してください',required=True)

    reverse=defaultdict(list)
    for row in valid:
        for rel,targets in row.get('links',{}).items():
            for target in targets:
                if target not in byid:
                    note('BROKEN_REFERENCE',row['id'],f'{rel} -> {target} がありません',always=True);continue
                reverse[target].append({'id':row['id'],'relation':rel})
                if target==row['id']: note('SELF_LINK',row['id'],rel,always=True)
                if byid[target].get('status')=='retired' and row.get('status')!='retired' and rel not in {'supersedes','conflicts_with'}:
                    note('RETIRED_REFERENCE',row['id'],target,required=True)
                if rel=='satisfies' and byid[target].get('type') not in REQS|{'story','need','goal'}:
                    note('LINK_TYPE',row['id'],f'satisfies先の型が不適切: {target}',always=True)
                if rel=='verifies' and (row.get('type')!='verification' or byid[target].get('type') not in REQS|{'design','story','goal'}):
                    note('LINK_TYPE',row['id'],f'verifiesの型が不適切: {target}',always=True)
    def reaches_goal(start:str)->bool:
        seen=set();stack=[start]
        while stack:
            key=stack.pop()
            if key in seen:continue
            seen.add(key);r=byid.get(key,{})
            if r.get('type')=='goal':return True
            for rel in ['derives_from','addresses','belongs_to','satisfies','verifies','changes']:
                stack.extend(r.get('links',{}).get(rel,[]))
        return False
    for row in valid:
        key=row['id'];typ=row.get('type');active=row.get('status')!='retired'
        if active and typ in REQS|{'need','capability','story','design','decision','change','issue','verification'} and not reaches_goal(key):
            note('NO_GOAL_PATH',key,'目的への追跡経路がありません',required=True)
        if active and typ in REQS:
            if not any(x['relation']=='satisfies' and byid[x['id']].get('type') in {'design','decision'} for x in reverse[key]):
                note('NO_DESIGN',key,'対応する設計を登録してください',required=True)
            if not any(x['relation']=='verifies' for x in reverse[key]):
                note('NO_VERIFICATION',key,'要件に対応する検証計画がありません',required=True)
        if active and typ=='story' and not any(x['relation'] in {'derives_from','satisfies'} for x in reverse[key]):
            note('UNREFINED_STORY',key,'ストーリーを具体的な要件・仕様へ展開してください',required=True)
        if active and typ in {'design','decision'} and not row.get('links',{}).get('satisfies'):
            note('ORPHAN_DESIGN',key,'設計が満たす要件・目的を明示してください',required=True)
    colors={}
    for initial in byid:
        if colors.get(initial)==2:continue
        stack=[(initial,False)]
        while stack:
            key,leaving=stack.pop()
            if leaving:colors[key]=2;continue
            if colors.get(key)==2:continue
            if colors.get(key)==1:
                note('DERIVATION_CYCLE',key,'derives_fromに循環があります',always=True);continue
            colors[key]=1;stack.append((key,True))
            for target in byid[key].get('links',{}).get('derives_from',[]):
                if target in byid:stack.append((target,False))
    errors=sum(x['severity']=='error' for x in findings)
    warnings=len(findings)-errors
    return {'schema_version':1,'system':config['system'],'phase':phase,
            'verdict':'NOT_READY' if errors else ('STRUCTURE_OK_WITH_WARNINGS' if warnings else 'STRUCTURE_OK'),
            'scope':'文書の構造・参照・必要フィールドとhash-bound approval整合性を検査する。要求内容の妥当性、ユーザー本人性、アプリの合否は判定しない。',
            'errors':errors,'warnings':warnings,'documents':scanned,'items':valid,
            'incoming':dict(reverse),'approval_states':states,'coverage':coverage,'findings':findings}


def matrix(result:dict)->str:
    def cell(x):return str(x).replace('|','\\|').replace('\n',' ')
    out=['# 上流トレーサビリティ（自動生成）','',result['scope'],'',
         '| ID | 種別 | 状態 | タイトル | 出ていく関係 | 参照元 | 正本 |','|---|---|---|---|---|---|---|']
    for r in result['items']:
        outgoing='; '.join(rel+': '+', '.join(ts) for rel,ts in r.get('links',{}).items())
        incoming='; '.join(x['id']+' ('+x['relation']+')' for x in result['incoming'].get(r['id'],[]))
        out.append('| '+' | '.join(map(cell,[r['id'],r.get('type'),r.get('status'),r.get('title'),outgoing,incoming,r['_file']+':'+str(r['_line'])]))+' |')
    out+=['','## 検査結果',f"{result['verdict']}: errors={result['errors']}, warnings={result['warnings']}",'']
    for f in result['findings']:out.append(f"- {f['severity']} / {f['code']} / {f['item']}: {f['message']}")
    return '\n'.join(out)+'\n'


def save_report(root:Path,result:dict)->None:
    c=load_project(root);base=c['docs_dir']+'/traceability/'
    if compact(c):
        p=inside(root,'.specify/workbench/trace/index.json')
        if p.exists() and json.loads(p.read_text()).get('generator')!='speckit-workbench':
            raise WorkbenchError('生成先に手書きファイルがあります: '+str(p))
        atomic_write(p,json_text({**result,'generator':'speckit-workbench'}).encode())
        return
    for rel,text in [('index.json',json_text(result)),('matrix.md',matrix(result))]:
        p=inside(root,base+rel)
        if p.exists():
            existing=p.read_text(encoding='utf-8')
            if rel=='index.json':
                try: owned=json.loads(existing).get('generator')=='speckit-workbench'
                except ValueError: owned=False
            else:owned=existing.startswith('<!-- Generated by speckit-workbench -->')
            if not owned:raise WorkbenchError(f'生成先に手書きファイルがあります。上書きしません: {p}')
    owned_result={**result,'generator':'speckit-workbench'}
    atomic_write(inside(root,base+'index.json'),json_text(owned_result).encode())
    atomic_write(inside(root,base+'matrix.md'),('<!-- Generated by speckit-workbench -->\n'+matrix(result)).encode())
