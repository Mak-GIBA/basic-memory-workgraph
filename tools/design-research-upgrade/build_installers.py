#!/usr/bin/env python3
"""Build both offline distribution scripts from two verified original base installers."""
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
import urllib.request
import zipfile
from pinned_base import (obtain_base, unpack_base, git_blob, safe_relative, TrustedRedirect,
                         safe_output, BASE_COMMIT, MAX_BASE)
from integrate import apply_to_stage

ROOT = Path(__file__).resolve().parent
U_BLOB = '141d62a811888b5791d7e5a23355b9238f58e6d0'
U_PAYLOAD = '2c03d352579233578bc39445bc16c49bfe7235de05236fe9a159b66fd4772c3c'


def obtain_upstream(local, offline):
    if local:
        if not local.is_file() or local.stat().st_size > MAX_BASE:
            raise ValueError('Missing or oversized pinned upstream installer')
        data = local.read_bytes()
    elif offline:
        raise ValueError('--offline requires both original installers in --base-dir')
    else:
        data = None; errors=[]
        opener = urllib.request.build_opener(TrustedRedirect())
        for endpoint in (
            'https://raw.githubusercontent.com/Mak-GIBA/basic-memory-workgraph/'+BASE_COMMIT+'/install_speckit_upstream.sh',
            'https://api.github.com/repos/Mak-GIBA/basic-memory-workgraph/contents/install_speckit_upstream.sh?ref='+BASE_COMMIT):
            try:
                request = urllib.request.Request(endpoint, headers={'User-Agent':'DesignResearch-Codex-Installer/2.3'})
                with opener.open(request, timeout=30) as r: data=r.read(MAX_BASE+1)
                if len(data)>MAX_BASE: raise ValueError('Oversized base response')
                if endpoint.startswith('https://api.'):
                    value=json.loads(data)
                    if value.get('encoding') != 'base64' or value.get('sha') != U_BLOB:
                        raise ValueError('Wrong upstream blob in API response')
                    data=base64.b64decode(''.join(value['content'].split()), validate=True)
                if git_blob(data) != U_BLOB: raise ValueError('Wrong upstream installer hash')
                break
            except (OSError, ValueError) as exc:
                errors.append(str(exc)); data=None
        if data is None: raise ValueError('Could not retrieve pinned upstream base: '+'; '.join(errors))
    if not data or len(data)>MAX_BASE or git_blob(data)!=U_BLOB:
        raise ValueError('Upstream base must be the original pinned 2.0.1, not an upgrade bootstrap')
    return data


def unpack_upstream(raw, repo):
    if git_blob(raw)!=U_BLOB: raise ValueError('Incorrect upstream base hash')
    marker=b"\n: <<'SWB_EMBEDDED_RESOURCES_V1'\n"
    if raw.count(marker)!=1: raise ValueError('Incorrect upstream payload boundary')
    encoded=raw.split(marker,1)[1].rsplit(b'\nSWB_EMBEDDED_RESOURCES_V1',1)[0]
    data=base64.b64decode(b''.join(encoded.split()),validate=True)
    if hashlib.sha256(data).hexdigest()!=U_PAYLOAD: raise ValueError('Incorrect upstream payload SHA-256')
    root=repo/'tools/speckit-upstream'; root.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        entries=z.infolist(); seen=set()
        if len(entries)>1000 or sum(x.file_size for x in entries)>15_000_000: raise ValueError('Oversized upstream archive')
        for e in entries:
            name=safe_relative(e.filename)
            if e.is_dir() or name in seen or stat.S_ISLNK(e.external_attr>>16): raise ValueError('Unsafe upstream archive entry')
            seen.add(name)
        if not {'build_single.py','swb.py','install.py','workbench/command_skills.py'}<=seen: raise ValueError('Incomplete upstream archive')
        for e in entries:
            p=root/safe_relative(e.filename); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(z.read(e)); p.chmod(0o644)
    (repo/'install_speckit_upstream.sh').write_bytes(raw)


def checked(argv, cwd, logs, label, env):
    r=subprocess.run(argv,cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    (logs/(label+'.log')).write_text('$ '+' '.join(argv)+'\n'+r.stdout,'utf-8')
    if r.returncode:
        raise ValueError(label+' failed; nothing installed.\n'+r.stdout[-9000:])


def build(output, base_dir=None, offline=False):
    output=safe_output(output)
    if output.exists() and any(output.iterdir()): raise ValueError('Build output must be missing or empty')
    local_d=Path(base_dir)/'install_design_research.sh' if base_dir else None
    local_u=Path(base_dir)/'install_speckit_upstream.sh' if base_dir else None
    raw_d=obtain_base(local_d,offline); raw_u=obtain_upstream(local_u,offline)
    with tempfile.TemporaryDirectory(prefix='codex-research-build-') as tmp:
        work=Path(tmp); repo=work/'repo'; logs=work/'validation'; logs.mkdir()
        unpack_base(raw_d,repo); unpack_upstream(raw_u,repo)
        metadata=apply_to_stage(repo)
        home=work/'home'; home.mkdir()
        env={**os.environ,'HOME':str(home),'CODEX_HOME':str(home/'.codex'),
             'PYTHONDONTWRITEBYTECODE':'1','PYTHON_BIN':sys.executable,
             'CODEX_INTERFACE_SOURCE_ROOT':str(repo)}
        checks=[
            ([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v'], 'codex-interface'),
            ([sys.executable,str(ROOT/'core_upgrade/run_tests.py'),'--source-root',str(repo)], 'core-upgrade'),
            ([sys.executable,'tools/design-research/build_installer.py'], 'build-design-research'),
            ([sys.executable,'tools/design-research/build_installer.py','--check'], 'check-design-research'),
            ([sys.executable,'tools/speckit-upstream/build_single.py','install_speckit_upstream.sh'], 'build-upstream'),
            ([sys.executable,'tools/speckit-upstream/build_single.py','--check','install_speckit_upstream.sh'], 'check-upstream'),
            (['bash','-n','install_design_research.sh'], 'bash-design-research'),
            (['bash','-n','install_speckit_upstream.sh'], 'bash-upstream'),
            (['bash','install_design_research.sh','--self-test','--json'], 'selftest-design-research'),
            (['bash','install_speckit_upstream.sh','--self-test'], 'selftest-upstream'),
        ]
        for cmd,label in checks:
            print('Checking '+label+'...',file=sys.stderr)
            checked(cmd,repo,logs,label,env)
        output.mkdir(parents=True,exist_ok=True)
        for name in ('install_design_research.sh','install_speckit_upstream.sh'):
            p=output/name
            with p.open('xb') as f: f.write((repo/name).read_bytes())
            p.chmod(0o755)
        import shutil
        shutil.copytree(logs,output/'validation')
        shutil.copytree(repo/'tools',output/'sources'/'tools',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        if (repo/'tests').exists(): shutil.copytree(repo/'tests',output/'sources'/'tests')
        metadata.update(base_commit=BASE_COMMIT,network_required_for_built_design_research=False,
                        checks=[label for _,label in checks],
                        limitations=['No live Codex/model run in this build. Original Design Research repository tests are not embedded in its base installer; upstream self-test includes its bundled suite.'])
        (output/'build-summary.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n','utf-8')
    return metadata


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True); p.add_argument('--base-dir',type=Path); p.add_argument('--offline',action='store_true')
    a=p.parse_args()
    try: print(json.dumps(build(a.out,a.base_dir,a.offline),ensure_ascii=False,indent=2))
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr); raise SystemExit(2)
