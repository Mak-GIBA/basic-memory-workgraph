"""Single-file Codex writing skills installer, companion version 1.2.0.
Reads/fetches pinned upstream text files; never runs npm/pip or an upstream installer.
All helper assets are embedded by the release packager.
"""
from __future__ import annotations
import argparse
import ast
import base64
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import time
import types
import unittest
from unittest import mock
import urllib.error
import urllib.request
import uuid
import zipfile
import zlib

SELF_SCRIPT = None
VERSION = '1.2.0'
OWNER = 'basic-memory-workgraph/codex-yomiyasu'
COMPONENTS = ('yomiyasu', 'paragraph-writing')
OWNERS = {'yomiyasu': OWNER, 'paragraph-writing': 'basic-memory-workgraph/paragraph-writing'}
REPO = 'nanaism/yomiyasu'
TAG = 'v1.0.4'
COMMIT = '8d5abeebe2dd20c2db005deaddcc50be43c59c0a'
# Expected Git blob identities and byte counts, read from the pinned repository tree.
# Git's blob SHA-1 is an integrity identifier, not a publisher signature.
PINS = {
    'SKILL.md': ('df3412cd46066a03a6f000a66af19d079ad6a4f8', 30291),
    'LICENSE': ('f0d06f87f9b209d47c7f7963321ff71bab68c1e8', 1064),
    'README.md': ('31d7e00c2297d6b85b382dc05a2d3663c1534908', 22888),
    'references/domains/business.md': ('a4a0c492d95df742a275202ac80148c6b08abe0b', 3719),
    'references/domains/essay.md': ('36919c63949102934c414bbe8a8f700a5ed1a971', 2216),
    'references/domains/tech.md': ('1394795ff9e3d43004330b3abc93a83527babae7', 3379),
    'references/gemini-syntax.md': ('f06c2bb457d582b890f9581047fac33c4716ef83', 26466),
    'references/slop-catalog.md': ('c4ad42f1ac4a3ab8255f1d35438806fe40a58b42', 10668),
    'scripts/yomiyasu_lint.py': ('cd5e05a82d7cadcab43cd8e7acf6516716682b28', 27280),
    'scripts/yomiyasu_diff.py': ('ccc1c6a553bcc6b1a30578a1d20e697891f51089', 26801),
}
MANIFEST = '.installer.json'
MAX_FILE = 2_000_000
MAX_TOTAL = 20_000_000
KNOWN_STYLERS = {'natural-japanese', 'japanese-humanizer', 'stop-ai-slop-jp',
                 'humanizer', 'humanizer-ja', 'stop-slop', 'yomiyasu'}
ASSET_SHA256 = '98c7af7f4cbb55c20ba93c018556e7417d69d19275d99c87d9c6b596d46933ba'
ASSET_B64 = '@ASSET_B64@'

class InstallError(Exception):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


def abs_path(value: str | Path) -> Path:
    # Keep symlinks visible for explicit validation rather than resolving them away.
    return Path(os.path.abspath(os.path.expanduser(str(value))))


def safe_path(p: Path) -> None:
    for part in [p, *p.parents]:
        if part.is_symlink():
            raise InstallError('symlink経由の管理先には書き込みません: ' + str(part))
        if part.exists() and part != p and not part.is_dir():
            raise InstallError('親パスがディレクトリではありません: ' + str(part))


def safe_rel(value: str) -> str:
    p = PurePosixPath(value)
    if not value or value != p.as_posix() or p.is_absolute() or '..' in p.parts or '\\' in value or ':' in value:
        raise InstallError('管理ファイルの相対パスが不正です。')
    return value


def emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def assets() -> dict[str, bytes]:
    if ASSET_B64 == '@ASSET_B64@':
        root = Path(__file__).parent
        out = {}
        for prefix, directory in [('', root/'assets'), ('tests/', root/'tests')]:
            for p in sorted(directory.rglob('*')):
                if p.is_symlink():
                    raise InstallError('開発資材のsymlinkを拒否しました。')
                if p.is_file() and '__pycache__' not in p.parts:
                    out[safe_rel(prefix+p.relative_to(directory).as_posix())] = p.read_bytes()
        return out
    raw = base64.b64decode(ASSET_B64, validate=True)
    if sha(raw) != ASSET_SHA256:
        raise InstallError('埋め込み資材が破損しています。')
    data = json.loads(zlib.decompress(raw))
    if not isinstance(data, dict):
        raise InstallError('埋め込み資材が不正です。')
    return {safe_rel(k): v.encode('utf-8') for k, v in data.items()}


def map_upstream(name: str) -> str:
    return 'upstream/' + ('SKILL.upstream.md' if name == 'SKILL.md' else name)


def verify_upstream(name: str, data: bytes) -> bytes:
    expected, size = PINS[name]
    if len(data) != size or blob_sha(data) != expected:
        raise InstallError('配布元ファイルのサイズ/固定blob hashが一致しません: ' + name)
    try:
        text = data.decode('utf-8')
    except UnicodeError as exc:
        raise InstallError('UTF-8ではない配布元ファイル: ' + name) from exc
    if '\x00' in text:
        raise InstallError('配布元に想定外のバイナリ: ' + name)
    if name.endswith('.py'):
        try:
            ast.parse(text, filename=name)
        except SyntaxError as exc:
            raise InstallError('配布元Pythonの構文エラー: ' + name) from exc
    return data


class LockedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        from urllib.parse import urlparse
        u = urlparse(newurl)
        if u.scheme != 'https' or u.hostname not in {'raw.githubusercontent.com', 'api.github.com'}:
            raise InstallError('想定外のダウンロード先へのredirectを拒否しました。')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url: str) -> bytes:
    from urllib.parse import urlparse
    u = urlparse(url)
    if u.scheme != 'https' or u.hostname not in {'raw.githubusercontent.com', 'api.github.com'}:
        raise InstallError('想定外のダウンロード先を拒否しました: ' + str(u.hostname or ''))
    opener = urllib.request.build_opener(LockedRedirect())
    request = urllib.request.Request(url, headers={'User-Agent': 'codex-yomiyasu-installer/1.1.0',
                                                  'Accept': 'application/vnd.github+json'})
    # No bearer token, document text or local path is sent.
    with opener.open(request, timeout=25) as response:
        payload = response.read(MAX_FILE + 1)
    if len(payload) > MAX_FILE:
        raise InstallError('ダウンロード上限を超えました。')
    return payload


def _json_download(url: str) -> dict:
    try:
        value = json.loads(download(url))
    except (ValueError, UnicodeError, urllib.error.URLError, OSError) as exc:
        raise InstallError('GitHubの更新情報を取得できませんでした。既存Skillは変更していません。') from exc
    if not isinstance(value, dict):
        raise InstallError('GitHub APIの応答形式が想定外です。')
    return value


def _resolve_tag_commit(tag: str) -> str:
    from urllib.parse import quote
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?', tag):
        raise InstallError('最新版tagの形式が想定外です: ' + tag)
    ref = _json_download(f'https://api.github.com/repos/{REPO}/git/ref/tags/{quote(tag, safe="")}')
    obj = ref.get('object')
    for _ in range(3):
        if not isinstance(obj, dict) or not re.fullmatch(r'[0-9a-f]{40}', str(obj.get('sha',''))):
            raise InstallError('release tagの参照先が不正です。')
        if obj.get('type') == 'commit':
            return obj['sha']
        if obj.get('type') != 'tag':
            raise InstallError('release tagがcommit/tag以外を参照しています。')
        tag_obj = _json_download(str(obj.get('url','')))
        obj = tag_obj.get('object')
    raise InstallError('release tagの参照が深すぎます。')


def _release_file_manifest(commit: str) -> dict[str, dict]:
    tree = _json_download(f'https://api.github.com/repos/{REPO}/git/trees/{commit}?recursive=1')
    if tree.get('truncated'):
        raise InstallError('Git tree応答がtruncatedです。安全のため更新しません。')
    rows = tree.get('tree')
    if not isinstance(rows, list):
        raise InstallError('Git tree応答にtreeがありません。')
    prefix = 'skills/yomiyasu/'
    out = {}
    total = 0
    for row in rows:
        if not isinstance(row, dict) or row.get('type') != 'blob':
            continue
        path = str(row.get('path',''))
        name = None
        if path in {'LICENSE', 'README.md'}:
            name = path
        elif path.startswith(prefix):
            rel = path[len(prefix):]
            if rel == 'SKILL.md' or rel.startswith(('references/', 'scripts/', 'assets/')):
                name = rel
        if name is None:
            continue
        if row.get('mode') not in {'100644','100755'}:
            raise InstallError('配布対象に通常ファイル以外があります: ' + path)
        size = row.get('size'); git_sha = row.get('sha')
        if not isinstance(size, int) or size < 0 or size > MAX_FILE or not re.fullmatch(r'[0-9a-f]{40}', str(git_sha or '')):
            raise InstallError('配布対象のtree metadataが不正です: ' + path)
        total += size
        if total > MAX_TOTAL or len(out) >= 200:
            raise InstallError('最新版Skillのサイズ/ファイル数が安全上限を超えています。')
        out[name] = {'repo_path': path, 'git_blob_sha1': git_sha, 'size': size}
    required = {'SKILL.md','LICENSE','scripts/yomiyasu_lint.py','scripts/yomiyasu_diff.py'}
    missing = sorted(required - set(out))
    if missing or not any(k.startswith('references/') for k in out):
        raise InstallError('最新版releaseに必要ファイルがありません: ' + ', '.join(missing or ['references/']))
    return out


def latest_release_meta() -> dict:
    meta = _json_download(f'https://api.github.com/repos/{REPO}/releases/latest')
    if meta.get('draft') or meta.get('prerelease'):
        raise InstallError('latest releaseがdraft/prereleaseのため更新しません。')
    tag = str(meta.get('tag_name') or '')
    commit = _resolve_tag_commit(tag)
    return {
        'tag': tag,
        'commit': commit,
        'published_at': meta.get('published_at'),
        'release_url': meta.get('html_url'),
        'files': _release_file_manifest(commit),
    }


