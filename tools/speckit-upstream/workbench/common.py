from __future__ import annotations
import contextlib, hashlib, json, os, re, shlex, shutil, subprocess, tempfile
from pathlib import Path
from typing import Any, Iterable

class WorkbenchError(Exception):
    pass

def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'

def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError) as exc:
        raise WorkbenchError(f'JSONを読めません: {path}: {exc}') from exc
    if not isinstance(data, dict):
        raise WorkbenchError(f'JSON objectが必要: {path}')
    return data

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def absolute_env(name: str, default: Path) -> Path:
    p = Path(os.environ.get(name, str(default))).expanduser()
    if not p.is_absolute():
        raise WorkbenchError(f'{name} は絶対パスにしてください: {p}')
    return p

def locations() -> dict[str, Path]:
    home = Path.home()
    data = absolute_env('XDG_DATA_HOME', home / '.local/share') / 'speckit-workbench'
    config = absolute_env('XDG_CONFIG_HOME', home / '.config') / 'speckit-workbench'
    return {'home':home, 'data':data, 'config':config,
            'bin':absolute_env('SWB_BIN_DIR', home / '.local/bin'),
            'skill':absolute_env('SWB_SKILL_DIR', home / '.agents/skills/speckit-workbench')}

def reject_symlinks(path: Path) -> None:
    p = path.absolute()
    for part in [p, *p.parents]:
        if part.is_symlink():
            raise WorkbenchError(f'管理対象のsymlinkは変更しません: {part}')

def inside(root: Path, relative: str) -> Path:
    r = Path(relative)
    if r.is_absolute() or not r.parts or '..' in r.parts or '\\' in relative:
        raise WorkbenchError(f'プロジェクト内の相対パスが必要: {relative}')
    p = root / r
    reject_symlinks(p)
    for parent in p.parents:
        if parent.exists() and not parent.is_dir():
            raise WorkbenchError(f'親パスがディレクトリではありません: {parent}')
    if not p.resolve().is_relative_to(root.resolve()):
        raise WorkbenchError(f'対象外パス: {relative}')
    return p

def project(path: str | Path) -> Path:
    p = Path(path).expanduser().absolute()
    if not p.is_dir():
        raise WorkbenchError(f'既存のプロジェクトフォルダを指定してください: {p}')
    reject_symlinks(p)
    return p

def atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    reject_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def add_files(root: Path, files: dict[str, bytes], apply: bool, executable: set[str] | None = None) -> list[str]:
    """Preflight every path; never overwrite divergent content. Roll back new files on I/O failure."""
    executable = executable or set()
    additions = []
    for rel, data in sorted(files.items()):
        p = inside(root, rel)
        if p.exists():
            if not p.is_file() or p.read_bytes() != data:
                raise WorkbenchError(f'既存内容と競合。変更せず停止: {p}')
            print(f'[SKIP] {rel}')
        else:
            additions.append(rel)
            print(f'[ADD]  {rel}')
    if apply:
        written=[]
        try:
            for rel in additions:
                p=inside(root,rel)
                # Exclusive creation protects against accidental concurrent replacement.
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open('xb') as f: f.write(files[rel])
                p.chmod(0o755 if rel in executable else 0o644)
                written.append(p)
        except Exception:
            for p in reversed(written):
                if p.exists() and sha(p.read_bytes()) == sha(files[str(p.relative_to(root))]): p.unlink()
            raise
    return additions

def command(argv: list[str], cwd: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv,cwd=cwd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',
                              timeout=timeout,check=False,env={**os.environ,'NO_COLOR':'1','TERM':'dumb','COLUMNS':'160'})
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise WorkbenchError(f'実行できません: {shlex.join(argv)}: {exc}') from exc

def checked(argv: list[str], cwd: Path | None = None, timeout: int = 60) -> str:
    r=command(argv,cwd,timeout)
    if r.returncode:
        raise WorkbenchError(f'コマンド失敗({r.returncode}): {shlex.join(argv)}\n{r.stdout[-5000:]}\n{r.stderr[-5000:]}')
    return r.stdout

def executable(name: str) -> str | None:
    found=shutil.which(name)
    if found: return str(Path(found).absolute())  # Preserve wrapper/symlink executable invocation.
    p=locations()['bin']/name
    return str(p) if p.is_file() and os.access(p,os.X_OK) else None

def identifier(value: str) -> str:
    if not re.fullmatch(r'[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+',value):
        raise WorkbenchError('IDは APP-FR-001 のような英大文字・数字・ハイフンにしてください')
    return value

def system_id(value: str) -> str:
    if not re.fullmatch(r'[A-Z][A-Z0-9]{0,23}',value):
        raise WorkbenchError('system IDは英大文字から始まる英大文字・数字(24文字以内)')
    return value

def load_project(root: Path) -> dict:
    p=inside(root,'.specify/workbench.json')
    if not p.is_file(): raise WorkbenchError('先に attach --project ... --system APP --apply を実行してください')
    c=read_json(p)
    if c.get('schema_version')!=1: raise WorkbenchError('未対応のworkbench設定バージョン')
    system_id(c.get('system',''))
    inside(root,c.get('docs_dir',''))
    return c

@contextlib.contextmanager
def project_lock(root: Path):
    # Attach is addition-only; lock created only when --apply, not during dry-run.
    p=inside(root,'.speckit-workbench.lock')
    try:
        with p.open('x') as f: f.write(str(os.getpid()))
    except FileExistsError as exc:
        raise WorkbenchError(f'別の処理が実行中か、前回のlockが残っています: {p}') from exc
    try: yield
    finally: p.unlink(missing_ok=True)
