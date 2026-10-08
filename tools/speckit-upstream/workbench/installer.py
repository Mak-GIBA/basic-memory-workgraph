from __future__ import annotations
import argparse, json, os, shutil, sys, time
from pathlib import Path
from . import VERSION, SPECIFY_PIN
from .common import *
from .command_skills import COMMANDS, render_skill, metadata
ROOT=Path(__file__).resolve().parents[1]


def global_files()->dict[Path,bytes]:
    loc=locations();release=loc['data']/'releases'/VERSION;files={}
    for folder in ['workbench','assets']:
        for p in sorted((ROOT/folder).rglob('*')):
            if p.is_symlink():raise WorkbenchError('配布物にsymlinkがあります')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
                files[release/p.relative_to(ROOT)]=p.read_bytes()
    files[release/'swb.py']=(ROOT/'swb.py').read_bytes()
    launch='#!/bin/sh\n# Managed by speckit-workbench\nexec '+shlex.quote(sys.executable)+' '+shlex.quote(str(release/'swb.py'))+' "$@"\n'
    files[loc['bin']/'speckit-workbench']=launch.encode()
    skill=(ROOT/'assets/skill/SKILL.md').read_text().replace('@COMMAND@',shlex.quote(str(loc['bin']/'speckit-workbench'))).replace('@ASSETS@',str(release/'assets'))
    files[loc['skill']/'SKILL.md']=skill.encode()
    files[loc['skill']/'agents/openai.yaml']=metadata('speckit-workbench','上流整理の共通入口。新規・既存・変更・不具合・設計改善。').encode()
    for name, (_, desc) in COMMANDS.items():
        folder=loc['skill'].parent/name
        files[folder/'SKILL.md']=render_skill(name,loc['bin']/'speckit-workbench',release/'assets').encode()
        files[folder/'agents/openai.yaml']=metadata(name,desc).encode()
    for name in ['README_COMMANDS.md','LICENSE']:
        files[release/name]=(ROOT/name).read_bytes()
    return files


def dependency_plan(skip:bool)->dict:
    loc=locations();found=executable('specify')
    if skip:return {'status':'skipped','path':found,'reason':'--skip-specify'}
    if found:
        reject_symlinks(Path(found).parent)
        output=checked([found,'version'])
        help_text=checked([found,'init','--help'])
        if '--integration' not in help_text or '--non-interactive' not in help_text:
            raise WorkbenchError('既存specifyが現行CLIに未対応。自動更新は行いません。更新方針を確認してください。')
        return {'status':'reuse','path':found,'version_output':output[-2000:],
                'note':'PATHで見つかったCLIの確認のみ。配布元や完全な互換性を認証したものではない。'}
    env=loc['data']/'tooling'/('specify-'+SPECIFY_PIN)
    exe=env/'bin/specify'
    if env.exists():
        if not exe.is_file():raise WorkbenchError(f'不完全な専用venvがあります。内容を確認してから再実行してください: {env}')
        return {'status':'link-existing-env','path':str(exe),'env':str(env),'version_output':checked([str(exe),'version'])[-2000:]}
    return {'status':'install','path':str(exe),'env':str(env),'pin':SPECIFY_PIN,
            'commands':[[sys.executable,'-m','venv',str(env)],
                        [str(env/'bin/python'),'-m','pip','install','--disable-pip-version-check',f'specify-cli=={SPECIFY_PIN}']]}


