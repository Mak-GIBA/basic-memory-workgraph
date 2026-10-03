#!/usr/bin/env bash
# Standalone Herdr installer + canonical-cwd workspace launcher.
# Requires Bash and Python 3.8+ on Linux/macOS. No sudo or pip packages.
# Usage: bash install_herdr.sh [--dry-run] [--binary /path/to/herdr]
set -euo pipefail
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'ERROR: Python 3.8+ (python3) is required.' >&2
    exit 1
fi
python3 - "$@" <<'HERDR_INSTALL_PY'
import argparse
import datetime
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile

RUNTIME = r'''#!/usr/bin/env python3
"""Open the workspace for a directory (Herdr 0.9.3).

Adapted from the find/focus/create/attach flow of herdr-open in:
https://github.com/herdrdev/herdr/discussions/841
Seeds canonical paths from identity_cwd, then keeps stable bindings in a sidecar.
Never matches labels or creates Git worktrees.
session.json is read only. Its private schema is checked before any creation.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

BINARY = str(Path.home() / '.local/bin/herdr')
WAIT_SECONDS = 15


def cli(*args):
    result = subprocess.run([BINARY, *args], capture_output=True, text=True, timeout=10)
    try:
        value = json.loads(result.stdout)
    except ValueError:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'Invalid CLI response')
    if result.returncode or 'error' in value:
        raise RuntimeError(json.dumps(value, ensure_ascii=False))
    return value


def session_directory():
    sessions = cli('session', 'list', '--json')['sessions']
    socket = os.environ.get('HERDR_SOCKET_PATH')
    if socket:
        matches = [s for s in sessions if Path(s['socket_path']).resolve() == Path(socket).resolve()]
        if len(matches) != 1:
            raise RuntimeError('Cannot safely locate session.json for HERDR_SOCKET_PATH')
        return Path(matches[0]['session_dir'])
    name = os.environ.get('HERDR_SESSION', 'default')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name):
        raise RuntimeError('Invalid HERDR_SESSION')
    for session in sessions:
        if session['name'] == name:
            return Path(session['session_dir'])
    default = next(s for s in sessions if s['default'])
    return Path(default['session_dir']) / 'sessions' / name


def workspace_list():
    return cli('workspace', 'list')['result']['workspaces']


def ensure_server(directory, cwd):
    try:
        workspace_list()
        return
    except RuntimeError as error:
        # Only the structured no-server error authorizes starting a server.
        try:
            missing = json.loads(str(error))['error']['code'] == 'server_not_running'
        except (ValueError, KeyError, TypeError):
            missing = False
        if not missing:
            raise
    with (directory / 'herdr-open-startup.log').open('ab') as log:
        process = subprocess.Popen([BINARY, 'server'], cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=log, start_new_session=True,
                                   close_fds=True)
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            workspace_list()
            return
        except RuntimeError:
            if process.poll() is not None:
                raise RuntimeError(f'Server startup failed; see {directory}/herdr-open-startup.log')
            time.sleep(0.1)
    raise RuntimeError(f'Server startup timed out; see {directory}/herdr-open-startup.log')


def consistent_workspaces(directory):
    deadline = time.monotonic() + WAIT_SECONDS
    reason = 'session snapshot has not caught up'
    while time.monotonic() < deadline:
        live = workspace_list()
        try:
            state = json.loads((directory / 'session.json').read_text())
            saved = state['workspaces']
            identities = {}
            for workspace in saved:
                identity = workspace['identity_cwd']
                if not isinstance(identity, str) or not os.path.isabs(identity):
                    raise ValueError('identity_cwd is not an absolute path')
                identities[workspace['id']] = os.path.realpath(identity)
            if len(identities) != len(saved):
                raise ValueError('duplicate saved workspace IDs')
            if set(identities) == {w['workspace_id'] for w in live}:
                return live, identities
        except FileNotFoundError as error:
            # A fresh headless session has no workspaces and no snapshot yet.
            if not live:
                return [], {}
            reason = str(error)
        except (OSError, ValueError, KeyError, TypeError) as error:
            reason = str(error)
        time.sleep(0.1)
    raise RuntimeError(f'Cannot verify workspace identities: {reason}; no further workspace changes made')


def bound_paths(directory, identities):
    """Freeze first-seen paths: Herdr rewrites identity_cwd from the root pane."""
    path = directory / 'herdr-open-workspaces.json'
    try:
        state = json.loads(path.read_text())
        if state['version'] != 1 or not isinstance(state['workspaces'], dict):
            raise ValueError('Unsupported herdr-open workspace registry')
        known = state['workspaces']
        if any(not isinstance(cwd, str) or not os.path.isabs(cwd) for cwd in known.values()):
            raise ValueError('Invalid path in herdr-open workspace registry')
    except FileNotFoundError:
        known = {}
    return {wid: os.path.realpath(known.get(wid, cwd)) for wid, cwd in identities.items()}


def save_paths(directory, paths):
    with tempfile.NamedTemporaryFile(mode='w', dir=directory, prefix='.herdr-open-',
                                     delete=False) as file:
        temporary = file.name
        try:
            json.dump({'version': 1, 'workspaces': paths}, file, ensure_ascii=False, indent=2)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
            os.replace(temporary, directory / 'herdr-open-workspaces.json')
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def main():
    if len(sys.argv) == 2 and sys.argv[1] in ('--help', '-h'):
        print('Usage: herdr-open [DIR]\nOpen or create the workspace for DIR (default: current directory).')
        return
    if len(sys.argv) > 2:
        raise RuntimeError('Usage: herdr-open [DIR]')
    cwd = Path(sys.argv[1] if len(sys.argv) == 2 else '.').resolve(strict=True)
    if not cwd.is_dir():
        raise RuntimeError(f'Not a directory: {cwd}')
    if not sys.stdin.isatty() and os.environ.get('HERDR_ENV') != '1':
        raise RuntimeError('An interactive terminal is required to open Herdr')
    directory = session_directory()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'herdr-open.lock').open('a') as lock:
        deadline = time.monotonic() + WAIT_SECONDS
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Timed out waiting for another herdr-open invocation')
                time.sleep(0.1)
        ensure_server(directory, str(cwd))
        live, identities = consistent_workspaces(directory)
        identities = bound_paths(directory, identities)
        save_paths(directory, identities)
        matches = [w for w in live if identities[w['workspace_id']] == str(cwd)]
        if matches:
            chosen = min(matches, key=lambda w: (not w['focused'], w['number']))
            workspace_id = chosen['workspace_id']
            cli('workspace', 'focus', workspace_id)
        else:
            result = cli('workspace', 'create', '--cwd', str(cwd), '--label', cwd.name or '/', '--focus')
            workspace_id = result['result']['workspace']['workspace_id']
            # Record the successful response immediately, before waiting for
            # Herdr's debounced snapshot; a later retry must reuse this ID.
            identities[workspace_id] = str(cwd)
            save_paths(directory, identities)
            _, saved_identities = consistent_workspaces(directory)
            if workspace_id not in saved_identities:
                raise RuntimeError('Created workspace identity does not match the requested directory')
        focused = [w['workspace_id'] for w in workspace_list() if w['focused']]
        if focused != [workspace_id]:
            raise RuntimeError('Workspace focus changed before attach; run herdr again')
    # Already inside Herdr: switch the existing UI instead of nesting a client.
    if os.environ.get('HERDR_ENV') != '1':
        os.chdir(cwd)
        os.execv(BINARY, [BINARY])


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        print(f'herdr-open: {error}', file=sys.stderr)
        sys.exit(1)
'''

