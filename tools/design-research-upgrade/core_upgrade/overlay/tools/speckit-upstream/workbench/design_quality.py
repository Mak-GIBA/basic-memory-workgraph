"""Local research-to-design consistency checks; not authorization or semantic proof.

New/edited designs opt into a versioned contract. Legacy documents remain readable
and receive a warning instead of silently migrating approved source material.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re

MARKER = "<!-- upstream-design-contract:v1 -->"
WORKSTREAM_MARKER = "<!-- upstream-design-contract:v2 -->"


def has_contract(text):
    return MARKER in text or WORKSTREAM_MARKER in text
BLOCK = re.compile(r"(?ms)^```design-research[ \t]*\n(.*?)^```[ \t]*$")
LIMIT = 5 * 1024 * 1024


def local_file(root, name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError("Use a project-relative path, not a URL")
    rel = Path(name)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError("A dependency must stay inside the project")
    root = Path(os.path.abspath(root))
    path = root / rel
    for node in (path, *path.parents):
        if node.is_symlink():
            raise ValueError("Symlink dependencies are not supported")
    if not path.is_file() or path.stat().st_size > LIMIT:
        raise ValueError("Missing/oversized design dependency: " + name)
    return path


def read(root, name):
    raw = local_file(root, name).read_bytes()
    if not raw or len(raw) > LIMIT:
        raise ValueError("Empty/oversized design dependency: " + name)
    raw.decode('utf-8')
    return raw


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bindings(text):
    matches = BLOCK.findall(text)
    if len(matches) != 1:
        raise ValueError("design.md needs exactly one design-research JSON binding")
    data = json.loads(matches[0])
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] not in {1, 2}:
        raise ValueError("Unsupported design-research binding schema")
    return data


def validate_binding(root, data, design_ids, canonical_requirements=None):
    deps = set()
    def load(name):
        path = local_file(root, name)
        deps.add(path)
        return read(root, name)
    plan = None
    if data.get('schema_version') == 2:
        try:
            from .research_workstreams import load_plan
        except ImportError:  # direct-module unit tests only
            from research_workstreams import load_plan
        ref = data.get('workstream_plan')
        if not isinstance(ref, dict):
            raise ValueError('Bind the requirements-to-core-logic workstream plan')
        raw = load(ref.get('path'))
        if sha(raw) != ref.get('sha256'):
            raise ValueError('Workstream plan binding is stale')
        plan = load_plan(Path(root), ref['path'])
        if canonical_requirements and plan['requirements']['path'] != canonical_requirements:
            raise ValueError('Workstream plan uses another requirements document')
        load(plan['requirements']['path'])
        if any(r['disposition'] == 'clarify' for r in plan['requirements']['items']):
            raise ValueError('Resolve outstanding concerns before finalizing design')
    runs = data.get('runs')
    if not isinstance(runs, list) or (not runs and plan is None) or len(runs) > 12:
        raise ValueError("Bind at least one completed research run to design decisions")
    covered = set()
    covered_tasks = set()
    for binding in runs:
        if not isinstance(binding, dict):
            raise ValueError("Research binding must be an object")
        raw = load(binding.get('state'))
        state = json.loads(raw)
        if not isinstance(state, dict) or state.get('schema_version') != 1:
            raise ValueError("Invalid research state")
        config = state.get('config', {})
        if not isinstance(config, dict) or config.get('mode') != 'research' or state.get('status') != 'research_complete':
            raise ValueError("Design needs a completed research/reassess run, not a plan or application-fix run")
        state_path = Path(binding['state'])
        if (state_path.name != 'state.json' or state_path.parent.name != state.get('run_id')
                or state_path.parent.parent.name != 'runs'
                or state_path.parents[2].parent != Path('docs/design-research')):
            raise ValueError("Research state must identify an exact docs/design-research topic/run")
        report = binding.get('report')
        expected = {str(state_path.parent / 'reports/report.md'),
                    str(state_path.parent / 'reports/design-research.md')}
        if report not in expected:
            raise ValueError("Link the same run's archived report, not its mutable topic-level report")
        load(report)
        requirements = state.get('requirements_context')
        if not isinstance(requirements, dict):
            raise ValueError("Rerun design-research with --requirements for the current canonical requirements")
        if canonical_requirements and requirements.get('project_path') != canonical_requirements:
            raise ValueError("Research input is not this project's canonical requirements.md")
        original = load(requirements.get('project_path'))
        snapshot_rel = state_path.parents[2] / str(requirements.get('snapshot', ''))
        frozen = load(snapshot_rel.as_posix())
        if not original or sha(original) != requirements.get('sha256') or sha(frozen) != requirements.get('sha256'):
            raise ValueError("Research is stale: current requirements differ from the frozen research input")
        # Pin exact local outputs in the reviewed design. This is integrity, not authenticity.
        for key, content in (('state_sha256', raw), ('report_sha256', read(root, report))):
            if binding.get(key) != sha(content):
                raise ValueError("Research binding hash is absent or stale: " + key)
        dossier = state.get('dossier', {})
        if not isinstance(dossier, dict):
            raise ValueError('Research dossier must be an object')
        candidates = {r['id'] for r in dossier.get('candidates', [])
                      if isinstance(r, dict) and isinstance(r.get('id'), str)}
        if plan is not None:
            task_id = binding.get('workstream_id')
            tasks = {t['id']: t for t in plan['workstreams']}
            context = state.get('workstream_context', {})
            if not isinstance(task_id, str) or task_id not in tasks or task_id in covered_tasks:
                raise ValueError('Bind exactly one selected run per research work package')
            if (not isinstance(context, dict) or context.get('workstream_id') != task_id
                    or context.get('plan_sha256') != data['workstream_plan']['sha256']
                    or context.get('plan_path') != data['workstream_plan']['path']
                    or context.get('task') != tasks[task_id]):
                raise ValueError('Research did not execute the selected frozen core-logic task')
            task_snapshot = state_path.parents[2] / str(context.get('snapshot', ''))
            if sha(load(task_snapshot.as_posix())) != context.get('plan_sha256'):
                raise ValueError('Frozen workstream plan snapshot is stale')
            covered_tasks.add(task_id)
        decisions = binding.get('decisions')
        if not isinstance(decisions, list) or not decisions:
            raise ValueError("Map research candidates to actual design IDs")
        run_designs = set()
        for row in decisions:
            if not isinstance(row, dict):
                raise ValueError("Decision mapping must be an object")
            did, cid = row.get('design_id'), row.get('candidate_id')
            if not isinstance(did, str) or did not in design_ids or did in run_designs or (plan is None and did in covered):
                raise ValueError("Decision mapping needs a unique existing design ID in this document")
            if not isinstance(cid, str) or cid not in candidates:
                raise ValueError("Decision mapping cites an unknown research candidate")
            if not isinstance(row.get('rationale'), str) or not row['rationale'].strip():
                raise ValueError("Explain how evidence and limitations support this design decision")
            covered.add(did)
            run_designs.add(did)
    if plan is not None:
        if covered_tasks != {t['id'] for t in plan['workstreams']}:
            raise ValueError('A required core-logic work package has no completed research')
        standard = data.get('standard_decisions', [])
        if not isinstance(standard, list):
            raise ValueError('standard_decisions must be a list')
        standard_reqs = {r['id'] for r in plan['requirements']['items'] if r['disposition'] == 'standard'}
        for row in standard:
            if not isinstance(row, dict):
                raise ValueError('Standard decision must be an object')
            did = row.get('design_id')
            reqs = row.get('requirement_ids')
            if not isinstance(did, str) or did not in design_ids or did in covered:
                raise ValueError('Standard decision needs a unique active design ID')
            if (not isinstance(reqs, list) or not reqs
                    or any(not isinstance(r, str) for r in reqs) or set(reqs) - standard_reqs):
                raise ValueError('Standard decision must map to standard-classified requirements')
            if not isinstance(row.get('reason'), str) or not row['reason'].strip():
                raise ValueError('Explain why existing evidence resolves this standard implementation')
            evidence = row.get('evidence')
            if not isinstance(evidence, list) or not evidence:
                raise ValueError('Standard implementation requires existing local evidence')
            for path in evidence:
                load(path)
            covered.add(did)
        integration = data.get('integration')
        if not isinstance(integration, dict) or integration.get('status') not in {'planned', 'verified', 'inconclusive'}:
            raise ValueError('Record the combined architecture verification status separately')
        for field in ('rationale', 'selected_combination', 'tradeoffs'):
            if not isinstance(integration.get(field), str) or not integration[field].strip():
                raise ValueError('Integration must explain combination and cross-task tradeoffs')
        checks = integration.get('verification_ids')
        if not isinstance(checks, list) or not checks or any(not isinstance(v, str) or not v.strip() for v in checks):
            raise ValueError('Integration needs corresponding verification IDs')
        artifacts = integration.get('artifacts', [])
        if not isinstance(artifacts, list):
            raise ValueError('Integration artifacts must be a list')
        if integration['status'] == 'verified' and not artifacts:
            raise ValueError('Individual successes are not combined execution evidence')
        for path in artifacts:
            deps.add(local_file(root, path))
    if covered != set(design_ids):
        raise ValueError("Every active design/decision needs a research mapping: " + ', '.join(sorted(set(design_ids)-covered)))
    ui = data.get('uiux')
    if not isinstance(ui, dict) or not isinstance(ui.get('applicable'), bool):
        raise ValueError("Record whether UI/UX screen design is applicable")
    if not isinstance(ui.get('reason'), str) or not ui['reason'].strip():
        raise ValueError("Explain UI/UX scope or why there are no screen examples")
    artifacts = ui.get('artifacts', [])
    if not isinstance(artifacts, list) or any(not isinstance(a, str) for a in artifacts):
        raise ValueError("UI/UX artifacts must be project-relative paths")
    if ui['applicable']:
        if not isinstance(ui.get('skill'), str) or not ui['skill'].strip():
            raise ValueError("Screen examples require the actual UI/UX skill name")
        if not artifacts or not isinstance(ui.get('review_notes'), str) or not ui['review_notes'].strip():
            raise ValueError("Screen examples need artifacts and scope-specific review notes")
        for name in artifacts:
            deps.add(local_file(root, name))  # may be PNG, not text
    elif artifacts:
        raise ValueError("Screen artifacts cannot bypass the UI/UX skill requirement")
    return deps


def document_issues(root, text, document_name="design.md"):
    errors = []
    # Deliberately limited structural checks. The reviewer checks diagram semantics.
    headings = ('目的|Purpose', '全体|Overall', 'コンポーネント|Component', '処理|Flow|Sequence', 'フレームワーク|Framework')
    for word in headings:
        if not re.search(r'(?im)^#{2,4}\s+.*(?:' + word + ')', text):
            errors.append("段階的な説明の見出しが必要: " + word)
    diagrams = re.findall(r'(?ms)^```mermaid[ \t]*\n(.+?)^```[ \t]*$', text)
    images = re.findall(r'!\[[^\]]+\]\(([^)]+)\)', text)
    local_images = []
    for image in images:
        try:
            absolute = Path(os.path.abspath(Path(root) / Path(document_name).parent / image))
            rel = absolute.relative_to(Path(os.path.abspath(root))).as_posix()
            local_file(root, rel)
            local_images.append(image)
        except ValueError:
            # Markdown image references are document-relative in ordinary use.
            errors.append("図ファイルの参照先が不正または見つかりません: " + image)
    if len(diagrams) + len(local_images) < 3:
        errors.append("全体・主要コンポーネント詳細・代表処理の3つの図を示してください")
    if not re.search(r'図(?:[0-9０-９]+)?の読み方|How to read', text, re.I):
        errors.append("図の読み方と矢印・境界の意味を説明してください")
    return errors


def inspect_design_documents(root, items, phase='draft', canonical_requirements=None):
    groups = {}
    for row in items:
        if row.get('type') in {'design', 'decision'} and row.get('status') != 'retired':
            groups.setdefault(row['_file'], set()).add(row['id'])
    output = []
    for name, ids in groups.items():
        def finding(message, legacy=False):
            output.append({'severity': 'error' if phase == 'ready' and not legacy else 'warning',
                           'code': 'LEGACY_DESIGN_CONTRACT' if legacy else 'DESIGN_RESEARCH_REQUIRED',
                           'item': name, 'message': message})
        try:
            text = read(root, name).decode('utf-8')
            if not has_contract(text):
                finding('既存文書は保持します。新たな方式設計・To-Be変更時に図解と研究実行の契約を追加してください。', True)
                continue
            data = bindings(text)
            if WORKSTREAM_MARKER in text and data.get('schema_version') != 2:
                raise ValueError('New workstream design marker requires a v2 binding')
            validate_binding(root, data, ids, canonical_requirements)
            if data.get('schema_version') == 2:
                known = {r['id'] for r in items if r.get('type') == 'verification' and r.get('status') != 'retired'}
                if set(data['integration']['verification_ids']) - known:
                    raise ValueError('Integration refers to an unknown active verification ID')
            for issue in document_issues(root, text, name):
                finding(issue)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            finding(str(exc))
    return output


def dependency_files(root, documents):
    """Bind research/requirements/screen bytes into upstream's existing gate snapshot."""
    paths = set()
    for doc in documents:
        text = doc.read_text('utf-8')
        if not has_contract(text):
            continue
        try:
            for image in re.findall(r'!\[[^\]]+\]\(([^)]+)\)', text):
                absolute = Path(os.path.abspath(doc.parent / image))
                rel = absolute.relative_to(Path(os.path.abspath(root))).as_posix()
                paths.add(local_file(root, rel))
            data = bindings(text)
            if data.get('schema_version') == 2:
                plan_ref = data['workstream_plan']['path']
                paths.add(local_file(root, plan_ref))
                plan = json.loads(read(root, plan_ref))
                paths.add(local_file(root, plan['requirements']['path']))
                for row in data.get('standard_decisions', []):
                    for name in row.get('evidence', []):
                        paths.add(local_file(root, name))
                for name in data.get('integration', {}).get('artifacts', []):
                    paths.add(local_file(root, name))
            for row in data.get('runs', []):
                for key in ('state', 'report'):
                    paths.add(local_file(root, row[key]))
                state = json.loads(read(root, row['state']))
                context = state.get('workstream_context')
                if context:
                    paths.add(local_file(root, context['plan_path']))
                    topic = Path(row['state']).parents[2]
                    paths.add(local_file(root, (topic/context['snapshot']).as_posix()))
                c = state.get('requirements_context', {})
                if c:
                    paths.add(local_file(root, c['project_path']))
                    topic = Path(row['state']).parents[2]
                    paths.add(local_file(root, (topic / c['snapshot']).as_posix()))
            for name in data.get('uiux', {}).get('artifacts', []):
                paths.add(local_file(root, name))
        except (ValueError, TypeError, KeyError, OSError):
            # Malformed bindings are reported by inspect; snapshot must not mask that result.
            continue
    return paths
