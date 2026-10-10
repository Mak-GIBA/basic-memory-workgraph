#!/usr/bin/env python3
"""Apply the proposed-method report upgrade to a verified checkout, then rebuild.

Only the inspected upstream report/harness versions (and this upgrade's own outputs)
are accepted. No network, Git mutation, model invocation or configuration changes.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parent
ROOT = Path("tools/design-research")
SKILL = ROOT / "skill"
MANIFEST = ROOT / "method-report-upgrade.json"
GENERATED = Path("install_design_research.sh")
VERSION = "2.2.0"
UPGRADE = "proposed-method-report-v1"
INSPECTED_HEAD = "d3f46e0d591b45cb2423317030a489b91566e891"
BASE_BLOBS = {
    SKILL / "scripts/harness.py": "482606e4bd83628e8f7b13585b1488d59921223b",
    SKILL / "scripts/report.py": "a986bd5c9942fc31291531625c460b56991b7888",
}


def safe(path):
    p = Path(os.path.abspath(Path(path).expanduser()))
    for node in [*reversed(p.parents), p]:
        if node.is_symlink():
            raise ValueError("Refusing symlink path: " + str(node))
        if node != p and node.exists() and not node.is_dir():
            raise ValueError("Parent is not a directory: " + str(node))
    return p


def blob_sha(content):
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Upstream integration anchor changed or is ambiguous: " + old[:90])
    return source.replace(old, new, 1)


def inside_function(source, name, old, new):
    tree = ast.parse(source)
    functions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(functions) != 1:
        raise ValueError("Expected one upstream function: " + name)
    node = functions[0]
    lines = source.splitlines(keepends=True)
    body = "".join(lines[node.lineno-1:node.end_lineno])
    lines[node.lineno-1:node.end_lineno] = [replace_once(body, old, new)]
    return "".join(lines)


def patch_harness(source):
    source = replace_once(source, 'HERE = Path(__file__).resolve().parent',
        '# ' + UPGRADE + '\nfrom proposal_report import require_method_report, prepare_preview\nfrom method_workflow import role_instructions, additional_gate_reasons\n\nHERE = Path(__file__).resolve().parent')
    source = replace_once(source, 'Comparison research normally includes 2-3 distinct candidates and a current/minimal baseline.',
        'Comparison-only research normally includes 2-3 distinct candidates and a current/minimal baseline. For proposed-method research use the frozen target_methods (default five including baseline).')
    source = inside_function(source, 'role_prompt', '"evidence", "sources", "discovery", "input_review", "fixes"]}',
        '"evidence", "sources", "discovery", "input_review", "fixes", "method_report_preview"]}')
    source = inside_function(source, 'role_prompt', 'return BASE + "\\nROLE: " + role',
        'return BASE + role_instructions(role, state) + "\\nROLE: " + role')
    source = inside_function(source, 'experiments', '    proposal = state["proposal"]',
        '    prepare_preview(state, workspace, run_dir)\n    proposal = state["proposal"]')
    source = inside_function(source, 'validate_review', '        state["dossier"] = dossier',
        '        require_method_report(dossier, state)\n        state["dossier"] = dossier')
    source = inside_function(source, 'gate_reasons', '    return reasons',
        '    reasons.extend(additional_gate_reasons(state))\n    return reasons')
    source = inside_function(source, 'config_from', '"reference_urls": args.reference_url}',
        '"reference_urls": args.reference_url,\n            "report_profile": getattr(args, "report_profile", "comparison"),\n            "target_methods": getattr(args, "target_methods", 5)}')
    source = inside_function(source, 'parser', '        sub.add_argument("--brief", required=True)', '''        if mode == "research":
            sub.add_argument("--report-profile", choices=("proposed-method", "comparison"),
                             default="comparison",
                             help="Require a detailed Methods chapter and actual design figures")
            sub.add_argument("--target-methods", type=int, choices=range(3, 21), default=5,
                             help="Approximate method count, including baseline; budgets unchanged")
        sub.add_argument("--brief", required=True)''')
    source, count = re.subn(r'(?m)^VERSION = "[0-9]+\.[0-9]+\.[0-9]+"$', 'VERSION = "' + VERSION + '"', source)
    if count != 1:
        raise ValueError("Harness version declaration changed")
    compile(source, 'harness.py', 'exec')
    return source


def patch_report(source):
    source = replace_once(source, 'from layout import MARKER, compact, record_path',
        'from layout import MARKER, compact, record_path\nfrom proposal_report import chapter_for_state, method_required')
    source = inside_function(source, 'publish', "        lines += ['', '### 主張と根拠', '']", '''        lines += chapter_for_state(state, workspace, run_dir)
        if method_required(state):
            lines += ['', '## 実験設定・結果・根拠', '']
        lines += ['', '### 主張と根拠', '']''')
    source = inside_function(source, 'publish', "    write(workspace,'report.md',lines)", '''    if method_required(state):
        if not dossier:
            lines += chapter_for_state(state, workspace, run_dir)
        headings = {
            '# 調査・検証報告': '# 研究報告書',
            '## 結論と確認してほしいこと': '## 要旨と現時点の結論',
            '## 調査・比較・検証': '## 背景・課題と比較対象',
            '## 残る確認と実行記録': '## 限界・次の実験と再現性',
        }
        lines = [headings.get(line, line) for line in lines]
    write(workspace,'report.md',lines)''')
    source = inside_function(source, 'publish_legacy', '        report += ["", "## Claims and Evidence", ""]',
        '        report += chapter_for_state(state, workspace, run_dir)\n        report += ["", "## Claims and Evidence", ""]')
    compile(source, 'report.py', 'exec')
    return source


def append_block(source, text, name):
    begin, end = f'<!-- {name}:begin -->', f'<!-- {name}:end -->'
    block = begin + '\n' + text.strip() + '\n' + end
    if begin in source or end in source:
        if source.count(begin) != 1 or source.count(end) != 1 or source.index(begin) > source.index(end):
            raise ValueError("Mismatched documentation markers")
        prefix, rest = source.split(begin)
        _, suffix = rest.split(end)
        return prefix + block + suffix
    return source.rstrip() + '\n\n' + block + '\n'


def overlay_files():
    """Ignore runtime bytecode; reject links before constructing the source overlay."""
    root = PACKAGE / 'overlay'
    result = []
    for source in sorted(root.rglob('*')):
        if source.is_symlink():
            raise ValueError("Overlay contains a symlink")
        if '__pycache__' in source.relative_to(root).parts or source.suffix == '.pyc':
            continue
        if source.is_file():
            result.append(source)
    return result


def _verify_previous_upgrade(repo):
    manifest = safe(repo / MANIFEST)
    if not manifest.exists():
        return False
    data = json.loads(manifest.read_text('utf-8'))
    if data.get('upgrade') != UPGRADE or not isinstance(data.get('files'), dict) or not data['files']:
        raise ValueError("Unknown or malformed upgrade manifest")
    for rel, digest in data['files'].items():
        if Path(rel).is_absolute() or '..' in Path(rel).parts:
            raise ValueError("Unsafe upgrade manifest path")
        path = safe(repo / rel)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Installed upgrade has local changes; reconcile before reapplying: " + rel)
    # Newer copies of this package must not silently get skipped.
    for source in overlay_files():
        rel = source.relative_to(PACKAGE / 'overlay')
        exact_earlier_diagram = (rel.as_posix() == 'tools/design-research/skill/scripts/proposal_report.py'
                                 and (repo / rel).is_file()
                                 and hashlib.sha256((repo / rel).read_bytes()).hexdigest() == '6039f5ed0492753d99a0f31bb6750e8548b7499328a16a361a30bd4e322558c7')
        if (not (repo / rel).is_file() or (repo / rel).read_bytes() != source.read_bytes()) and not exact_earlier_diagram:
            raise ValueError("A different upgrade payload is already applied; inspect changes")
    return True


def plan(repo, *, verify_base=True):
    files = {}
    for rel, sha in BASE_BLOBS.items():
        raw = safe(repo / rel).read_bytes()
        if verify_base and blob_sha(raw) != sha:
            raise ValueError(f'Upstream or local edits differ from the inspected base: {rel}. No files changed; merge against that version explicitly.')
        files[rel] = (patch_harness if rel.name == 'harness.py' else patch_report)(raw.decode('utf-8')).encode('utf-8')
    for source in overlay_files():
        files[source.relative_to(PACKAGE / 'overlay')] = source.read_bytes()
    # Carry the v5 ideation instructions forward, while replacing the standalone-only handoff.
    for rel, name in ((SKILL / 'SKILL.md', 'skill'), (SKILL / 'references/roles.md', 'roles'),
                      (SKILL / 'references/protocol.md', 'protocol'), (SKILL / 'references/evidence-format.md', 'contract')):
        source = safe(repo / rel).read_text('utf-8')
        if name == 'skill':
            source = replace_once(source,
                'gan-harness.sh research --project <target>',
                'gan-harness.sh research --report-profile proposed-method --target-methods 5 --project <target>')
        if name in {'skill', 'roles', 'protocol'} and '<!-- method-ideation-upgrade:begin -->' in source:
            # This replaces our earlier managed block; arbitrary prose is preserved.
            source = append_block(source, (PACKAGE / 'integration' / (name + '.md')).read_text('utf-8'), 'method-ideation-upgrade')
        else:
            source = append_block(source, (PACKAGE / 'integration' / (name + '.md')).read_text('utf-8'), UPGRADE)
        files[rel] = source.encode('utf-8')
    original_builder = (repo / ROOT / 'build_installer.py').read_text('utf-8')
    original_installer = (repo / ROOT / 'install_design_research.py').read_text('utf-8')
    bv = re.search(r'"version":\s*"([0-9]+\.[0-9]+\.[0-9]+)"', original_builder)
    iv = re.search(r'VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', original_installer)
    if not bv or not iv or bv[1] != iv[1]:
        raise ValueError("Existing builder/installer versions disagree; preserve and reconcile")
    for rel, pattern in ((ROOT / 'build_installer.py' , r'("version":\s*")[0-9]+\.[0-9]+\.[0-9]+(")'),
                         (ROOT / 'install_design_research.py', r'(VERSION\s*=\s*")[0-9]+\.[0-9]+\.[0-9]+(")')):
        text = safe(repo / rel).read_text('utf-8')
        text, count = re.subn(pattern, lambda m:m[1]+VERSION+m[2], text)
        if count != 1:
            raise ValueError("Version anchor changed: " + str(rel))
        files[rel] = text.encode('utf-8')
    for rel, content in files.items():
        safe(repo / rel)
        if rel.suffix == '.py':
            compile(content, str(rel), 'exec')
    return files


def apply(repo, *, dry_run=False):
    repo = safe(repo)
    if not repo.is_dir():
        raise ValueError("Repository directory does not exist")
    if _verify_previous_upgrade(repo):
        return {'action':'skip', 'reason':'same verified upgrade already applied', 'version':VERSION}
    changes = plan(repo)
    # Added files may come from v5, but never overwrite unrelated custom extensions.
    prior_overlay = PACKAGE / 'previous-v5'
    for rel in [p.relative_to(PACKAGE/'overlay') for p in overlay_files()]:
        target = safe(repo / rel)
        if target.exists() and target.read_bytes() != changes[rel]:
            previous = prior_overlay / rel
            # Only the exact earlier v5 bytes or the inspected upstream report template are managed.
            permitted_template = rel == SKILL/'templates/report.md' and blob_sha(target.read_bytes()) == 'a1c292f7477304cdb65d1c5cbb47b6ac43225566'
            if not permitted_template and (not previous.is_file() or target.read_bytes() != previous.read_bytes()):
                raise ValueError('Custom extension would be overwritten: ' + str(rel))
    modified = {p:b for p,b in changes.items() if not (repo/p).exists() or (repo/p).read_bytes()!=b}
    result = {'action':'upgrade', 'version':VERSION, 'base_commit':INSPECTED_HEAD,
              'files':[p.as_posix() for p in modified], 'rebuild':True, 'network':False}
    if dry_run:
        return {**result,'dry_run':True}
    targets = list(modified) + [GENERATED, MANIFEST]
    snapshots = {}
    for rel in targets:
        p=safe(repo/rel)
        if p.exists() and not p.is_file():
            raise ValueError('Expected ordinary file: '+str(p))
        snapshots[rel]=(p.read_bytes(),p.stat().st_mode & 0o777) if p.exists() else None
    backup=Path(tempfile.mkdtemp(prefix='design-research-report-backup-'))
    for rel, previous in snapshots.items():
        if previous:
            p=backup/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(previous[0]); p.chmod(previous[1])
    # A preflight conflict must NOT trigger rollback over somebody else's edit.
    for rel, previous in snapshots.items():
        p=safe(repo/rel)
        if (p.read_bytes() if p.exists() else None) != (previous[0] if previous else None):
            raise ValueError('Destination changed during preflight: '+str(rel))
    try:
        for rel, content in modified.items():
            p=safe(repo/rel); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(content)
        subprocess.run([sys.executable,str(repo/ROOT/'build_installer.py')],cwd=repo,check=True)
        subprocess.run([sys.executable,str(repo/ROOT/'build_installer.py'),'--check'],cwd=repo,check=True)
        subprocess.run(['bash',str(repo/GENERATED),'--self-test'],cwd=repo,check=True)
        hashes={p.as_posix():hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in targets if p!=MANIFEST}
        (repo/MANIFEST).write_text(json.dumps({'upgrade':UPGRADE,'version':VERSION,'files':hashes},indent=2)+'\n')
    except BaseException:
        for rel, previous in snapshots.items():
            p=safe(repo/rel)
            if previous:
                p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(previous[0]); p.chmod(previous[1])
            elif p.exists():
                p.unlink()
        raise
    return {**result,'backup':str(backup)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args(argv)
    try:
        print(json.dumps(apply(args.repo,dry_run=args.dry_run),ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