START = '# >>> herdr-open: cwd workspace >>>'
END = '# <<< herdr-open: cwd workspace <<<'
INSTALL_URL = 'https://herdr.dev/install.sh'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, timeout=30, text=True, **kwargs)


def checked_binary(binary):
    version = run(str(binary), '--version', capture_output=True).stdout.strip()
    if not re.fullmatch(r'herdr \S+', version):
        raise ValueError('Not a Herdr binary: ' + str(binary))
    for args, required in [
        (('session', 'list', '--help'), ('--json',)),
        (('workspace', 'create', '--help'), ('--cwd', '--focus')),
        (('workspace', 'focus', '--help'), ('workspace_id',)),
    ]:
        result = run(str(binary), *args, capture_output=True)
        help_text = result.stdout + result.stderr
        if not all(word in help_text for word in required):
            raise ValueError('Required Herdr CLI interface is missing: ' + ' '.join(args))
    return version


def replace_block(text, block):
    if START in text or END in text:
        if text.count(START) != 1 or text.count(END) != 1:
            raise ValueError('Malformed or duplicate herdr-open markers in .bashrc')
        begin = text.index(START)
        end = text.index(END) + len(END)
        if begin >= end:
            raise ValueError('Reversed herdr-open markers in .bashrc')
        unmanaged = text[:begin] + text[end:]
        updated = text[:begin] + block + text[end:]
    else:
        unmanaged = text
        updated = text + ('' if not text or text.endswith('\n') else '\n') + '\n' + block + '\n'
    if re.search(r'^\s*(?:function\s+herdr\b|herdr\s*\(\s*\)|alias\s+herdr\s*=)', unmanaged, re.M):
        raise ValueError('Unmanaged herdr function/alias exists in .bashrc; preserve it and resolve the conflict first')
    return updated


def write_file(path, text, default_mode):
    # Follow a user's existing dotfile symlink, preserving it and its target mode.
    target = path.resolve()
    if target.exists() and target.read_text() == text:
        print('Unchanged:', path)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else default_mode
    if target.exists():
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup = target.with_name(target.name + '.before-herdr-open-' + stamp)
        shutil.copy2(target, backup)
        print('Backup:', backup)
    with tempfile.NamedTemporaryFile(mode='w', dir=target.parent, delete=False) as file:
        temporary = Path(file.name)
        try:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
            os.chmod(temporary, mode)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    print('Configured:', path)


