#!/usr/bin/env python3
"""Install Codex-facing research workflows from a pinned base plus an embedded upgrade.

This distribution is an assembly bootstrap: first build downloads two verified base
installers. --build-only creates the ordinary offline single-file distributions.
No GitHub authentication, clone, model call or repository write is performed.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import zipfile

COMPONENT = '@COMPONENT@'
BUNDLE_SHA256 = '@BUNDLE_SHA256@'
MARKER = b'\n__CODEX_RESEARCH_BUNDLE__\n'
VERSIONS = {'design-research':'2.5.0', 'upstream':'2.0.6'}
ENTRIES = ['design-research']


def safe_path(path):
    path=Path(os.path.abspath(Path(path).expanduser()))
    for node in (path,*path.parents):
        if node.is_symlink():raise ValueError('Refusing symlink output: '+str(node))
        if node!=path and node.exists() and not node.is_dir():raise ValueError('Output parent is not a directory')
    return path


def relative(name):
    if not name or '\\' in name or '\x00' in name or ':' in name:raise ValueError('Unsafe archive member')
    parts=name.split('/')
    if any(x in {'','.','..'} for x in parts) or Path(name).is_absolute():raise ValueError('Unsafe archive path')
    return name


def bundle(path):
    raw=path.read_bytes()
    if raw.count(MARKER)!=1:raise ValueError('Embedded bundle marker is missing or repeated')
    data=base64.b64decode(b''.join(raw.split(MARKER,1)[1].split()),validate=True)
    if hashlib.sha256(data).hexdigest()!=BUNDLE_SHA256:raise ValueError('Embedded bundle checksum mismatch')
    return data


def extract(data,destination):
    destination=safe_path(destination)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError('Bundle output must be absent or empty')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        entries=z.infolist();seen=set()
        if len(entries)>2000 or sum(e.file_size for e in entries)>48*1024*1024:raise ValueError('Oversized embedded archive')
        for e in entries:
            n=relative(e.filename)
            if not n.startswith('codex_interface_upgrade/') or e.is_dir() or n in seen or stat.S_ISLNK(e.external_attr>>16):
                raise ValueError('Unsafe or duplicate archive member')
            seen.add(n)
        required={'codex_interface_upgrade/build_installers.py','codex_interface_upgrade/integrate.py',
                  'codex_interface_upgrade/command_assets.py','codex_interface_upgrade/installer_commands.py'}
        if not required<=seen:raise ValueError('Incomplete embedded bundle')
        for e in entries:
            p=destination/e.filename;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(e));p.chmod(0o644)
    return destination/'codex_interface_upgrade'


def parse(argv):
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False,
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog='''Default: design-research installs; upstream only plans unless --apply is passed.
Installer options (passed to the original managed installer after build):
  design-research: --update --skills-dir DIR --project DIR --force --uninstall
                  --status --doctor --self-test --extract DIR --json
  upstream:       --apply --update --skip-specify --doctor --self-test --extract DIR

Examples (Codex entry points are typed in Codex, not in your shell):
  bash install_design_research.sh --dry-run --update
  bash install_design_research.sh --update
  bash install_speckit_upstream.sh --apply --update
  bash install_design_research.sh --list-skills
  bash install_design_research.sh --bundle-self-test
  bash install_design_research.sh --build-only ./offline-installers

--dry-run does not download, install, or inspect an existing destination.
--build-only outputs both rebuilt scripts and build logs, without installing.
--base-dir requires the ORIGINAL pinned 2.0.1 files, not previous upgrade wrappers.
A generated Design Research installer installs offline. Upstream's --skip-specify
prevents its original optional SpecKit dependency installation.
''')
    p.add_argument('--base-dir',type=Path,help='Directory with both original pinned installers')
    p.add_argument('--offline',action='store_true',help='Do not fetch base files; --base-dir required for a build')
    p.add_argument('--build-only',type=Path,metavar='DIRECTORY')
    p.add_argument('--bundle-self-test',action='store_true',help='Offline tests of this embedded package, not live Codex')
    p.add_argument('--extract-bundle',type=Path,metavar='DIRECTORY',help='Inspect all upgrade sources offline')
    p.add_argument('--list-skills',action='store_true',help='Show Codex-facing entry names; no install or network')
    p.add_argument('--dry-run',action='store_true')
    p.add_argument('--version',action='version',version=COMPONENT+' '+VERSIONS.get(COMPONENT,'')+' (assembly bootstrap)')
    a,rest=p.parse_known_args(argv)
    special=sum(bool(v) for v in (a.bundle_self_test,a.extract_bundle,a.list_skills,a.build_only))
    if special>1:p.error('Choose one bundle operation')
    if special and rest:p.error('Bundle operations cannot be combined with installation options')
    if a.dry_run and (a.bundle_self_test or a.extract_bundle or a.list_skills):p.error('--dry-run applies to install or build only')
    # Catch misspelled installer options before any network activity.
    flagsets={'design-research':{'--update','--uninstall','--status','--doctor','--self-test','--force','--json','--print-mcp-config'},
              'upstream':{'--apply','--update','--skip-specify','--doctor','--self-test'}}
    valuesets={'design-research':{'--skills-dir','--project','--extract'},'upstream':{'--extract'}}
    i=0
    while i<len(rest):
        word=rest[i];key,sep,val=word.partition('=')
        if key in valuesets[COMPONENT]:
            if not sep:
                i+=1
                if i>=len(rest) or rest[i].startswith('--'):p.error('Missing value for '+key)
            elif not val:p.error('Empty value for '+key)
        elif word not in flagsets[COMPONENT]:p.error('Unknown installer option: '+word)
        i+=1
    return a,rest


def main(installer,argv):
    if sys.version_info<(3,11):raise ValueError('Python 3.11+ is required')
    args,rest=parse(argv)
    data=bundle(installer)
    if args.list_skills:
        names=ENTRIES if COMPONENT=='design-research' else ['upstream-new','upstream-existing','upstream-change','upstream-bug','upstream-refactor','upstream-check','upstream-review','upstream-approve']
        print(json.dumps({'component':COMPONENT,'codex_entries':['$'+n for n in names],
                          'installed_now':False,'note':'These are Codex Skills, not shell commands.'},ensure_ascii=False,indent=2));return 0
    if args.extract_bundle:
        root=extract(data,args.extract_bundle)
        print(json.dumps({'extracted':str(root),'network':False,'installed':False},indent=2));return 0
    no_apply=COMPONENT=='upstream' and not any(x in rest for x in ('--apply','--doctor','--self-test','--extract')) and not any(x.startswith('--extract=') for x in rest)
    if args.dry_run or (no_apply and not args.build_only and not args.bundle_self_test):
        print(json.dumps({'action':'assembly_plan','component':COMPONENT,'version':VERSIONS[COMPONENT],
            'base_commit':'d3f46e0d591b45cb2423317030a489b91566e891',
            'network_now':False,'destination_changed':False,'destination_inspected':False,
            'network_on_apply':args.base_dir is None and not args.offline,
            'offline_would_block':args.offline and args.base_dir is None,
            'base_files':['install_design_research.sh','install_speckit_upstream.sh'],
            'installer_arguments':rest,'build_only':str(args.build_only) if args.build_only else None,
            'codex_entries':['$'+n for n in ENTRIES]},ensure_ascii=False,indent=2));return 0
    if args.offline and args.base_dir is None and not args.bundle_self_test:
        raise ValueError('--offline build/install requires --base-dir with both original pinned base files')
    # Resolve user paths before changing the build subprocess working directory.
    args.base_dir=safe_path(args.base_dir) if args.base_dir else None
    args.build_only=safe_path(args.build_only) if args.build_only else None
    for i,word in enumerate(rest):
        if word in ('--skills-dir','--project','--extract'):
            rest[i+1]=str(safe_path(rest[i+1]))
        elif any(word.startswith(k+'=') for k in ('--skills-dir','--project','--extract')):
            key,_,value=word.partition('=');rest[i]=key+'='+str(safe_path(value))
    with tempfile.TemporaryDirectory(prefix='codex-research-installer-') as tmp:
        work=Path(tmp);root=extract(data,work/'bundle')
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHON_BIN':sys.executable}
        if args.bundle_self_test:
            # Prevent inherited staging-root overrides from silently changing the tested code.
            env.pop('CODEX_INTERFACE_SOURCE_ROOT',None);env.pop('UPGRADE_SOURCE_ROOT',None)
            for cmd in ([sys.executable,'-m','unittest','discover','-s',str(root/'tests'),'-v'],
                        [sys.executable,str(root/'core_upgrade/run_tests.py')]):
                result=subprocess.run(cmd,cwd=root,env=env,check=False)
                if result.returncode:return result.returncode
            return 0
        output=args.build_only or work/'built'
        cmd=[sys.executable,str(root/'build_installers.py'),'--out',str(output)]
        if args.base_dir:cmd+=['--base-dir',str(args.base_dir)]
        if args.offline:cmd+=['--offline']
        result=subprocess.run(cmd,cwd=root,env=env,check=False)
        if result.returncode:return result.returncode
        if args.build_only:return 0
        filename='install_design_research.sh' if COMPONENT=='design-research' else 'install_speckit_upstream.sh'
        return subprocess.run(['bash',str(output/filename),*rest],env=env,check=False).returncode


if __name__=='__main__':
    try:raise SystemExit(main(Path(sys.argv[1]),sys.argv[2:]))
    except (ValueError,OSError,subprocess.SubprocessError,zipfile.BadZipFile) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);raise SystemExit(2)