def _verify_release_file(name: str, data: bytes, spec: dict) -> bytes:
    if len(data) != spec['size'] or blob_sha(data) != spec['git_blob_sha1']:
        raise InstallError('release treeと取得内容が一致しません: ' + name)
    text_ext = {'.md','.txt','.json','.yaml','.yml','.py','.toml'}
    if Path(name).suffix.lower() in text_ext or name in {'LICENSE'}:
        try:
            text = data.decode('utf-8')
        except UnicodeError as exc:
            raise InstallError('UTF-8ではない配布元テキスト: ' + name) from exc
        if '\x00' in text:
            raise InstallError('配布元テキストにNULがあります: ' + name)
        if name.endswith('.py'):
            try:
                ast.parse(text, filename=name)
            except SyntaxError as exc:
                raise InstallError('配布元Pythonの構文エラー: ' + name) from exc
    return data


def fetch_release_upstream(meta: dict) -> dict[str, bytes]:
    out = {}
    commit = meta['commit']
    for name, spec in sorted(meta['files'].items()):
        raw = f'https://raw.githubusercontent.com/{REPO}/{commit}/{spec["repo_path"]}'
        try:
            data = download(raw)
        except (OSError, urllib.error.URLError) as exc:
            raise InstallError('最新版releaseの取得に失敗しました。既存Skillは変更していません: ' + name) from exc
        out[map_upstream(name)] = _verify_release_file(name, data, spec)
    return out


def baseline_meta() -> dict:
    return {'tag': TAG, 'commit': COMMIT, 'published_at': None, 'release_url': None,
            'files': {k: {'repo_path': k, 'git_blob_sha1': v[0], 'size': v[1]} for k,v in PINS.items()}}


def installed_upstream_meta(files: dict[str, bytes], manifest: dict) -> dict:
    try:
        raw = json.loads(files['UPSTREAM.json'])
    except Exception:
        raw = {}
    return {
        'tag': raw.get('tag') or manifest.get('upstream_tag'),
        'commit': raw.get('commit') or manifest.get('upstream_commit'),
        'published_at': raw.get('published_at'),
        'release_url': raw.get('release_url'),
        'files': raw.get('files') or {},
    }


def check_update(target: Path) -> dict:
    files = inventory(target) if target.exists() else {}
    manifest = manifest_for(files) if files else None
    latest = latest_release_meta()
    installed = installed_upstream_meta(files, manifest) if manifest else None
    return {
        'action': 'check-update',
        'installed': installed,
        'latest': {k:v for k,v in latest.items() if k != 'files'},
        'update_available': (installed is None or installed.get('commit') != latest['commit'] or manifest.get('version') != VERSION),
        'note': '確認のみ。更新は --update --apply で明示してください。',
    }


def fetch_upstream(source: Path | None = None) -> dict[str, bytes]:
    out = {}
    for name in PINS:
        if source is not None:
            p = source / name
            safe_path(p)
            if not p.is_file() or p.stat().st_size > MAX_FILE:
                raise InstallError('配布元ファイルがない/大きすぎます: ' + name)
            data = p.read_bytes()
        else:
            raw = f'https://raw.githubusercontent.com/{REPO}/{COMMIT}/{name}'
            try:
                data = download(raw)
            except (OSError, urllib.error.URLError):
                api = f'https://api.github.com/repos/{REPO}/contents/{name}?ref={COMMIT}'
                try:
                    meta = json.loads(download(api))
                    if not isinstance(meta, dict) or meta.get('encoding') != 'base64' or meta.get('sha') != PINS[name][0]:
                        raise InstallError('GitHub contents応答が固定版と一致しません: ' + name)
                    data = base64.b64decode(''.join(meta['content'].split()), validate=True)
                except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
                    raise InstallError('配布元の取得に失敗しました。既存Skillは変更していません: ' + name) from exc
        out[map_upstream(name)] = verify_upstream(name, data)
    return out


def inventory(directory: Path) -> dict[str, bytes]:
    safe_path(directory)
    if not directory.is_dir():
        raise InstallError('Skill配置先がディレクトリではありません。')
    out = {}; total = 0
    for parent, dirs, files in os.walk(directory, followlinks=False):
        for d in dirs:
            p = Path(parent) / d
            if p.is_symlink():
                raise InstallError('管理下のsymlinkを拒否しました: ' + str(p))
        for filename in files:
            p = Path(parent) / filename
            mode = p.lstat().st_mode
            if not stat.S_ISREG(mode):
                raise InstallError('通常ファイル以外を拒否しました: ' + str(p))
            size = p.stat().st_size
            total += size
            if size > MAX_FILE or total > MAX_TOTAL or len(out) >= 1000:
                raise InstallError('Skillフォルダが検査上限を超えました。')
            out[p.relative_to(directory).as_posix()] = p.read_bytes()
    return out


