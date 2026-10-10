# Compatibility migration for owned Codex shortcuts from 2.3.0.
# New installations publish only the main design-research Skill. None of the old
# shortcuts' instructions are removed from the main Skill's internal references.
COMMAND_NAMES = ('design-research-reassess', 'design-research-plan',
                 'design-research-workstream', 'design-research-resume', 'design-research-status')
COMMAND_MANIFEST = '.design-research-command.json'


def command_hashes(target):
    out = {}
    for p in sorted(target.rglob('*')):
        rel = p.relative_to(target).as_posix()
        mode = p.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            fail('Refusing non-regular legacy Skill path: '+str(p))
        if p.is_file() and rel != COMMAND_MANIFEST:
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def command_status(root):
    states = []
    for name in COMMAND_NAMES:
        path = safe_path(root / name)
        if not path.exists():
            states.append({'name': name, 'state': 'absent'}); continue
        if not path.is_dir():
            states.append({'name': name, 'state': 'unmanaged'}); continue
        marker = safe_path(path / COMMAND_MANIFEST)
        try:
            meta = json.loads(marker.read_text('utf-8'))
        except (OSError, ValueError):
            meta = {}
        if (not isinstance(meta, dict) or meta.get('owner') != OWNER+'/commands'
                or meta.get('name') != name or not isinstance(meta.get('files'), dict)
                or not meta['files']):
            states.append({'name': name, 'state': 'unmanaged'}); continue
        states.append({'name': name, 'state': 'installed', 'version': meta.get('version'),
                       'modified': command_hashes(path) != meta['files']})
    return states


_perform_core = perform


def perform(root, payload, decoded, *, update=False, force=False,
            uninstall=False, dry_run=False):
    """Retire only intact, owned legacy shortcuts; preserve edits and unmanaged paths.

    No new companion Skills are installed. When the main core update fails, restore
    the original shortcut directories in-place. The core installer owns its own
    transactional update and only untouched 2.3.0 shortcuts are safely retired.
    """
    root = safe_path(root)
    core_plan = _perform_core(root, payload, decoded, update=update, force=force,
                              uninstall=uninstall, dry_run=True)
    original = command_status(root)
    retire = [r['name'] for r in original
              if r['state'] == 'installed' and not r.get('modified')]
    retained = [r['name'] for r in original
                if r['state'] == 'unmanaged' or r.get('modified')]
    # Don't retire a functioning 2.3.0 interface while refusing to update its core.
    current_core = inspect_target(safe_path(root / NAME))
    if not uninstall and core_plan.get('action') == 'skip' and current_core.get('version') != VERSION:
        retire = []
    plan = {**core_plan, 'codex_entries': ['$design-research'],
            'legacy_shortcuts_to_retire': retire,
            'legacy_shortcuts_preserved': retained,
            'legacy_shortcuts': original}
    if dry_run:
        return {**plan, 'dry_run': True}
    if not retire:
        actual = _perform_core(root, payload, decoded, update=update, force=force,
                               uninstall=uninstall)
        return {**plan, **actual, 'dry_run': False, 'legacy_shortcuts': command_status(root)}
    root.mkdir(parents=True, exist_ok=True)
    lock = safe_path(root / '.design-research-command-install.lock')
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError:
        fail('Legacy shortcut migration lock exists; inspect before retrying')
    stage = Path(tempfile.mkdtemp(prefix='.design-research-legacy-', dir=root))
    backup = safe_path(root.parent / '.design-research-backups' / ('legacy-'+uuid.uuid4().hex))
    moved = []
    try:
        if command_status(root) != original:
            fail('Codex shortcuts changed during preflight')
        for name in retire:
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copytree(root / name, backup / name)
            if command_hashes(backup / name) != command_hashes(root / name):
                fail('Legacy shortcut backup failed integrity check')
        if command_status(root) != original or inspect_target(safe_path(root / NAME)) != current_core:
            fail('Destination changed before shortcut migration')
        for name in retire:
            os.replace(root / name, stage / name)
            moved.append(name)
        actual = _perform_core(root, payload, decoded, update=update, force=force,
                               uninstall=uninstall)
        plan.update(actual)
        plan['dry_run'] = False
        plan['legacy_shortcuts'] = command_status(root)
        plan['legacy_backup'] = str(backup)
        return plan
    except BaseException:
        for name in reversed(moved):
            os.replace(stage / name, root / name)
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        lock.rmdir()
