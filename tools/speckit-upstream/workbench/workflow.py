"""Deterministic workflow selection and snapshot-bound structural review gates.

A gate is a local consistency check, NOT permission control for Codex and NOT an
app test. No model calls, hook edits, deployments, or application code edits.
"""
from __future__ import annotations
import datetime, json
from pathlib import Path
from . import VERSION
from .common import WorkbenchError, inside, read_json, json_text, sha, atomic_write, load_project, project_lock
from .project_ops import MODES, ROOT
from .trace import inspect, documents
from .approval_core import LEDGER_PATH
from .approval import approval_plan

GATE_PATH = '.specify/workbench/gate-ready.json'
GENERATOR = 'speckit-workbench-gate'
DESCRIPTIONS = {
    'new': '新規アプリ・新機能。目的とユーザー価値から上流を作る。実装は別途承認。',
    'existing': '既存システム。確認できた現状、合意済み仕様、改善案を分ける。',
    'change': '仕様変更。元の要件と変更理由、影響範囲、互換性を明示する。',
    'bug': '不具合の上流整理。期待挙動と現象、根拠、再現条件、修正・回帰計画を接続する。',
    'refactor': 'リファクタリングの上流整理。挙動の不変条件と品質改善目標を明示する。',
    'check': '上流文書の構造と内容を点検する。アプリの動作テストではない。',
}

def flow(root: Path, mode: str) -> str:
    if mode not in DESCRIPTIONS:
        raise WorkbenchError('未対応のワークフローです')
    p=inside(root,'.specify/workbench.json')
    state='未準備: system IDを確認し、attachの差分を提示して承認後に--applyする。'
    if p.exists():
        c=load_project(root)
        state=f'準備済み: system={c["system"]}, docs={c["docs_dir"]}, layout={c.get("document_layout","legacy")}, mode={c.get("specify_mode","unknown")}, approval_profile={c.get("approval_profile","normal")}'
    text=f'# 固定ワークフロー: upstream-{mode}\n\n対象: {root}\n状態: {state}\n\n{DESCRIPTIONS[mode]}\n\n'
    text+=(ROOT/'assets/prompts/common.md').read_text(encoding='utf-8')+'\n'
    if mode in {'existing', 'check', 'change', 'bug', 'refactor'}:
        text+='\n## 既存要件・実現方式の見直し\n'
        text+='参照資料: '+str(ROOT/'assets/references/REASSESSMENT.md')+'\n'
        text+='要件・評価方法・方式を見直す場合はこの資料を読む。判断を左右する不確実性があれば、Design Researchの利用を明示しresearch/auditを実行して結果を仕様へ戻す。\n'
    if mode in MODES:
        text+=(ROOT/'assets/prompts'/f'{mode}.md').read_text(encoding='utf-8')+'\n'
    else:
        text+='''## 文書監査の順序
1. 対象システムと正本の所在を確認する。
2. check --phase draft でID・参照・フィールドを点検する。
3. 根拠、分解粒度、受入条件、矛盾、As-Isと規範仕様の混同を内容レビューする。
4. 修正案を提示し、承認後にだけ本文を直す。承認情報を代筆しない。
5. trace --write で内部の対応索引を更新する。
6. 合意済みの全上流計画を確定する場合だけgate --writeを実行する。
'''
    if p.exists():
        plan=approval_plan(root)
        text+='\n## 承認チェックポイント\n'
        for row in plan['checkpoints']:
            text+=f"- {row['checkpoint']}: {'完了' if row['complete'] else '要レビュー'} / pending={', '.join(row['pending']) if row['pending'] else '-'}\n"
        text+='レビューは $upstream-review、明示承認の記録は $upstream-approve を使用する。\n'
    text+='''
## 全モードの固定成果物と停止条件
- システム目的、関係者ニーズ、シナリオ/ストーリー、要件、仕様/設計、検証計画。
- 各項目のID、出典/根拠、状態、上位目的と下流設計/検証へのリンク。
- As-Is/合意済み仕様/To-Be、不明点、未確認の数値、承認待ちを分離した記録。
- 実行した構造検査の結果と、正本のIDによる対応関係。
- 計画・要求・設計のレビュー点で確認する。省略には理由を記録する。
- 実装、DB変更、デプロイはこのワークフローに含まれない。別の明示承認が必要。
- 必要な研究・実測はDesign Researchのresearch/auditで行う。runによるアプリ修正は含めない。CLI flow自体は研究を起動しない。
- 未実行のテストをPASSにしない。gateは構造検査だけである。
- 既存文書があれば更新し、同じ要求の全文を別ファイルへ複製しない。
'''
    return text