def manifest_for(files: dict[str, bytes], component: str = 'yomiyasu') -> dict:
    if MANIFEST not in files:
        raise InstallError('同名Skillは別の方法で導入済みです。--forceでも上書きしません。既存の導入方法で整理してください。')
    try:
        manifest = json.loads(files[MANIFEST])
    except (ValueError, UnicodeError) as exc:
        raise InstallError('所有manifestが不正です。変更しません。') from exc
    if not isinstance(manifest, dict) or manifest.get('owner') != OWNERS[component] or manifest.get('schema') != 1:
        raise InstallError('このinstallerの管理対象ではありません。')
    tracked = manifest.get('files')
    if not isinstance(tracked, dict) or not tracked or MANIFEST in tracked:
        raise InstallError('管理ファイル一覧が不正です。')
    for name, value in tracked.items():
        safe_rel(name)
        if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise InstallError('管理hashが不正です。')
    if manifest.get('mode') not in {'auto', 'explicit'}:
        raise InstallError('保存済み発動モードが不正です。')
    return manifest


def edited(files: dict[str, bytes], manifest: dict) -> list[str]:
    return [k for k, v in manifest['files'].items() if k not in files or sha(files[k]) != v]


def conflict_scan(target: Path, cwd: Path | None = None) -> dict:
    home = abs_path(Path.home())
    codex = abs_path(os.environ.get('CODEX_HOME', str(home / '.codex')))
    cwd = abs_path(cwd or Path.cwd())
    roots = {target.parent, home/'.agents/skills', codex/'skills'}
    for parent in [cwd, *cwd.parents]:
        roots.add(parent/'.agents/skills'); roots.add(parent/'.codex/skills')
        if parent == home:
            break
    duplicates = []; stylers = []
    for root in sorted(roots, key=str):
        if not root.is_dir():
            continue
        for name in sorted(KNOWN_STYLERS | set(COMPONENTS)):
            d = root / name
            if d == target or not (d/'SKILL.md').is_file():
                continue
            if name == target.name:
                duplicates.append(str(d))
            elif name not in COMPONENTS:
                stylers.append(str(d))
    return {'duplicate_skill': duplicates, 'duplicate_'+target.name.replace('-', '_'): duplicates,
            'other_style_skills': stylers,
            'scope': '標準ユーザー/現プロジェクトの既知パスを確認。全plugin cacheと別プロジェクトは未走査。'}


