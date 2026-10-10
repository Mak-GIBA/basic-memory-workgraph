#!/usr/bin/env python3
"""Stage a small research-first workflow upgrade, test, and rebuild both installers.

Default is a read-only plan. --apply touches maintained files only, never invokes
models, installs dependencies, changes Git refs, settings, or existing user docs.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parent
D = Path('tools/design-research')
U = Path('tools/speckit-upstream')
MANIFEST = Path('tools/upstream-research-light-upgrade.json')
ID = 'upstream-research-workstreams-v2'
VERSION_D, VERSION_U = '2.2.2', '2.0.3'
BASE = 'd3f46e0d591b45cb2423317030a489b91566e891'
sys.dont_write_bytecode = True
UPSTREAM_BASES = {
 U/'workbench/trace.py': '05fef0869c3ef9e080a6a2ef3a1755ee314a5b34',
 U/'workbench/workflow.py': 'a85e82c5b5237e1bc043837869a1f4a1c182e1c3',
 U/'workbench/command_skills.py': 'df30cc84a6a1de6d1e3cdeaf1119d6971efb175f',
 U/'assets/templates/design.md': '4f40ad782da178cc33c36f5dac14123797e254ac',
 U/'assets/templates/requirements.md': '2fad161d19d0b8697b23498cc0f22e19ee3182d8',
 U/'assets/templates/verification.md': '3e166199c40edf1f845b8480058817642433cbbf',
 U/'tests/test_compact.py': '096437822a794908b1b72a5c31b1939cc072c352',
 U/'tests/test_workbench.py': '515cf01fa4421d466daf8b45ba945fdc50743c45',
}
GENERATED = (Path('install_design_research.sh'), Path('install_speckit_upstream.sh'))


def safe(path):
    path = Path(os.path.abspath(Path(path).expanduser()))
    for node in (path, *path.parents):
        if node.is_symlink():
            raise ValueError('Refusing symlink path: ' + str(node))
    return path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Changed or ambiguous integration anchor: ' + before[:90])
    return source.replace(before, after, 1)


def function_patch(source, function, before, after):
    nodes = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == function]
    if len(nodes) != 1:
        raise ValueError('Expected one function: ' + function)
    node = nodes[0]; lines = source.splitlines(True)
    lines[node.lineno-1:node.end_lineno] = [once(''.join(lines[node.lineno-1:node.end_lineno]), before, after)]
    return ''.join(lines)


def function_patch_method(source, class_name, method_name, before, after):
    classes = [n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == class_name]
    methods = [n for c in classes for n in c.body if isinstance(n, ast.FunctionDef) and n.name == method_name]
    if len(methods) != 1:
        raise ValueError('Expected one class method: '+class_name+'.'+method_name)
    node=methods[0];lines=source.splitlines(True)
    lines[node.lineno-1:node.end_lineno]=[once(''.join(lines[node.lineno-1:node.end_lineno]),before,after)]
    return ''.join(lines)


def append(source, text, name=ID):
    begin, end = '<!-- '+name+':begin -->', '<!-- '+name+':end -->'
    if begin in source or end in source:
        raise ValueError('Upgrade block already exists without matching manifest: ' + name)
    return source.rstrip() + '\n\n' + begin + '\n' + text.strip() + '\n' + end + '\n'


def patch_harness(source):
    source = once(source, 'HERE = Path(__file__).resolve().parent',
        'from readable_report import instructions as readable_instructions, require_contract\n'
        'from reassessment import snapshot_requirements\n\nHERE = Path(__file__).resolve().parent')
    source = once(source,
        'Comparison-only research normally includes 2-3 distinct candidates and a current/minimal baseline.',
        'Legacy comparison may use 2-3 candidates. Reader-friendly comparison uses the frozen target_methods (default five including a current/minimal baseline), with a substantive exception when fewer candidates are appropriate.')
    source = function_patch(source, 'role_prompt', '    inputs["workspace"] = ',
        '    for key in ("reassessment_context", "requirements_context"):\n'
        '        inputs[key] = state.get(key)\n    inputs["workspace"] = ')
    source = function_patch(source, 'role_prompt', 'return BASE + role_instructions(role, state)',
        'return BASE + readable_instructions(role, state) + role_instructions(role, state)')
    source = function_patch(source, 'validate_review', '        state["dossier"] = dossier',
        '        require_contract(dossier, state, workspace)\n        state["dossier"] = dossier')
    source = function_patch(source, 'config_from', '"reference_urls": args.reference_url,',
        '"reference_urls": args.reference_url,\n'
        '            "reader_friendly": getattr(args, "reader_friendly", False),\n'
        '            "requested_mode": "reassess" if getattr(args, "reassessment_context", None) else args.mode,')
    source = function_patch(source, 'parser', '        if mode == "research":',
        '        sub.add_argument("--reader-friendly", action="store_true",\n'
        '                         help="Require progressive explanations and diagrams")\n'
        '        if mode == "research":\n'
        '            sub.add_argument("--requirements", help="Freeze canonical project-relative requirements")')
    source = function_patch(source, 'execution', '            state["original_source"] = state["expected_source"]',
        '            state["original_source"] = state["expected_source"]\n'
        '            if getattr(args, "reassessment_context", None):\n'
        '                state["reassessment_context"] = args.reassessment_context')
    source = function_patch(source, 'execution', '                state["test_env_hash"] = ',
        '                requirements = snapshot_requirements(args, project, run_dir, workspace)\n'
        '                if requirements:\n'
        '                    state["requirements_context"] = requirements\n'
        '                state["test_env_hash"] = ')
    source = function_patch(source, 'gate_reasons', '    return reasons',
        '    from readable_report import quality_issues as reader_issues\n'
        '    from reassessment import quality_issues as reassess_issues\n'
        '    reasons.extend(reader_issues(state.get("dossier") or {}, state))\n'
        '    reasons.extend(reassess_issues(state.get("dossier") or {}, state))\n'
        '    return reasons')
    source = re.sub(r'(?m)^VERSION = "[0-9.]+"$', 'VERSION = "'+VERSION_D+'"', source)
    compile(source, 'harness.py', 'exec')
    return source


def patch_workstream_harness(source):
    source = once(source, 'from reassessment import snapshot_requirements',
        'from reassessment import snapshot_requirements\n'
        'from research_workstreams import snapshot_task, role_instructions as workstream_instructions')
    source = function_patch(source, 'role_prompt',
        'for key in ("reassessment_context", "requirements_context"):',
        'for key in ("reassessment_context", "requirements_context", "workstream_context"):')
    source = function_patch(source, 'role_prompt', 'return BASE + readable_instructions(role, state)',
        'return BASE + workstream_instructions(role, state) + readable_instructions(role, state)')
    source = function_patch(source, 'parser',
        '            sub.add_argument("--requirements", help="Freeze canonical project-relative requirements")',
        '            sub.add_argument("--requirements", help="Freeze canonical project-relative requirements")\n'
        '            sub.add_argument("--workstream-plan", help="Frozen requirements-to-core-logic plan")\n'
        '            sub.add_argument("--workstream-id", help="One core-logic work package to investigate")')
    source = function_patch(source, 'execution',
        '                    state["requirements_context"] = requirements',
        '                    state["requirements_context"] = requirements\n'
        '                workstream = snapshot_task(args, project, run_dir, workspace)\n'
        '                if workstream:\n'
        '                    state["workstream_context"] = workstream')
    compile(source, 'harness.py', 'exec')
    return source


def patch_report(source):
    source = once(source, 'from layout import MARKER, compact, record_path',
        'from layout import MARKER, compact, record_path\nfrom readable_report import sections as reader_sections')
    source = function_patch(source, 'publish', "    lines += ['## 調査・比較・検証',", 
        "    lines += reader_sections(state)\n    lines += ['## 調査・比較・検証',")
    source = function_patch(source, 'publish_legacy', '        report += ["", "## Candidate Comparison", "",',
        '        report += reader_sections(state)\n        report += ["", "## Candidate Comparison", "",')
    compile(source, 'report.py', 'exec')
    return source


def prior_module():
    spec = importlib.util.spec_from_file_location('prior_report_upgrade', PACKAGE/'previous_report_upgrade/apply_upgrade.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def overlay_files():
    result = {}
    for path in sorted((PACKAGE/'overlay').rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink overlay')
        if '__pycache__' not in path.parts and path.suffix != '.pyc' and path.is_file():
            result[path.relative_to(PACKAGE/'overlay')] = path.read_bytes()
    return result


def package_digest():
    # Tests and all embedded source matter; logs and examples are not executable payload.
    records = {}
    for path in PACKAGE.rglob('*'):
        rel = path.relative_to(PACKAGE)
        if path.is_symlink():
            raise ValueError('Symlink package')
        if path.is_file() and '__pycache__' not in rel.parts and path.suffix != '.pyc' and rel.parts[0] not in {'validation','examples'}:
            records[str(rel)] = sha(path.read_bytes())
    return sha(json.dumps(records, sort_keys=True).encode())


def already_applied(repo):
    p = safe(repo/MANIFEST)
    if not p.exists():
        return False
    value = json.loads(p.read_text('utf-8'))
    if value.get('upgrade') != ID or value.get('package_digest') != package_digest() or not value.get('files'):
        raise ValueError('Different or unrecognized upgrade already recorded; reconcile explicitly')
    for name, digest in value['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Unsafe manifest')
        path = safe(repo/name)
        if not path.is_file() or sha(path.read_bytes()) != digest:
            raise ValueError('Local edits after upgrade: ' + name)
    return True


def plan(repo, *, verify_base=True):
    repo = safe(repo)
    if not repo.is_dir():
        raise ValueError('Repository does not exist')
    previous = prior_module()
    # Support exact main and the earlier fully applied report package, not unverified merges.
    has_previous = (repo/D/'skill/scripts/proposal_report.py').is_file()
    if has_previous:
        if not previous._verify_previous_upgrade(repo):
            raise ValueError('Existing report extension is unversioned; merge explicitly')
        changes = {}
    else:
        changes = previous.plan(repo, verify_base=verify_base)
        for source in previous.overlay_files():
            rel = source.relative_to(previous.PACKAGE/'overlay')
            target = safe(repo/rel)
            if target.exists() and target.read_bytes() != changes[rel]:
                older = previous.PACKAGE/'previous-v5'/rel
                owned_template = rel == D/'skill/templates/report.md' and blob(target.read_bytes()) == 'a1c292f7477304cdb65d1c5cbb47b6ac43225566'
                if not owned_template and (not older.is_file() or target.read_bytes() != older.read_bytes()):
                    raise ValueError('Custom earlier extension would be overwritten: '+str(rel))
    def get(rel):
        return changes[rel].decode('utf-8') if rel in changes else safe(repo/rel).read_text('utf-8')
    def put(rel, text):
        changes[rel] = text.encode('utf-8')
    if verify_base:
        for rel, expected in UPSTREAM_BASES.items():
            if blob(safe(repo/rel).read_bytes()) != expected:
                raise ValueError('Changed upstream base; preserve local edits and merge explicitly: '+str(rel))
    for rel, raw in overlay_files().items():
        target = safe(repo/rel)
        if target.exists() and rel not in UPSTREAM_BASES and target.read_bytes() != raw:
            raise ValueError('Unmanaged overlay file would be overwritten: '+str(rel))
        changes[rel] = raw
    # Same SVG bytes, without relying on Python 3.12's relaxed f-string grammar.
    rel = D/'skill/scripts/proposal_report.py'
    diagram = get(rel)
    old_fstring = "            out.append(f'<text x=\"{lx}\" y=\"{ly+16*j}\" font-size=\"12\" text-anchor=\"{'end' if feedback else 'middle'}\">{html.escape(label)}</text>')"
    new_fstring = "            anchor = 'end' if feedback else 'middle'\n            out.append(f'<text x=\"{lx}\" y=\"{ly+16*j}\" font-size=\"12\" text-anchor=\"{anchor}\">{html.escape(label)}</text>')"
    if old_fstring in diagram:
        put(rel, once(diagram, old_fstring, new_fstring))
    put(D/'skill/scripts/harness.py', patch_workstream_harness(patch_harness(get(D/'skill/scripts/harness.py'))))
    put(D/'skill/scripts/report.py', patch_report(get(D/'skill/scripts/report.py')))
    # One implementation shipped in both independent installers; no cross-install import.
    changes[U/'workbench/research_workstreams.py'] = changes[D/'skill/scripts/research_workstreams.py']
    rel = D/'skill/scripts/gan-harness.sh'
    put(rel, once(get(rel), 'exec "${PYTHON_BIN:-python3}" -B "$DR_GAN_SCRIPT_DIR/harness.py" "$@"',
        'if [[ "${1:-}" == "reassess" ]]; then\n'
        '  shift\n  exec "${PYTHON_BIN:-python3}" -B "$DR_GAN_SCRIPT_DIR/reassessment.py" "$@"\n'
        'fi\n'
        'if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then\n'
        '  printf "%s\\n" "Additional mode: reassess --prior-run <state.json> --slug <new-topic> --brief <reason>"\n'
        'fi\nexec "${PYTHON_BIN:-python3}" -B "$DR_GAN_SCRIPT_DIR/harness.py" "$@"'))
    for rel in (D/'skill/SKILL.md', D/'skill/references/roles.md', D/'skill/references/protocol.md'):
        text = append(get(rel), (PACKAGE/'integration/research.md').read_text('utf-8'))
        if rel.name == 'SKILL.md':
            text = text.replace('gan-harness.sh research --report-profile', 'gan-harness.sh research --reader-friendly --report-profile')
            for mode in ('audit', 'run'):
                text = text.replace('gan-harness.sh '+mode+' --project', 'gan-harness.sh '+mode+' --reader-friendly --project')
        put(rel, text)
    text = (PACKAGE/'integration/upstream.md').read_text('utf-8')
    skill = get(U/'assets/skill/SKILL.md')
    skill = skill.replace('判断を左右する技術的な不確実性があれば、Design Researchの使用理由とresearch/auditを明示し、実際のSkillを読み、gan-harness.shを実行する。',
        '新規/変更の実現方式を設計する場合はDesign Researchを必ず使用し、実際のSkillを読んでresearch/reassessを実行する。As-Isの診断は必要に応じてauditを使う。')
    put(U/'assets/skill/SKILL.md', append(skill, text))
    put(U/'assets/prompts/common.md', append(get(U/'assets/prompts/common.md'), text.replace('@ASSETS@/', '共通資材の')))
    rel = U/'workbench/trace.py'
    put(rel, function_patch(get(rel), 'inspect', "    errors=sum(x['severity']=='error' for x in findings)",
        "    from .design_quality import inspect_design_documents\n"
        "    findings.extend(inspect_design_documents(root, valid, phase, config['docs_dir']+'/requirements.md' if compact(config) else None))\n"
        "    errors=sum(x['severity']=='error' for x in findings)"))
    rel = U/'workbench/workflow.py'
    text = function_patch(get(rel), 'snapshot', '    paths=set(documents(root,c))',
        '    paths=set(documents(root,c))\n    from .design_quality import dependency_files\n'
        '    paths.update(dependency_files(root, tuple(paths)))')
    text = function_patch(text, 'flow', "    text+=(ROOT/'assets/prompts/common.md').read_text(encoding='utf-8')+'\\n'",
        "    text+=(ROOT/'assets/prompts/common.md').read_text(encoding='utf-8')+'\\n'\n"
        "    text+='\\n必須の設計手順: '+str(ROOT/'assets/references/RESEARCH_FIRST.md')+'\\n'\n")
    put(rel, text)
    rel = U/'workbench/command_skills.py'
    put(rel, function_patch(get(rel), 'render_skill', '    return body',
        "    body += '\\n方式設計前に要件から研究が必要なコアロジックを切り出し、各テーマでdesign-researchを実行して統合する。全体一括研究や画面/API単位の機械的分割はしない。詳しくは '+str(assets/'references/RESEARCH_FIRST.md')+' を読む。画面例には実在するUI/UX Skillを使う。\\n'\n"
        '    return body'))
    additions = {
      'requirements.md': '''\n## ストーリー・懸念とユースケース

TBD: 既存ストーリーを再利用し、誰の何の不安が未解決かを確認する。回答済みの内容は再質問しない。
TBD: 利用者、きっかけ、前提、主要手順、状態のフィードバック、成功条件、失敗/取消/中断復帰を具体例で記述する。
TBD: 利用フロー/状態遷移図を示し、キャプションと図の読み方を付ける。

| ストーリーID | 懸念・回答・未決定 | ユースケースID | 要件ID | 検証方法 |
|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD |

「使いやすい」は仮説とし、完了成功率・迷い・やり直し等の評価方法を決める。未回答を合意にしない。
''',
      'verification.md': '''\n## 初見向けの検証の読み方

TBD: 要件→テスト入力/操作→観測→判定の流れを図で示し、キャプションと図の読み方を付ける。
TBD: 代表ユースケースの成功/失敗/復帰を具体例で説明する。研究の仮説、前回測定、今回の実測、未実行を分ける。
TBD: UIの見栄え、実際の操作完了、人による使用感の確認を区別する。
'''}
    for name, addition in additions.items():
        rel = U/'assets/templates'/name
        text = get(rel); before, sep, after = text.rpartition('<!-- /upstream:section -->')
        if not sep:
            raise ValueError('Expected scoped template: '+name)
        put(rel, before+addition+'\n'+sep+after)
    # Existing scoping tests deliberately retain legacy fixture semantics. The new
    # research-first contract is tested separately in tests/test_research_first.py.
    rel = U/'tests/test_compact.py'
    put(rel, function_patch_method(get(rel), 'CompactTests', 'rows',
        "        return rows",
        "        # Legacy approval/scoping fixture; see test_research_first.py for the new contract.\n"
        "        design=self.root/'docs/upstream/design.md'\n"
        "        design.write_text(design.read_text().replace('<!-- upstream-design-contract:v1 -->', '<!-- Legacy scoping fixture -->').replace('<!-- upstream-design-contract:v2 -->', '<!-- Legacy scoping fixture -->'))\n"
        "        return rows"))
    # Legacy documents remain usable, with an explicit design-contract warning.
    rel = U/'tests/test_workbench.py'
    put(rel, function_patch_method(get(rel), 'TraceTests', 'test_complete_fixture_ready',
        "        self.write_records(demo_records());self.assertEqual(inspect(self.root,'ready')['verdict'],'STRUCTURE_OK')",
        "        self.write_records(demo_records())\n"
        "        result=inspect(self.root,'ready')\n"
        "        self.assertEqual(result['verdict'],'STRUCTURE_OK_WITH_WARNINGS')\n"
        "        self.assertEqual({f['code'] for f in result['findings'] if f['severity']=='warning'}, {'LEGACY_DESIGN_CONTRACT'})\n"
        "        self.assertFalse([f for f in result['findings'] if f['severity']=='error'])"))
    for rel, pattern in ((D/'build_installer.py', r'("version":\s*")[0-9.]+(")'),
                          (D/'install_design_research.py', r'(VERSION\s*=\s*")[0-9.]+(")')):
        text, count = re.subn(pattern, lambda m: m[1]+VERSION_D+m[2], get(rel))
        if count != 1:
            raise ValueError('Design Research version anchor changed')
        put(rel, text)
    rel = D/'install_design_research.py'
    put(rel, once(get(rel),
        '"scripts/evidence.py", "scripts/report.py", "references/evidence-format.md"',
        '"scripts/evidence.py", "scripts/report.py", "references/evidence-format.md",\n'
        '    "scripts/reassessment.py", "scripts/readable_report.py", "scripts/research_workstreams.py"'))
    for rel in (U/'build_single.py', U/'workbench/__init__.py'):
        text = get(rel)
        if '2.0.1' not in text:
            raise ValueError('Unexpected upstream version in '+str(rel))
        put(rel, text.replace('2.0.1', VERSION_U))
    for rel, content in changes.items():
        safe(repo/rel)
        if rel.suffix == '.py':
            compile(content, str(rel), 'exec')
    return {r:b for r,b in changes.items() if not (repo/r).is_file() or (repo/r).read_bytes()!=b}


def copy_checkout(repo, stage):
    # Only this kit's trusted sources/tests are needed to rebuild. Never copy user data/.git.
    for name in ('tools', 'tests', 'docs'):
        source = safe(repo/name)
        if not source.is_dir():
            raise ValueError('Incomplete checkout: '+name)
        for p in source.rglob('*'):
            if p.is_symlink():
                raise ValueError('Symlink checkout assets are not supported: '+str(p))
        shutil.copytree(source, stage/name, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for source in repo.glob('*.sh'):
        shutil.copy2(safe(source), stage/source.name)
    if (repo/'README.md').is_file():
        shutil.copy2(safe(repo/'README.md'), stage/'README.md')


def check_stage(stage, logdir):
    commands = [
      [sys.executable, str(PACKAGE/'run_tests.py'), '--source-root', str(stage)],
      [sys.executable, str(D/'build_installer.py')],
      [sys.executable, str(D/'build_installer.py'), '--check'],
      [sys.executable, str(U/'build_single.py'), 'install_speckit_upstream.sh'],
      ['bash','-n','install_design_research.sh'], ['bash','-n','install_speckit_upstream.sh'],
      ['bash','install_design_research.sh','--self-test'],
      ['bash','install_speckit_upstream.sh','--self-test'],
      [sys.executable,'-m','unittest','discover','-s','tests','-p','test_*design_research*.py','-v'],
      [sys.executable,'-m','unittest','discover','-s','tests/design_research_method_report','-v'],
    ]
    # Builds/self-tests work with isolated HOME, not the operator's installed skills/settings.
    home = logdir/'isolated-home'; home.mkdir()
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE':'1', 'HOME':str(home), 'CODEX_HOME':str(home/'.codex'), 'PYTHON_BIN':sys.executable}
    for i, command in enumerate(commands, 1):
        result = subprocess.run(command, cwd=stage, env=env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=300)
        (logdir/f'{i:02d}.log').write_text('$ '+' '.join(command)+'\n'+result.stdout, 'utf-8')
        if result.returncode:
            raise ValueError(f'Staged verification failed; original untouched. Read {logdir}/{i:02d}.log')
    return commands


def source_snapshot(repo):
    result = {}
    for rel in (D, U, Path('tests')):
        root = safe(repo/rel)
        if not root.is_dir():
            raise ValueError('Incomplete checkout: '+str(rel))
        for path in sorted(root.rglob('*')):
            safe(path)
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                result[str(path.relative_to(repo))] = sha(path.read_bytes())
    for rel in GENERATED:
        path=safe(repo/rel)
        result[str(rel)] = sha(path.read_bytes()) if path.is_file() else None
    return result


def apply(repo, *, execute=False):
    repo = safe(repo)
    if already_applied(repo):
        return {'action':'skip','reason':'same package and file hashes already applied'}
    source_before = source_snapshot(repo)
    changes = plan(repo)
    if source_snapshot(repo) != source_before:
        raise ValueError('Source changed during planning; retry without overwriting edits')
    result = {'action':'upgrade' if execute else 'plan', 'base':BASE,
              'versions':{'design-research':VERSION_D,'upstream':VERSION_U},
              'files':[str(p) for p in changes], 'rebuild':[str(p) for p in GENERATED],
              'network':False,'model_calls':False,'git_writes':False}
    if not execute:
        return result
    # Lock guards another invocation of this updater; it is not a global repository lock.
    lock = safe(repo/'.upstream-research-light.lock')
    lock.mkdir(mode=0o700)
    try:
        records = {p: (safe(repo/p).read_bytes(), safe(repo/p).stat().st_mode & 0o777)
                   if (repo/p).exists() else None for p in (*changes, *GENERATED, MANIFEST)}
        backup = Path(tempfile.mkdtemp(prefix='upstream-research-light-backup-'))
        for rel, record in records.items():
            if record is not None:
                p = backup/'original'/rel; p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(record[0]); p.chmod(record[1])
        logs = backup/'verification'; logs.mkdir()
        with tempfile.TemporaryDirectory(prefix='upstream-research-stage-') as temp:
            stage = Path(temp)
            copy_checkout(repo, stage)
            for rel, content in changes.items():
                p=stage/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
            commands = check_stage(stage, logs)
            for rel in GENERATED:
                changes[rel] = (stage/rel).read_bytes()
        # Publish the exact tested bytes, after confirming the working copy did not change.
        if source_snapshot(repo) != source_before:
            raise ValueError('Source changed while staging; no upgrade files were published')
        for rel, record in records.items():
            p=safe(repo/rel)
            if (p.read_bytes() if p.exists() else None) != (record[0] if record else None):
                raise ValueError('Destination changed while staging; no writes performed: '+str(rel))
        manifest={'upgrade':ID,'package_digest':package_digest(),'base_commit':BASE,
                  'files':{str(p):sha(b) for p,b in changes.items()},
                  'scope':'Local structural tests/builds, not scientific or live Codex validation'}
        changes[MANIFEST] = (json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
        written=[]
        try:
            for rel, content in changes.items():
                target=safe(repo/rel);target.parent.mkdir(parents=True,exist_ok=True)
                fd,tmp=tempfile.mkstemp(prefix='.upgrade-',dir=target.parent)
                try:
                    with os.fdopen(fd,'wb') as f:f.write(content)
                    os.chmod(tmp, records[rel][1] if records.get(rel) else (0o755 if rel.suffix=='.sh' else 0o644))
                    os.replace(tmp,target);written.append(rel)
                finally:
                    if os.path.exists(tmp):os.unlink(tmp)
        except BaseException:
            for rel in reversed(written):
                target=safe(repo/rel);old=records[rel]
                # Preserve an intervening human edit rather than rolling back over it.
                if target.read_bytes()!=changes[rel]:
                    continue
                if old:
                    target.write_bytes(old[0]);target.chmod(old[1])
                else:
                    target.unlink()
            raise
        return {**result,'backup':str(backup),'verification_logs':str(logs),'checks':len(commands)}
    finally:
        lock.rmdir()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',required=True,type=Path)
    modes=p.add_mutually_exclusive_group()
    modes.add_argument('--apply',action='store_true')
    modes.add_argument('--dry-run',action='store_true')
    args=p.parse_args()
    if sys.version_info < (3,11):p.error('Python 3.11+ is required')
    try:
        print(json.dumps(apply(args.repo,execute=args.apply),ensure_ascii=False,indent=2))
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 2
    return 0


if __name__=='__main__':
    raise SystemExit(main())