def main():
    parser = argparse.ArgumentParser(
        prog='install_herdr.sh',
        description='Install Herdr if missing, then configure Bash: cd project && herdr.',
        epilog='Requires Python 3.8+. First install also needs curl and the official installer dependencies. '
               'Existing binaries/config/session data are preserved; no server is started. '
               'Wrapper tested with Herdr 0.9.3; unknown session.json formats fail closed. '
               'After setup run: source ~/.bashrc')
    parser.add_argument('--dry-run', action='store_true', help='Show intended actions without downloads or writes')
    parser.add_argument('--binary', type=Path, help='Use this existing Herdr executable (never reinstall it)')
    args = parser.parse_args()
    if sys.version_info < (3, 8):
        raise ValueError('Python 3.8+ is required')
    if sys.platform not in ('linux', 'darwin'):
        raise ValueError('This installer supports Bash on Linux/macOS')
    home = Path.home()
    bindir = home / '.local/bin'
    wrapper = bindir / 'herdr-open'
    bashrc = home / '.bashrc'
    if args.binary:
        binary = args.binary.expanduser().absolute()
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError('--binary must name an existing executable')
        install = False
    else:
        found = shutil.which('herdr')
        binary = Path(found).absolute() if found else bindir / 'herdr'
        install = not binary.exists()
        if not install and not os.access(binary, os.X_OK):
            raise ValueError('Existing Herdr is not executable: ' + str(binary))
    if binary.resolve() == wrapper.resolve():
        raise ValueError('The Herdr binary and herdr-open wrapper must be different files')
    if install and binary.is_symlink():
        raise ValueError('Refusing to replace a dangling Herdr symlink')
    qbin, qwrapper = shlex.quote(str(binary)), shlex.quote(str(wrapper))
    block = '\n'.join([
        START,
        'case ":$PATH:" in',
        '    *":$HOME/.local/bin:"*) ;;',
        '    *) export PATH="$HOME/.local/bin:$PATH" ;;',
        'esac',
        'herdr() {',
        '    if [ "$#" -eq 0 ]; then',
        '        ' + qwrapper,
        '    else',
        '        command ' + qbin + ' "$@"',
        '    fi',
        '}',
        END,
    ])
    text = bashrc.read_text() if bashrc.exists() else ''
    updated = replace_block(text, block)
    payload = RUNTIME.replace("BINARY = str(Path.home() / '.local/bin/herdr')", 'BINARY = ' + repr(str(binary)), 1)
    compile(payload, str(wrapper), 'exec')
    # Validate the full resulting shell config before downloading or writing.
    run('bash', '-n', input=updated, capture_output=True)
    if wrapper.exists() and 'https://github.com/herdrdev/herdr/discussions/841' not in wrapper.read_text():
        raise ValueError('Unrecognized existing herdr-open; refusing to overwrite it')
    print(('Install latest stable via ' + INSTALL_URL + ': ' if install else 'Keep existing binary: ') + str(binary))
    print('Wrapper:', wrapper)
    print('Bash configuration:', bashrc, flush=True)
    if args.dry_run:
        print('Dry run: no downloads or changes.')
        return
    if install:
        if not shutil.which('curl'):
            raise ValueError('curl is required for the initial Herdr installation')
        # Official installer verifies the release SHA-256. Install into staging
        # first so a failed download/check never replaces an existing binary.
        with tempfile.TemporaryDirectory(prefix='herdr-install-') as tmp:
            staging = Path(tmp)
            script = staging / 'official-install.sh'
            run('curl', '-fsSL', '--proto', '=https', '--tlsv1.2', '--connect-timeout', '10',
                '--max-time', '25', INSTALL_URL, '-o', str(script))
            env = os.environ.copy()
            env['HERDR_INSTALL_DIR'] = str(staging / 'bin')
            env['PATH'] = str(staging / 'bin') + os.pathsep + env.get('PATH', '')
            subprocess.run(['sh', str(script)], check=True, env=env, timeout=600)
            version = checked_binary(staging / 'bin/herdr')
            bindir.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also guards against a concurrent installation.
            with binary.open('xb') as target, (staging / 'bin/herdr').open('rb') as source:
                shutil.copyfileobj(source, target)
            binary.chmod(0o755)
    else:
        version = checked_binary(binary)
    write_file(wrapper, payload, 0o755)
    wrapper.chmod(0o755)
    write_file(bashrc, updated, 0o644)
    print('Ready:', version)
    print('Run in your current Bash: source ~/.bashrc')
    print('Then: cd ~/some-project && herdr')
    print('Arguments such as herdr --version are passed directly to the original binary.')
    print('Workspace bindings: <Herdr session directory>/herdr-open-workspaces.json')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('ERROR:', error, file=sys.stderr)
        sys.exit(1)
HERDR_INSTALL_PY