def install(apply:bool=False,skip_specify:bool=False,update:bool=False)->None:
    if sys.version_info<(3,11):raise WorkbenchError('Python 3.11以上が必要です')
    if os.environ.get('SUDO_USER'):raise WorkbenchError('sudoは使わず通常ユーザーで実行してください')
    loc=locations();manifest=loc['config']/'install.json';reject_symlinks(manifest)
    old=read_json(manifest) if manifest.exists() else {'managed':{}}
    if old.get('managed') is None or not isinstance(old.get('managed',{}),dict):raise WorkbenchError('管理manifestが不正')
    files=global_files();changes=[]
    for p,data in files.items():
        reject_symlinks(p)
        if p.exists():
            if not p.is_file():raise WorkbenchError('配置先がファイルではありません: '+str(p))
            cur=p.read_bytes()
            if cur==data:continue
            if not update or old['managed'].get(str(p))!=sha(cur):
                raise WorkbenchError(f'既存・編集済みファイルは上書きしません: {p}\n未編集の管理ファイルの更新だけ --update で許可できます。')
        changes.append(p)
    dep=dependency_plan(skip_specify)
    print('[DEPENDENCY] '+json_text(dep))
    for p in changes:print('[WRITE] '+str(p))
    if not changes:print('[SKIP] グローバル資材は同一内容です')
    if not apply:
        print('DRY RUN: 対象ファイル・CLIを変更していません。適用は --apply。')
        return
    # Installing an external dependency is intentionally not part of local-file rollback.
    # A failed venv install remains visible for diagnosis; do not silently mask failures.
    if dep['status']=='install':
        env=Path(dep['env']);reject_symlinks(env)
        env.parent.mkdir(parents=True,exist_ok=True)
        for argv in dep['commands']:
            print('[RUN] '+shlex.join(argv));checked(argv,timeout=300)
        checked([dep['path'],'version'])
    if dep['status'] in {'install','link-existing-env'}:
        p=loc['bin']/'specify';reject_symlinks(p)
        launcher=('#!/bin/sh\n# SpecKit CLI; intentionally retained by Workbench uninstall\nexec '+shlex.quote(dep['path'])+' "$@"\n').encode()
        if p.exists() and p.read_bytes()!=launcher:raise WorkbenchError('既存specifyを上書きしません: '+str(p))
        if not p.exists():atomic_write(p,launcher,0o755)
        dep['launcher']=str(p)
    rollback={};created=[]
    try:
        for p in changes:
            if p.exists():
                rollback[p]=p.read_bytes()
                backup=loc['data']/'backups'/(str(time.time_ns())+'-'+p.name)
                atomic_write(backup,rollback[p])
            else:created.append(p)
            atomic_write(p,files[p],0o755 if p.parent==loc['bin'] else 0o644)
        m={'schema_version':1,'workbench_version':VERSION,'managed':{**old.get('managed',{}),**{str(p):sha(data) for p,data in files.items()}},
           'specify':dep,'python':sys.executable}
        # Preserve dependency provenance across idempotent re-runs when it is still the same executable.
        prior_specify = old.get('specify')
        if (isinstance(prior_specify, dict) and prior_specify.get('launcher')
                and prior_specify['launcher'] == dep.get('path')):
            m['specify'] = prior_specify
        atomic_write(manifest,json_text(m).encode())
    except Exception:
        for p,data in rollback.items():atomic_write(p,data)
        for p in created:p.unlink(missing_ok=True)
        raise
    print('\n導入完了。既存ECC・Basic Memory・Codex config・Hooks・AGENTS.mdは変更していません。')
    print('コマンド: '+str(loc['bin']/'speckit-workbench'))
    print('Codex入力欄: $upstream-existing / $upstream-new / $upstream-change / $upstream-bug / $upstream-refactor / $upstream-check')
    print('後続の長い初期プロンプトは不要。対象だけを続けて入力できます。')
    print('PATHにない場合: export PATH='+shlex.quote(str(loc['bin']))+':"$PATH"')


def uninstall(apply:bool)->None:
    loc=locations();path=loc['config']/'install.json'
    m=read_json(path);kept=[];deleted=[]
    for name,digest in m.get('managed',{}).items():
        p=Path(name)
        if not p.is_absolute() or '..' in p.parts:
            raise WorkbenchError('manifestに不正なパスがあります')
        allowed=p==loc['bin']/'speckit-workbench' or p.is_relative_to(loc['skill']) or p.is_relative_to(loc['data']/'releases') or any(p.is_relative_to(loc['skill'].parent/n) for n in COMMANDS)
        if not allowed:raise WorkbenchError('manifestに対象外パスがあります: '+name)
        reject_symlinks(p)
        if not p.exists():continue
        if not p.is_file() or sha(p.read_bytes())!=digest:
            print('[KEEP modified] '+name);kept.append(name);continue
        print('[REMOVE] '+name);deleted.append(p)
    if apply:
        for p in deleted:p.unlink()
        if not kept:path.unlink(missing_ok=True)
    print('各プロジェクトの文書、SpecKit CLIと専用venv、バックアップは残します。')


def main():
    p=argparse.ArgumentParser(description='SpecKitと上流ドキュメント手順をユーザー共通環境へ導入')
    group=p.add_mutually_exclusive_group();group.add_argument('--apply',action='store_true');group.add_argument('--dry-run',action='store_true')
    p.add_argument('--skip-specify',action='store_true',help='CLIを入れず手順・文書ツールだけ配置する（オフライン準備用）')
    p.add_argument('--update',action='store_true',help='自分が配置した未編集のWorkbenchファイルのみ更新。SpecKitは更新しない')
    a=p.parse_args()
    try:install(a.apply,a.skip_specify,a.update)
    except (WorkbenchError,OSError,ValueError) as e:print('ERROR: '+str(e),file=sys.stderr);return 2
    return 0
