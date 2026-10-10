#!/usr/bin/env python3
"""Codex-facing discovery and dispatch. Prepare is read-only; run calls the real harness.

No model-generated file paths, latest-run guessing, shell interpolation or nested
harnesses. Existing runtime sandbox/locks/approval limits remain authoritative.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
LIMIT = 2 * 1024 * 1024
SLUG = re.compile(r'[a-z0-9][a-z0-9-]{0,63}\Z')
MODES = ('research', 'reassess', 'workstream', 'resume')


class SelectionNeeded(ValueError):
    def __init__(self, message, choices):
        super().__init__(message)
        self.choices = choices


def project_path(value):
    root = Path(os.path.abspath(Path(value).expanduser()))
    for part in (root, *root.parents):
        if part.is_symlink():
            raise ValueError('Symlink project roots are not supported')
    if not root.is_dir():
        raise ValueError('Project directory is missing')
    return root


def safe(root, name):
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
        raise ValueError('Expected a project file path')
    p = Path(name).expanduser()
    if '..' in p.parts:
        raise ValueError('Parent traversal is not allowed')
    p = Path(os.path.abspath(p if p.is_absolute() else root / p))
    if not p.is_relative_to(root):
        raise ValueError('Input must stay inside the selected project')
    if any(x in {'.git', '.ssh', '.aws'} or x.startswith('.env') for x in p.relative_to(root).parts):
        raise ValueError('Sensitive paths cannot be research input')
    for node in (p, *p.parents):
        if node.is_symlink():
            raise ValueError('Symlink inputs are not supported')
    return p


def read(root, name):
    p = safe(root, name)
    if not p.is_file() or not 0 < p.stat().st_size <= LIMIT:
        raise ValueError('Missing, empty or oversized input: ' + str(name))
    raw = p.read_bytes()
    if not 0 < len(raw) <= LIMIT:
        raise ValueError('Input changed size while reading')
    raw.decode('utf-8')
    return raw


def state_record(root, name):
    path = safe(root, name)
    rel = path.relative_to(root).parts
    if len(rel) != 6 or rel[:2] != ('docs', 'design-research') or rel[3] != 'runs' or rel[5] != 'state.json':
        raise ValueError('Use docs/design-research/<topic>/runs/<run-id>/state.json')
    raw = read(root, name)
    state = json.loads(raw)
    if not isinstance(state, dict) or state.get('schema_version') != 1:
        raise ValueError('Unsupported run state')
    cfg = state.get('config')
    if not isinstance(cfg, dict) or state.get('run_id') != rel[4] or cfg.get('slug') != rel[2]:
        raise ValueError('Run identity does not match its path')
    archive = path.parent/'reports/report.md'
    if not archive.is_file():
        archive = path.parent/'reports/design-research.md'
    report = None
    if archive.is_file():
        read(root, str(archive))
        report = archive.relative_to(root).as_posix()
    completed = (cfg.get('mode') == 'research' and state.get('status') == 'research_complete'
                 and isinstance(state.get('dossier'), dict) and bool(report))
    resumable = (state.get('status') in {'running', 'blocked', 'cancelled'} and state.get('phase') != 'fixing'
                 and cfg.get('project') == str(root))
    if state.get('phase') in {'experiments', 'checks'} and state.get('iteration', 1) >= cfg.get('max_iterations', 5):
        resumable = False
    return {'run_id': state['run_id'], 'topic': rel[2], 'mode': cfg.get('mode'),
            'requested_mode': cfg.get('requested_mode', cfg.get('mode')), 'status': state.get('status'),
            'brief': cfg.get('brief', ''), 'phase': state.get('phase'), 'state_path': path.relative_to(root).as_posix(),
            'report_path': report, 'reassess_eligible': completed, 'resume_eligible': resumable,
            'sha256': hashlib.sha256(raw).hexdigest(), '_state': state}


def public(row):
    return {k: v for k, v in row.items() if not k.startswith('_')}


def runs(root, topic=None):
    if topic is not None and not SLUG.fullmatch(topic):
        raise ValueError('Topic must be a safe slug')
    base = safe(root, 'docs/design-research')
    records, warnings = [], []
    count = 0
    for path in sorted(base.glob('*/runs/*/state.json')):
        count += 1
        if count > 500:
            warnings.append('Run scan limited to 500 records; use an exact --prior-run/--run-id')
            break
        if topic and path.parents[2].name != topic:
            continue
        try:
            records.append(state_record(root, str(path)))
        except (ValueError, OSError, TypeError, KeyError) as exc:
            warnings.append(f'{path.relative_to(root)}: {exc}')
    return records, warnings


def choose(rows, message):
    if not rows:
        raise ValueError(message + ': no eligible record; no run was started')
    if len(rows) != 1:
        raise SelectionNeeded(message, [public(row) for row in rows])
    return rows[0]


def fresh_slug(root, base):
    if not SLUG.fullmatch(base):
        raise ValueError('Slug must contain 1-64 lowercase letters, digits and hyphens')
    for i in range(1, 1000):
        suffix = '' if i == 1 else '-' + str(i)
        slug = base[:64-len(suffix)].rstrip('-') + suffix
        if not safe(root, 'docs/design-research/'+slug).exists():
            return slug
    raise ValueError('Cannot find a fresh topic name')


def requirements_path(root, supplied=None, prior=None):
    if supplied:
        p = safe(root, supplied); read(root, supplied)
        return p.relative_to(root).as_posix()
    possible = []
    config_path = safe(root, '.specify/workbench.json')
    if config_path.exists():
        cfg = json.loads(read(root, str(config_path)))
        if not isinstance(cfg, dict):
            raise ValueError('Invalid upstream project config')
        if isinstance(cfg.get('docs_dir'), str):
            possible.append(cfg['docs_dir'].rstrip('/')+'/requirements.md')
    if prior:
        bound = prior['_state'].get('requirements_context')
        if isinstance(bound, dict) and isinstance(bound.get('project_path'), str):
            possible.append(bound['project_path'])
    possible.append('docs/upstream/requirements.md')
    found = sorted({safe(root, n).relative_to(root).as_posix() for n in possible if safe(root, n).is_file()})
    if len(found) > 1:
        raise SelectionNeeded('Choose the canonical requirements; do not guess from modification time', found)
    if found:
        read(root, found[0])
        return found[0]
    if prior and prior['_state'].get('requirements_context'):
        raise ValueError('Previously bound requirements are missing; supply --requirements')
    return None  # Standalone algorithm research need not fabricate an upstream requirements file.


def pick_prior(root, args):
    if args.prior_run:
        row = state_record(root, args.prior_run)
        if not row['reassess_eligible']:
            raise ValueError('Reassessment needs completed research and its archived report')
        return row
    candidates, warnings = runs(root, args.topic)
    if warnings:
        raise SelectionNeeded('Run discovery was incomplete; select an exact --prior-run',
                              {'runs': [public(r) for r in candidates], 'warnings': warnings})
    return choose([r for r in candidates if r['reassess_eligible']], 'Choose the previous completed research')


def prepare(args):
    root = project_path(args.project)
    if os.environ.get('DR_GAN_CHILD'):
        raise ValueError('A harness child must not dispatch another harness')
    mode = args.mode
    if mode != 'workstream' and (args.plan or args.workstream_id or args.dependency_run):
        raise ValueError('Plan/workstream inputs require workstream mode')
    if mode != 'resume' and args.run_id:
        raise ValueError('--run-id belongs to resume; use --prior-run for reassess')
    prior = None
    bound = {}
    context = {}
    if mode == 'resume':
        rows, warnings = runs(root, args.topic)
        if args.run_id:
            # Search path IDs directly when the general listing was capped.
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', args.run_id):
                raise ValueError('Unsafe run ID')
            rows = [state_record(root, str(p)) for p in safe(root, 'docs/design-research').glob('*/runs/'+args.run_id+'/state.json')]
        elif warnings:
            raise SelectionNeeded('Run scan incomplete; select an exact --run-id', warnings)
        row = choose([r for r in rows if r['resume_eligible']], 'Choose an interrupted run; completed work uses reassess')
        if (args.brief or args.requirements or args.slug or args.plan or args.workstream_id or args.prior_run
                or args.allow_network or args.model or args.target_methods is not None
                or args.report_profile is not None or args.evaluation_purpose is not None):
            raise ValueError('Resume preserves frozen inputs; changed requirements need fresh research/reassess')
        argv = ['bash', str(HERE/'gan-harness.sh'), 'resume', row['run_id'], '--project', str(root)]
        bound[row['state_path']] = row['sha256']
        return {'status': 'ready', 'executed': False, 'project': str(root), 'mode': mode, 'argv': argv,
                'inputs_sha256': bound, 'selected_run': public(row), 'scope': 'Resume the same frozen run'}
    if mode == 'workstream':
        from research_workstreams import load_plan, digest
        plan_name = args.plan or '.specify/workbench/research-plan.json'
        plan_name = safe(root, plan_name).relative_to(root).as_posix()
        plan = load_plan(root, plan_name)
        if any(r['disposition'] == 'clarify' for r in plan['requirements']['items']):
            raise ValueError('Resolve pending requirement clarifications before execution')
        tasks = plan['workstreams']
        if args.workstream_id:
            tasks = [t for t in tasks if t['id'] == args.workstream_id]
        if len(tasks) != 1:
            raise SelectionNeeded('Select one core-logic workstream; no bulk execution',
                                  [{'id': t['id'], 'title': t['title'], 'depends_on': t['depends_on']} for t in tasks])
        task = tasks[0]
        plan_hash = digest(read(root, plan_name))
        rows, warnings = runs(root)
        dependency_rows = []
        choices = {}
        for item in args.dependency_run:
            key, sep, value = item.partition('=')
            if not sep or not key or not value or key in choices:
                raise ValueError('--dependency-run must be unique WORKSTREAM_ID=state.json')
            choices[key] = value
        if set(choices) - set(task['depends_on']):
            raise ValueError('Unexpected dependency-run ID')
        for key in task['depends_on']:
            candidates = [state_record(root, choices[key])] if key in choices else rows
            matched = [r for r in candidates if r['reassess_eligible']
                       and r['_state'].get('workstream_context', {}).get('workstream_id') == key
                       and r['_state'].get('workstream_context', {}).get('plan_sha256') == plan_hash]
            dep = choose(matched, 'Provide completed same-plan dependency '+key)
            dependency_rows.append(public(dep))
            bound[dep['state_path']] = dep['sha256']
            bound[dep['report_path']] = digest(read(root, dep['report_path']))
        mode = task['mode']
        if (args.brief or args.slug or args.requirements or args.prior_run or args.topic or args.target_methods is not None
                or args.report_profile is not None or args.evaluation_purpose is not None):
            raise ValueError('A workstream uses frozen plan inputs; edit and revalidate the plan instead')
        brief, slug, requirement, target = task['question'], task['slug'], plan['requirements']['path'], task.get('target_methods', 5)
        if safe(root, 'docs/design-research/'+slug).exists():
            raise ValueError('This task topic already exists; resume it or create a new reassessment plan/slug')
        if mode == 'reassess':
            prior = state_record(root, task['prior_run'])
            if not prior['reassess_eligible']:
                raise ValueError('Workstream prior research is not complete')
        bound[plan_name] = plan_hash
        context = {'workstream_id': task['id'], 'task': task, 'dependency_runs': dependency_rows,
                   'plan_path': plan_name, 'discovery_warnings': warnings,
                   'parallelism': 'Single dispatch only; preserve project locks. Waves are a plan, not executed jobs.'}
        extras = ['--workstream-plan', plan_name, '--workstream-id', task['id']]
        # Carry exact dependency paths into the child-visible brief without treating them as fresh measurements.
        if dependency_rows:
            brief += '\n先行研究（同一計画の完了済み履歴、今回の新規実測ではない）: '+json.dumps(dependency_rows, ensure_ascii=False)
    else:
        if not args.brief or not args.brief.strip():
            raise ValueError('Describe the research question or reason for reassessment')
        brief, target = args.brief.strip(), args.target_methods or 5
        if mode == 'reassess':
            prior = pick_prior(root, args)
            slug = args.slug or fresh_slug(root, prior['topic'][:52]+'-reassess')
        else:
            if args.prior_run or args.run_id:
                raise ValueError('Previous-run input belongs to reassess or resume')
            slug = args.slug or fresh_slug(root, 'research')
        if not SLUG.fullmatch(slug) or safe(root, 'docs/design-research/'+slug).exists():
            raise ValueError('Use a fresh safe topic slug')
        requirement = requirements_path(root, args.requirements, prior)
        extras = []
    profile = task.get('report_profile', 'comparison') if args.mode == 'workstream' else (args.report_profile or 'comparison')
    purpose = task.get('evaluation_purpose', 'auto') if args.mode == 'workstream' else (args.evaluation_purpose or 'auto')
    argv = ['bash', str(HERE/'gan-harness.sh'), mode, '--project', str(root), '--slug', slug, '--brief', brief,
            '--reader-friendly', '--report-profile', profile, '--evaluation-purpose', purpose, '--target-methods', str(target),
            '--max-iterations', str(args.max_iterations), '--phase-timeout', str(args.phase_timeout)]
    if requirement:
        argv += ['--requirements', requirement]
        bound[requirement] = hashlib.sha256(read(root, requirement)).hexdigest()
    if prior:
        from reassessment import load_previous
        load_previous(root, prior['state_path'], slug)
        argv += ['--prior-run', prior['state_path']]
        bound[prior['state_path']] = prior['sha256']
        bound[prior['report_path']] = hashlib.sha256(read(root, prior['report_path'])).hexdigest()
    argv += extras + (['--allow-network'] if args.allow_network else ['--offline'])
    if args.model:
        argv += ['--model', args.model]
    return {'status': 'ready', 'executed': False, 'project': str(root), 'mode': mode,
            'argv': argv, 'inputs_sha256': bound, 'selected_run': public(prior) if prior else None,
            'context': context, 'target_methods': target, 'report_profile': profile, 'evaluation_purpose': purpose,
            'scope': 'Isolated research/PoC and report only; no application changes, installs or human approval'}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='operation', required=True)
    q = sub.add_parser('runs', help='List real local runs; no execution')
    q.add_argument('--project', default='.')
    q.add_argument('--topic')
    q = sub.add_parser('workstreams', help='Validate and show execution waves; does not launch jobs')
    q.add_argument('--project', default='.')
    q.add_argument('--plan', default='.specify/workbench/research-plan.json')
    for op in ('prepare', 'run'):
        q = sub.add_parser(op, help='Resolve inputs only' if op == 'prepare' else 'Dispatch the real installed harness')
        q.add_argument('mode', choices=MODES)
        q.add_argument('--project', default='.')
        q.add_argument('--brief')
        q.add_argument('--topic')
        q.add_argument('--slug')
        q.add_argument('--prior-run')
        q.add_argument('--run-id')
        q.add_argument('--requirements')
        q.add_argument('--plan')
        q.add_argument('--workstream-id')
        q.add_argument('--dependency-run', action='append', default=[])
        q.add_argument('--target-methods', type=int, choices=range(3, 21))
        q.add_argument('--report-profile', choices=('comparison', 'proposed-method'))
        q.add_argument('--evaluation-purpose', choices=('auto', 'effectiveness', 'design', 'literature'))
        q.add_argument('--max-iterations', type=int, choices=range(1, 6), default=5)
        q.add_argument('--phase-timeout', type=int, default=1800)
        q.add_argument('--model')
        q.add_argument('--expect-dispatch', help='SHA-256 from prepare; required by run')
        n = q.add_mutually_exclusive_group()
        n.add_argument('--allow-network', action='store_true')
        n.add_argument('--offline', action='store_true')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.operation == 'runs':
            rows, warnings = runs(project_path(args.project), args.topic)
            print(json.dumps({'executed': False, 'runs': [public(r) for r in rows],
                              'warnings': warnings, 'complete': not warnings}, ensure_ascii=False, indent=2))
            return 0
        if args.operation == 'workstreams':
            from research_workstreams import load_plan, execution_waves
            root = project_path(args.project)
            plan = load_plan(root, safe(root, args.plan).relative_to(root).as_posix())
            print(json.dumps({'valid': True, 'executed': False, 'waves': execution_waves(plan),
                              'workstreams': plan['workstreams']}, ensure_ascii=False, indent=2))
            return 0
        if args.phase_timeout < 1:
            raise ValueError('Positive phase timeout required')
        result = prepare(args)
        result['dispatch_sha256'] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if args.operation == 'prepare':
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.expect_dispatch != result['dispatch_sha256']:
            raise ValueError('Run requires the unchanged --expect-dispatch SHA-256 from prepare')
        for name, expected in result['inputs_sha256'].items():
            if hashlib.sha256(read(Path(result['project']), name)).hexdigest() != expected:
                raise ValueError('Input changed before dispatch; prepare again')
        # Use an argument vector, not shell=True; metacharacters in user text are data.
        # The real harness performs its own source/evidence checks and retains its locks.
        return subprocess.run(result['argv'], cwd=result['project'], check=False).returncode
    except SelectionNeeded as exc:
        print(json.dumps({'status': 'needs_selection', 'executed': False, 'reason': str(exc),
                          'choices': exc.choices}, ensure_ascii=False, indent=2))
        return 2
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'blocked', 'executed': False, 'reason': str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
