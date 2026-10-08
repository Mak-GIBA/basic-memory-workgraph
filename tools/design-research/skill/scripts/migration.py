"""Explicit, locked consolidation. Historical run records and receipts stay immutable."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import urllib.parse

from layout import LEGACY_REPORTS, MARKER, RECORDS, compact
from runtime import Blocked, atomic_bytes, atomic_json, regular_path, relative


def migrate(project, slug, apply=False):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',slug):
        raise Blocked('Invalid migration slug')
    project = regular_path(project)
    parent = regular_path(project/'docs/design-research')
    workspace = regular_path(parent/slug)
    if not workspace.is_dir():
        raise Blocked('Research workspace does not exist')
    # Preview acquires an existing lock read-only; no file/directory is created.
    lock_path = regular_path(parent/'.gan.lock')
    lock = lock_path.open('a+' if apply else 'r') if (apply or lock_path.exists()) else None
    try:
        if lock:
            try:
                fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Blocked('Cannot migrate while a harness is running') from exc
        if compact(workspace):
            return {'applied':False, 'already_compact':True, 'report':str(workspace/'report.md')}
        if regular_path(workspace/'report.md').exists():
            raise Blocked('report.md already exists; migration will not overwrite it')
        originals = {}
        records = {}
        for name in (*LEGACY_REPORTS,*RECORDS):
            path = regular_path(workspace/name)
            if path.exists():
                if not path.is_file() or path.stat().st_size>5_000_000:
                    raise Blocked('Invalid/oversized migration source: '+name)
                originals[name] = path.read_bytes()
                if name in RECORDS:
                    records[name] = json.loads(originals[name].decode('utf-8'))
                    if not isinstance(records[name],dict):
                        raise Blocked('Record must be an object: '+name)
        if not originals:
            raise Blocked('No legacy research documents were found')
        for path in workspace.glob('runs/*/state.json'):
            path = regular_path(path)
            state = json.loads(path.read_text('utf-8'))
            if (not isinstance(state,dict) or state.get('schema_version')!=1
                    or state.get('run_id')!=path.parent.name or not isinstance(state.get('evidence'),dict)):
                raise Blocked('Broken run state: '+str(path))
            if state.get('status')=='running':
                raise Blocked('Cannot migrate a run recorded as running; stop/recover it first')
            from evidence import assert_records
            try:
                assert_records(state,workspace)
            except (KeyError,TypeError) as exc:
                raise Blocked('Malformed evidence records in run state') from exc
        status = records.get('status.json',{})
        if 'status.json' in records and (not isinstance(status.get('run_id'),str) or not status['run_id']
                or not isinstance(status.get('status'),str) or not isinstance(status.get('state_path'),str)
                or status['state_path']!='runs/'+status['run_id']+'/state.json'):
            raise Blocked('Malformed status record identity/path')
        if status.get('status')=='running':
            raise Blocked('Cannot migrate while the current run is running')
        if status:
            path = regular_path(workspace/relative(status.get('state_path','')))
            if not path.is_file():
                raise Blocked('Current status references a missing state')
            state = json.loads(path.read_text('utf-8'))
            if (not isinstance(state,dict) or state.get('schema_version')!=1
                    or state.get('run_id')!=status.get('run_id') or state.get('status')!=status.get('status')):
                raise Blocked('Current status does not match its run state')
            from evidence import assert_records
            try:
                assert_records(state,workspace)
            except (KeyError,TypeError) as exc:
                raise Blocked('Malformed evidence records in current run state') from exc
        if 'evidence.json' in records:
            ledger=records['evidence.json']
            if ledger.get('schema_version')!=1:
                raise Blocked('Unsupported evidence ledger schema')
            # Draft omissions/placeholders can move; malformed/duplicate IDs cannot.
            for group in ('constraints','sources','claims','candidates','experiments'):
                rows=ledger.get(group)
                if not isinstance(rows,list):
                    raise Blocked('Malformed ledger collection: '+group)
                seen=set()
                for row in rows:
                    if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id']:
                        raise Blocked('Malformed ledger ID: '+group)
                    if row['id'] in seen:
                        raise Blocked('Duplicate ledger ID: '+row['id'])
                    seen.add(row['id'])
            # Draft skeletons remain drafts. Completed ledgers must pass the same checks.
            if status.get('status') in {'research_complete','passed','reviewed'} and state.get('dossier'):
                from evidence import verify_artifacts
                checked = verify_artifacts(records['evidence.json'],workspace,state.get('evidence',{}))
                if not checked['valid']:
                    raise Blocked('Broken evidence ledger: '+'; '.join(checked['errors'][:5]))
        if 'research-log.json' in records and records['research-log.json'].get('schema_version')!=1:
            raise Blocked('Unsupported research log schema')
        mapping = {name:'report.md#legacy-'+name.removesuffix('.md') for name in LEGACY_REPORTS if name in originals}
        mapping.update({name:'.internal/'+name for name in RECORDS if name in originals})
        bodies = {}
        for name in LEGACY_REPORTS:
            if name not in originals:
                continue
            anchor = 'legacy-'+name.removesuffix('.md')
            counts = {}; lines = []; in_fence = False
            for line in originals[name].decode('utf-8').splitlines():
                if line.lstrip().startswith('```'):
                    in_fence = not in_fence
                heading = re.match(r'^(#{1,6}) +(.+?) *#*$',line) if not in_fence else None
                if heading:
                    key = re.sub(r'[^\w\- ]','',heading[2].lower()).replace(' ','-')
                    n = counts.get(key,0);counts[key] = n+1
                    key += '-'+str(n) if n else ''
                    ident = anchor+'--'+key
                    mapping[name+'#'+key] = 'report.md#'+ident
                    lines.append('<a id="'+ident+'"></a>')
                    line = '#'*min(6,len(heading[1])+2)+' '+heading[2]
                lines.append(line)
            bodies[name] = '\n'.join(lines)

        def rebase(target):
            u = urllib.parse.urlsplit(target)
            if u.scheme or u.netloc or target.startswith('/'):
                return target
            path = os.path.normpath(urllib.parse.unquote(u.path)) if u.path else origin
            key = path+('#'+urllib.parse.unquote(u.fragment) if u.fragment else '')
            if key in mapping:
                return mapping[key]
            if path in RECORDS and path in mapping:
                return mapping[path]+('?' + u.query if u.query else '')+('#'+u.fragment if u.fragment else '')
            if path in mapping and u.fragment:
                raise Blocked('Cannot resolve migrated heading: '+origin+' -> '+target)
            if u.path and not regular_path(workspace/path).exists():
                raise Blocked('Local migration link target is missing: '+origin+' -> '+target)
            return target
        lines = [MARKER,'# 調査・検証報告','',
                 '## 結論と確認してほしいこと','',
                 f"実行ID: {status.get('run_id','未実行')} / 状態: **{status.get('status','下書き')}**",
                 status.get('reason',''), '',
                 '旧資料を統合しました。元の文章と証拠を保持しています。移行は調査の再実行や採用承認ではありません。',
                 '下記の各節の実行IDを確認してください。異なる実行の結果は今回の結果に含めません。','']
        for origin,body in bodies.items():
            text = re.sub(r'(\]\()([^\s)]+)([^)]*\))',lambda m:m[1]+rebase(m[2])+m[3],body)
            lines += ['<a id="legacy-'+origin.removesuffix('.md')+'"></a>',
                      '## '+{'design-research.md':'調査・比較','decision.md':'採用候補と条件',
                               'review.md':'確認結果と指摘','fix-report.md':'変更と再検証',
                               'reference-implementations.md':'参考となる設計・実装'}[origin],
                      '', '<!-- Migrated from '+origin+' -->', text, '']
        outputs = {'report.md':('\n'.join(lines)+'\n').encode()}
        outputs.update({'.internal/'+name:data for name,data in originals.items() if name in RECORDS})
        layout = {'schema_version':1,'generator':'design-research','layout':'compact-v1'}
        outputs['.internal/layout.json'] = (json.dumps(layout,indent=2)+'\n').encode()
        for target in outputs:
            if regular_path(workspace/target).exists():
                raise Blocked('Migration destination already exists: '+target)
        # Leave custom inputs/history untouched; block incoming Markdown links that would break.
        for folder,dirs,files in os.walk(project):
            dirs[:]=[d for d in dirs if d not in {'.git','node_modules','.venv','venv','runs','migrations','__pycache__'}
                     and not (Path(folder)/d).is_symlink()]
            for name in files:
                path=Path(folder)/name
                if (not name.endswith('.md') or path.is_symlink() or path.stat().st_size>5_000_000
                        or (path.parent==workspace and name in originals)):
                    continue
                for target in re.findall(r'\]\(([^\s)]+)',path.read_text('utf-8')):
                    u=urllib.parse.urlsplit(target)
                    old=Path(os.path.normpath(path.parent/urllib.parse.unquote(u.path)))
                    if not u.scheme and old.parent==workspace and old.name in originals:
                        raise Blocked('Update the custom incoming link before migration: '+str(path.relative_to(project))+' -> '+target)
        digest = hashlib.sha256(b''.join(n.encode()+data for n,data in sorted(originals.items()))).hexdigest()[:20]
        backup = '.internal/migrations/compact-'+digest
        preview = {'applied':False,'report':str(workspace/'report.md'), 'sources':sorted(originals),
                   'links':mapping,'backup':str(workspace/backup),'content':outputs['report.md'].decode(),
                   'preserved':'runs/, immutable receipts/snapshots and custom documents'}
        if not apply:
            return preview
        base = regular_path(workspace/backup)
        if base.exists():
            raise Blocked('Backup destination already exists')
        base.mkdir(parents=True)
        created = []
        try:
            for name,data in originals.items():
                atomic_bytes(base/name,data)
            atomic_json(base/'manifest.json',{k:v for k,v in preview.items() if k!='content'})
            for target,data in outputs.items():
                path = regular_path(workspace/target)
                created.append(path)
                atomic_bytes(path,data)
            for name in originals:
                (workspace/name).unlink()
            if not compact(workspace):
                raise Blocked('Migration layout self-check failed')
        except BaseException:
            for path in created:
                path.unlink(missing_ok=True)
            for name,data in originals.items():
                atomic_bytes(workspace/name,data)
            shutil.rmtree(base)
            raise
        preview['applied'] = True
        return preview
    finally:
        if lock:
            lock.close()