def snapshot(root: Path) -> dict[str,str]:
    c=load_project(root)
    paths=set(documents(root,c))
    paths.add(inside(root,'.specify/workbench.json'))
    ledger=inside(root,LEDGER_PATH)
    if ledger.is_file():paths.add(ledger)
    constitution=inside(root,'.specify/memory/constitution.md')
    if constitution.is_file():paths.add(constitution)
    return {p.relative_to(root).as_posix():sha(p.read_bytes()) for p in sorted(paths)}

def snapshot_hash(files: dict[str,str]) -> str:
    return sha(json.dumps(files,sort_keys=True,separators=(',',':')).encode('utf-8'))

def run_gate(root: Path, write: bool=False) -> dict:
    # Check before and after inspection to avoid silently certifying a changing tree.
    before=snapshot(root)
    result=inspect(root,'ready')
    plan=approval_plan(root)
    for checkpoint in plan['checkpoints']:
        if not checkpoint['complete']:
            result['findings'].append({'severity':'error','code':'INCOMPLETE_CHECKPOINT',
                'item':checkpoint['checkpoint'],
                'message':'承認段階が未完了です。missing='+', '.join(checkpoint['missing_categories'])+
                          ' / pending='+', '.join(checkpoint['pending'])})
    result['errors']=sum(f['severity']=='error' for f in result['findings'])
    result['warnings']=len(result['findings'])-result['errors']
    after=snapshot(root)
    if before!=after:
        raise WorkbenchError('検査中に文書が変更されました。再実行してください。')
    output={
        'schema_version':1, 'generator':GENERATOR, 'workbench_version':VERSION,
        'system':result['system'], 'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'passed':result['errors']==0,
        'verdict':'UPSTREAM_STRUCTURE_READY' if result['errors']==0 else 'BLOCKED',
        'scope':result['scope'], 'fingerprint':snapshot_hash(after), 'files':after,
        'errors':result['errors'], 'warnings':result['warnings'], 'findings':result['findings'],
        'coverage':result['coverage'], 'approval_plan':plan,
        'limitations':['構造検査とhash-bound approval整合性のみ。ユーザー本人性は認証しない。',
                       'アプリのテスト/品質やCodexの行動を強制しない。',
                       'approval ledgerは署名済み証明や改ざん耐性のある記録ではない。'],
    }
    if write:
        with project_lock(root):
            target=inside(root,GATE_PATH)
            if target.exists() and read_json(target).get('generator')!=GENERATOR:
                raise WorkbenchError('gateの保存先に別のファイルがあります。上書きしません。')
            if snapshot(root)!=after:
                raise WorkbenchError('記録前に文書が変更されました。再実行してください。')
            atomic_write(target,json_text(output).encode())
        output['saved_to']=GATE_PATH
    return output

def verify_gate(root: Path) -> dict:
    target=inside(root,GATE_PATH)
    if not target.is_file():raise WorkbenchError('gate記録がありません。gate --writeを実行してください。')
    saved=read_json(target)
    if saved.get('generator')!=GENERATOR or saved.get('schema_version')!=1:
        raise WorkbenchError('未対応のgate記録です')
    current=snapshot(root)
    if saved.get('files')!=current or saved.get('fingerprint')!=snapshot_hash(current):
        raise WorkbenchError('STALE: 検査後に文書・設定の追加/変更/削除があります。gateを再実行してください。')
    if saved.get('passed') is not True:
        raise WorkbenchError('BLOCKED: 前回の構造検査は合格していません。')
    # Recompute rather than trusting a stored PASS flag.
    result=run_gate(root,False)
    if not result['passed']:raise WorkbenchError('BLOCKED: 現在の構造検査が不合格です。')
    if result['fingerprint']!=saved['fingerprint'] or result['files']!=saved['files']:
        raise WorkbenchError('STALE: 再検査中に文書が変更されました。')
    return {**result,'record_is_current':True}