def bundle(upstream: dict[str, bytes], mode: str, upstream_meta: dict | None = None) -> dict[str, bytes]:
    own = assets()
    out = {k: v for k, v in own.items() if k.startswith(('references/', 'scripts/')) or k == 'SKILL.md'}
    out.update(upstream)
    policy = 'true' if mode == 'auto' else 'false'
    upstream_meta = upstream_meta or baseline_meta()
    out['agents/openai.yaml'] = ('''interface:
  display_name: "yomiyasu 日本語推敲"
  short_description: "日本語文章が成果物のタスクで、意味を保って自然に整える"
  default_prompt: "日本語文章そのものが成果物なら$yomiyasuを使って最終推敲してください。Issue/PR、定例報告、リリース文、仕様書、技術・研究文書、メール等を対象にし、主張・数値・専門用語・条件・断定強度は保持してください。コード実装だけ・事実回答だけ・逐語引用には適用しないでください。"
policy:
  products:
    - "CODEX"
  allow_implicit_invocation: ''' + policy + '\n').encode('utf-8')
    out['UPSTREAM.json'] = (json.dumps({'repository': REPO, 'tag': upstream_meta['tag'], 'commit': upstream_meta['commit'],
                                      'published_at': upstream_meta.get('published_at'), 'release_url': upstream_meta.get('release_url'),
                                      'files': upstream_meta.get('files', {}),
                                      'note': '配布元資材は無改変。SKILL.mdのみネスト検出を避けSKILL.upstream.mdへ改名。入口・運用設定は独自追加。'},
                                     ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    return out


@contextmanager
def lock(target: Path):
    lock_path = target.parent / '.yomiyasu-installer.lock'
    safe_path(lock_path)
    try:
        fd = os.open(lock_path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise InstallError('別の処理のlockがあります。実行中でないことを確認してから手動で除去してください: ' + str(lock_path)) from exc
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(json.dumps({'pid': os.getpid(), 'time': time.time()}))
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def backup(target: Path, files: dict[str, bytes]) -> Path:
    base = target.parent / '.yomiyasu-installer-backups'
    safe_path(base); base.mkdir(parents=True, exist_ok=True, mode=0o700)
    archive = base / (target.name+'-'+time.strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:10] + '.zip')
    fd = os.open(archive, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        with zipfile.ZipFile(f, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for name, content in sorted(files.items()):
                z.writestr(name, content)
    return archive


def paragraph_bundle(mode: str) -> dict[str, bytes]:
    prefix = 'paragraph-writing/'
    out = {k[len(prefix):]: v for k, v in assets().items() if k.startswith(prefix)}
    meta = json.loads(out['UPSTREAM.json'])
    for name, digest in meta['files'].items():
        if name not in out or sha(out[name]) != digest:
            raise InstallError('同梱したparagraph-writing原本のhashが一致しません。')
    policy = 'true' if mode == 'auto' else 'false'
    out['agents/openai.yaml'] = (
        'interface:\n'
        '  display_name: "paragraph-writing 段落構成"\n'
        '  short_description: "日本語文書の段落の役割と主張・根拠のつながりを整える"\n'
        '  default_prompt: "$paragraph-writingで、読者と目的に合う段落構成に整えてください。主張・数値・条件・断定の強さを保持してください。"\n'
        'policy:\n  products:\n    - "CODEX"\n  allow_implicit_invocation: ' + policy + '\n'
    ).encode()
    return out


def replace_directories(stages: list[tuple[Path | None, Path]]) -> None:
    """Commit directory switches together; retain every original until all renames succeed."""
    switched = []
    try:
        for stage, target in stages:
            retired = target.parent / ('.'+target.name+'-retired-'+uuid.uuid4().hex)
            had = target.exists()
            if had:
                os.replace(target, retired)
            entry = {'target': target, 'retired': retired, 'had': had, 'placed': False}
            switched.append(entry)
            if stage is not None:
                os.replace(stage, target)
                entry['placed'] = True
    except BaseException:
        for entry in reversed(switched):
            try:
                if entry['placed']:
                    shutil.rmtree(entry['target'])
                if entry['had']:
                    os.replace(entry['retired'], entry['target'])
            except OSError as exc:
                # Do not delete the remaining original if restoration itself fails.
                raise InstallError('復元に失敗しました。原本を保持しています: '+str(entry['retired'])) from exc
        raise
    for entry in switched:
        if entry['had']:
            try:
                shutil.rmtree(entry['retired'])
            except OSError:
                # The commit succeeded; report cleanup separately rather than imply rollback.
                print('WARN: 配置/解除は完了しましたが旧一時フォルダを除去できません: '+str(entry['retired']), file=sys.stderr)


def replace_directory(stage: Path, target: Path) -> None:
    replace_directories([(stage, target)])


def plan(target: Path, mode: str | None, force: bool, project: Path | None = None,
         component: str = 'yomiyasu') -> tuple[dict, dict | None, dict[str, bytes]]:
    safe_path(target)
    files = inventory(target) if target.exists() else {}
    manifest = manifest_for(files, component) if target.exists() else None
    if manifest:
        changes = edited(files, manifest)
        if changes:
            raise InstallError('管理ファイルに変更・欠落があります。--forceでも消しません: '+', '.join(changes))
    effective = mode or (manifest['mode'] if manifest else 'auto')
    same = bool(manifest and manifest.get('version') == VERSION and manifest['mode'] == effective)
    if manifest and not same and not force:
        raise InstallError('既存版/設定を更新するには --force を明示してください。')
    result = {'action': 'skip' if same and not force else ('update' if manifest else 'install'),
              'component': component, 'target': str(target), 'version': VERSION, 'mode': effective,
              'conflicts': conflict_scan(target, project), 'changes_other_settings': False,
              'note': 'autoはSkill選択の許可で、毎回答の自動校正Hookではありません。'}
    if component == 'yomiyasu':
        result.update(upstream_tag=manifest.get('upstream_tag') if manifest else TAG,
                      upstream_commit=manifest.get('upstream_commit') if manifest else COMMIT)
    else:
        result['upstream_revision'] = json.loads(assets()['paragraph-writing/UPSTREAM.json'])['revision']
    return result, manifest, files


def selected_plans(root: Path, names: tuple[str, ...], mode: str | None, force: bool,
                   project: Path | None) -> dict:
    inherited = 'auto'
    yomi = root/'yomiyasu'
    # A separately installed/edited yomiyasu does not become managed merely by
    # installing paragraph-writing. Only a valid owned manifest supplies a default.
    if mode is None and yomi.exists():
        try:
            inherited = manifest_for(inventory(yomi))['mode']
        except (InstallError, OSError, ValueError):
            pass
    if 'yomiyasu' in names:
        yomi_state = plan(yomi, mode, force, project)
        inherited = yomi_state[0]['mode']
    states = {}
    for name in names:
        target = root/name
        if name == 'yomiyasu':
            states[name] = yomi_state
        else:
            chosen = mode if mode is not None else (inherited if not target.exists() else None)
            states[name] = plan(target, chosen, force, project, name)
    return states


def prepare_install(result: dict, manifest: dict | None, files: dict[str, bytes],
                    source: Path | None, latest: dict | None) -> tuple[dict, dict[str, bytes]]:
    name, mode = result['component'], result['mode']
    network = False
    if name == 'paragraph-writing':
        expected = paragraph_bundle(mode)
        meta = json.loads(expected['UPSTREAM.json'])
        upstream_marker = {'upstream_revision': meta['revision']}
    else:
        if latest:
            meta = latest
            if manifest and manifest.get('upstream_commit') == meta['commit']:
                upstream = {k:v for k,v in files.items() if k.startswith('upstream/')}
                if 'upstream/SKILL.upstream.md' not in upstream:
                    raise InstallError('既存upstream資材が不完全です。')
                meta = installed_upstream_meta(files, manifest)
            else:
                upstream = fetch_release_upstream(meta)
                network = True
        elif source is not None:
            upstream = fetch_upstream(source)
            meta = baseline_meta()
        elif manifest:
            meta = installed_upstream_meta(files, manifest)
            upstream = {k:v for k,v in files.items() if k.startswith('upstream/')}
            if 'upstream/SKILL.upstream.md' not in upstream:
                raise InstallError('既存upstream資材がありません。')
        else:
            meta = latest_release_meta()
            upstream = fetch_release_upstream(meta)
            network = True
        expected = bundle(upstream, mode, meta)
        upstream_marker = {'upstream_tag': meta['tag'], 'upstream_commit': meta['commit']}
    extras = {k:v for k,v in files.items() if manifest and k not in manifest['files'] and k != MANIFEST}
    collisions = sorted(set(extras) & set(expected))
    if collisions:
        raise InstallError('ユーザー追加ファイルが新資材と競合します: '+', '.join(collisions))
    marker = {'owner': OWNERS[name], 'component': name, 'schema': 1, 'version': VERSION,
              'mode': mode, **upstream_marker, 'files': {k:sha(v) for k,v in sorted(expected.items())},
              'publisher_signature_verified': False}
    content = {**expected, **extras, MANIFEST: (json.dumps(marker, ensure_ascii=False, indent=2)+'\n').encode()}
    return {**result, **upstream_marker, 'applied': True, 'network': network,
            'preserved_extra_files': sorted(extras), 'implicit_invocation': mode == 'auto',
            'next': '適用後はCodexを再起動してください。明示する場合は $'+name+' を使えます。'}, content


def summarize(results: dict[str, dict]) -> dict:
    if len(results) == 1:
        return next(iter(results.values()))
    return {'action': 'bundle', 'version': VERSION, 'applied': any(r.get('applied', False) for r in results.values()),
            'network': any(r.get('network', False) for r in results.values()),
            'components': results, 'changes_other_settings': False}


def install_selected(root: Path, names: tuple[str, ...] = COMPONENTS, mode: str | None = None,
                     force: bool = False, apply: bool = False, source: Path | None = None,
                     project: Path | None = None, update: bool = False) -> dict:
    if source is not None and ('yomiyasu' not in names or update):
        raise InstallError('--source-dir はyomiyasuの導入にだけ使用でき、--updateとは併用できません。')
    states = selected_plans(root, names, mode, force or update, project)
    latest = latest_release_meta() if update and 'yomiyasu' in names else None
    results = {}
    for name, (result, manifest, files) in states.items():
        result.update(applied=False, network=bool(latest and name == 'yomiyasu'))
        if update:
            if name == 'yomiyasu':
                installed = manifest.get('upstream_commit') if manifest else None
                result.update(upstream_tag=latest['tag'], upstream_commit=latest['commit'],
                              upstream_update=installed != latest['commit'])
                current_upstream = manifest and installed == latest['commit']
            else:
                current_upstream = manifest and manifest.get('upstream_revision') == result['upstream_revision']
            if current_upstream and manifest.get('version') == VERSION and manifest['mode'] == result['mode'] and not force:
                result['action'] = 'skip'
        results[name] = result
    pending = [name for name in names if results[name]['action'] != 'skip']
    if not apply or not pending:
        return summarize(results)
    for result in results.values():
        if result['conflicts']['duplicate_skill']:
            raise InstallError('別の場所に同名Skillがあります。二重登録はしません: '+', '.join(result['conflicts']['duplicate_skill']))
    root.mkdir(parents=True, exist_ok=True)
    staged = []
    with lock(root/names[0]):
        try:
            for name in names:
                target = root/name
                safe_path(target)
                now = inventory(target) if target.exists() else {}
                if now != states[name][2]:
                    raise InstallError('lock取得前に既存Skillが変わりました。変更せず終了します。')
                if conflict_scan(target, project)['duplicate_skill']:
                    raise InstallError('別の場所に同名Skillがあります。二重登録はしません。')
            for name in pending:
                result, manifest, files = states[name]
                prepared, content = prepare_install(result, manifest, files, source, latest)
                stage = Path(tempfile.mkdtemp(prefix='.'+name+'-stage-', dir=root))
                staged.append((stage, root/name))
                for rel, data in content.items():
                    safe_rel(rel)
                    dst = stage/rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(data)
                    dst.chmod(0o644)
                results[name] = prepared
            # Check every selected component, including skipped ones, before any switch.
            for name in names:
                target = root/name
                now = inventory(target) if target.exists() else {}
                if now != states[name][2]:
                    raise InstallError('準備中に既存Skillが変わりました。変更せず終了します。')
                if conflict_scan(target, project)['duplicate_skill']:
                    raise InstallError('準備中に同名Skillが追加されました。二重登録はしません。')
            for name in pending:
                result, manifest, files = states[name]
                archive = backup(root/name, files) if manifest else None
                results[name]['backup'] = str(archive) if archive else None
            for name in names:
                target = root/name
                now = inventory(target) if target.exists() else {}
                if now != states[name][2]:
                    raise InstallError('バックアップ中に既存Skillが変わりました。変更せず終了します。')
            replace_directories(staged)
        finally:
            for stage, target in staged:
                if stage.exists():
                    shutil.rmtree(stage)
    return summarize(results)


def install(target: Path, mode: str | None = None, force: bool = False, apply: bool = False,
            source: Path | None = None, project: Path | None = None, update: bool = False) -> dict:
    """Retain the existing single-yomiyasu Python entry point."""
    return install_selected(target.parent, ('yomiyasu',), mode, force, apply, source, project, update)


def uninstall_selected(root: Path, names: tuple[str, ...], apply: bool) -> dict:
    states = {}
    results = {}
    for name in names:
        target = root/name
        safe_path(target)
        if not target.exists():
            results[name] = {'action': 'absent', 'component': name, 'applied': False}
            continue
        files = inventory(target)
        manifest = manifest_for(files, name)
        if edited(files, manifest):
            raise InstallError('編集済みの管理ファイルがあるため解除しません: '+name)
        extras = [k for k in files if k not in manifest['files'] and k != MANIFEST]
        if extras:
            raise InstallError('ユーザー追加ファイルがあるため解除しません: '+name+' / '+', '.join(extras))
        states[name] = files
        results[name] = {'action': 'uninstall', 'component': name, 'target': str(target), 'applied': False}
    if not apply or not states:
        return summarize(results)
    with lock(root/next(iter(states))):
        for name, files in states.items():
            if inventory(root/name) != files:
                raise InstallError('解除準備中に内容が変更されました。')
        for name, files in states.items():
            results[name]['backup'] = str(backup(root/name, files))
        for name, files in states.items():
            if inventory(root/name) != files:
                raise InstallError('バックアップ中に内容が変更されました。解除せず終了します。')
        replace_directories([(None, root/name) for name in states])
        for name in states:
            results[name]['applied'] = True
    return summarize(results)


def uninstall(target: Path, apply: bool) -> dict:
    return uninstall_selected(target.parent, ('yomiyasu',), apply)


def doctor(target: Path, project: Path | None, component: str = 'yomiyasu') -> tuple[dict, int]:
    warnings = conflict_scan(target, project)
    out = {'component': component, 'target': str(target), 'python': sys.version.split()[0],
           'codex_on_path': bool(shutil.which('codex')), 'conflicts': warnings}
    try:
        files = inventory(target)
        marker = manifest_for(files, component)
        changed = edited(files, marker)
        openai = files.get('agents/openai.yaml', b'').decode('utf-8', 'replace')
        out.update(version=marker['version'], mode=marker['mode'],
                   implicit_invocation=('allow_implicit_invocation: true' in openai), edited=changed,
                   status='READY_FILES' if not changed else 'DAMAGED_OR_EDITED')
        if component == 'yomiyasu':
            meta = installed_upstream_meta(files, marker)
            out.update(upstream_tag=meta.get('tag'), upstream_commit=meta.get('commit'))
        else:
            out['upstream_revision'] = marker.get('upstream_revision')
        return out, 0 if not changed and not warnings['duplicate_skill'] else 2
    except (InstallError, OSError, ValueError) as exc:
        out.update(status='NOT_READY', error=str(exc))
        return out, 2


def check_updates(root: Path, names: tuple[str, ...]) -> dict:
    results = {}
    for name in names:
        if name == 'yomiyasu':
            results[name] = {**check_update(root/name), 'component': name, 'network': True, 'applied': False}
        else:
            target = root/name
            safe_path(target)
            files = inventory(target) if target.exists() else {}
            marker = manifest_for(files, name) if target.exists() else None
            revision = json.loads(assets()['paragraph-writing/UPSTREAM.json'])['revision']
            results[name] = {'action': 'check-update', 'component': name, 'network': False,
                             'installed_version': marker.get('version') if marker else None,
                             'latest_version': VERSION, 'bundled_revision': revision,
                             'update_available': not marker or marker.get('version') != VERSION or marker.get('upstream_revision') != revision,
                             'note': '確認のみ。同梱版への更新は --update --apply。Gistへの通信はありません。'}
    return summarize(results)


def extract(destination: Path) -> dict:
    safe_path(destination)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise InstallError('展開先は存在しないか、空のディレクトリを指定してください。')
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in assets().items():
        p = destination / name; safe_path(p); p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('xb') as f:
            f.write(data)
    # Make readable Python source available for independent review/testing.
    if SELF_SCRIPT is not None:
        shell = Path(SELF_SCRIPT).read_text(encoding='utf-8')
        module_source = shell.split("<<'YOMI_INSTALL_PY'\n", 1)[1].rsplit('\nYOMI_INSTALL_PY', 1)[0]
        module_source = module_source.replace(
            "    SELF_SCRIPT = abs_path(sys.argv[1])\n    raise SystemExit(main(sys.argv[2:]))",
            "    raise SystemExit(main())")
        (destination/'installer.py').write_text(module_source, encoding='utf-8')
    elif '__file__' in globals():
        source = Path(__file__).read_text(encoding='utf-8')
        if ASSET_B64 == '@ASSET_B64@':
            raw = zlib.compress(json.dumps({k:v.decode('utf-8') for k,v in assets().items()}, ensure_ascii=False,
                                           sort_keys=True, separators=(',', ':')).encode(), 9)
            source = source.replace("ASSET_B64 = '@ASSET_B64@'", 'ASSET_B64 = '+repr(base64.b64encode(raw).decode()))
            source = re.sub(r"^ASSET_SHA256 = '.*'$", 'ASSET_SHA256 = '+repr(sha(raw)), source, flags=re.M)
        (destination/'installer.py').write_text(source, encoding='utf-8')
    (destination/'upstream-pin.json').write_text(json.dumps({'repo': REPO, 'baseline_tag': TAG, 'baseline_commit': COMMIT, 'baseline_files': PINS, 'update_policy': 'latest stable GitHub Release via --update'}, indent=2)+'\n')
    return {'action': 'extract', 'path': str(destination), 'note': '独自資材を展開。初期baselineと更新ポリシーを記録。インストールはしていません。'}


def self_test() -> int:
    module = types.ModuleType('yomiyasu_installer_tests')
    module.I = sys.modules[__name__]
    exec(compile(assets()['tests/test_installer.py'].decode(), 'test_installer.py', 'exec'), module.__dict__)
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    print('Offline tests: upstream/network responses are mocked. No Codex model invocation.', flush=True)
    # Discovery walks project ancestors as well as HOME. Keep the test CWD
    # outside the caller's project so installed skills cannot leak into fixtures.
    previous_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix='yomiyasu-test-project-') as directory:
        try:
            os.chdir(directory)
            result = unittest.TextTestRunner(verbosity=2).run(suite)
        finally:
            os.chdir(previous_cwd)
    return 0 if result.wasSuccessful() else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='Codex用yomiyasu + paragraph-writing installer（単一ファイル）')
    a = p.add_mutually_exclusive_group()
    a.add_argument('--apply', action='store_true', help='実際に配置/解除する')
    a.add_argument('--dry-run', action='store_true', help='予定表示のみ（既定）')
    p.add_argument('--force', action='store_true', help='companion設定/資材を明示更新。上流更新は --update。編集済みは上書きしない')
    p.add_argument('--update', action='store_true', help='GitHub Releasesの最新安定版yomiyasuへ更新。--applyなしは予定表示')
    p.add_argument('--mode', choices=['auto', 'explicit'], help='自然言語発動を許可/明示呼び出しのみ。新規はauto、既存は設定を維持')
    p.add_argument('--only', choices=['all', *COMPONENTS], default='all', help='導入/更新/診断/解除の対象。既定は両方')
    action = p.add_mutually_exclusive_group()
    action.add_argument('--doctor', '--status', action='store_true', help='配置とhash、暗黙発火設定、既知の競合を診断。通信なし')
    action.add_argument('--check-update', action='store_true', help='GitHub Releasesの最新安定版と導入版を比較。読み取りのみ')
    action.add_argument('--uninstall', action='store_true', help='本installer所有のSkillだけ解除。既定は予定表示')
    action.add_argument('--self-test', action='store_true', help='一時HOMEでローカルテスト。外部取得は模擬応答')
    action.add_argument('--extract', metavar='DIRECTORY', help='独自Skill/検査コード/テストを展開')
    p.add_argument('--skills-dir', help='Skillを配置する親ディレクトリ。既定 ~/.agents/skills')
    p.add_argument('--source-dir', help='固定commitと一致するローカルupstreamチェックアウト。通信不要')
    p.add_argument('--project', help='競合診断対象プロジェクト。設定変更やHook登録はしない')
    args = p.parse_args(argv)
    try:
        if args.doctor or args.self_test or args.extract or args.check_update:
            if args.apply or args.force or args.mode or args.source_dir or args.uninstall or args.update:
                raise InstallError('診断/展開/テストと変更用オプションは同時指定できません。')
        if args.uninstall and (args.force or args.mode or args.source_dir or args.update):
            raise InstallError('解除と更新オプションは同時指定できません。')
        root = abs_path(args.skills_dir or Path.home()/'.agents/skills')
        names = COMPONENTS if args.only == 'all' else (args.only,)
        project = abs_path(args.project) if args.project else None
        if args.self_test:
            if args.only != 'all':
                raise InstallError('--self-test は両方を検証するため --only と併用できません。')
            return self_test()
        if args.extract:
            if args.only != 'all':
                raise InstallError('--extract は全資材を展開するため --only と併用できません。')
            emit(extract(abs_path(args.extract))); return 0
        if args.doctor:
            outcomes = {name: doctor(root/name, project, name) for name in names}
            emit(summarize({name:value[0] for name,value in outcomes.items()}))
            return max(value[1] for value in outcomes.values())
        if args.check_update:
            emit(check_updates(root, names)); return 0
        if args.uninstall:
            emit(uninstall_selected(root, names, args.apply)); return 0
        result = install_selected(root, names, args.mode, args.force, args.apply,
                                  abs_path(args.source_dir) if args.source_dir else None, project, args.update)
        emit(result)
        return 0
    except (InstallError, OSError, ValueError, KeyError) as exc:
        emit({'status': 'ERROR', 'message': str(exc), 'note': '不明な状態で上書きせず停止しました。'})
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
