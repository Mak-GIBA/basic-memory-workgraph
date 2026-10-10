#!/usr/bin/env python3
"""Run independent offline tests, optionally against the staged checkout modules."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-root',type=Path)
a=p.parse_args()
root=Path(__file__).resolve().parent
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
if a.source_root:env['UPGRADE_SOURCE_ROOT']=str(a.source_root.absolute())
else:env.pop('UPGRADE_SOURCE_ROOT',None)
for directory in (root/'tests',root/'previous_report_upgrade/tests'):
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(directory),'-v'],env=env)
    if result.returncode:raise SystemExit(result.returncode)

source=a.source_root.absolute() if a.source_root else root/'overlay'
env['PYTHONPATH']=str(source/'tools/speckit-upstream')+os.pathsep+env.get('PYTHONPATH','')
result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(root/'overlay/tools/speckit-upstream/tests'),'-v'],env=env)
raise SystemExit(result.returncode)
