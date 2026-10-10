#!/usr/bin/env python3
"""Read-only Japanese document diagnostics. Never rewrites text or calls an LLM.
The local detector is intentionally a candidate finder, not a semantic grader.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).absolute().parent.parent
MAX_BYTES = 2_000_000
GENRES = ('report', 'research', 'email', 'manual', 'article', 'template')


def read_text(path: str) -> tuple[Path, str]:
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_file() or p.suffix.lower() not in {'.md', '.markdown', '.txt'}:
        raise ValueError('入力はUTF-8の.md/.markdown/.txtを指定してください。')
    if p.stat().st_size > MAX_BYTES:
        raise ValueError('入力は2MB以下に分割してください。')
    with p.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('入力が上限を超えました。')
    text = raw.decode('utf-8-sig')
    if '\x00' in text:
        raise ValueError('NULを含む入力は扱いません。')
    return p, text


def mask_inline(text: str) -> str:
    """Mask inline code and balanced Japanese quotations, retaining offsets."""
    out = list(text)
    for m in re.finditer(r'(?<!`)(`+)(?!`)(.+?)\1(?!`)', text):
        out[m.start():m.end()] = ' ' * len(m[0])
    stack = []
    pairs = {'「': '」', '『': '』'}
    start = 0
    for i, c in enumerate(text):
        if out[i] == ' ' and text[i] != ' ':
            continue
        if c in pairs:
            if not stack:
                start = i
            stack.append(pairs[c])
        elif stack and c == stack[-1]:
            stack.pop()
            if not stack:
                out[start:i+1] = ' ' * (i+1-start)
    for m in re.finditer(r'https?://[^\s<>]+', ''.join(out)):
        out[m.start():m.end()] = ' ' * len(m[0])
    return ''.join(out)


def blocks(text: str) -> list[dict]:
    """Conservative Markdown segmentation. Not a full CommonMark parser."""
    rows = []
    fence = None
    front = False
    comment = False
    footnote_continuation = False
    for no, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if no == 1 and s == '---':
            front = True
            rows.append({'line': no, 'kind': 'frontmatter', 'text': line, 'visible': ''})
            continue
        if front:
            if s in ('---', '...'):
                front = False
            rows.append({'line': no, 'kind': 'frontmatter', 'text': line, 'visible': ''})
            continue
        if fence:
            if re.fullmatch(r' {0,3}' + re.escape(fence[0]) + '{' + str(fence[1]) + r',}[ \t]*', line):
                fence = None
            rows.append({'line': no, 'kind': 'code', 'text': line, 'visible': ''})
            continue
        m = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if m:
            fence = (m[1][0], len(m[1]))
            kind = 'code'
        elif re.match(r'^ {0,3}>', line):
            kind = 'quote'
        elif footnote_continuation and line.startswith(('    ', '\t')) and not line.startswith('        '):
            kind = 'footnote'
        elif line.startswith(('    ', '\t')):
            kind = 'code'
        elif comment or '<!--' in line:
            kind = 'comment'
            comment = '-->' not in line
        elif not s:
            kind = 'blank'
        elif re.match(r'^ {0,3}#{1,6}\s', line):
            kind = 'heading'
        elif re.match(r'^ {0,3}\[\^[^\]]+\]:', line):
            kind = 'footnote'
        elif re.match(r'^ {0,3}\[[^\]]+\]:\s*\S+', line):
            kind = 'reference'
        elif s.startswith('|') or re.match(r'^\s*\|?\s*:?-{3,}', line):
            kind = 'table'
        elif re.match(r'^\s*(?:図|表|Figure|Table)\s*\d+\s*[:：.．]', line, re.I):
            kind = 'caption'
        elif re.match(r'^ {0,3}(?:[-*+]\s+|\d+[.)]\s+)', line):
            kind = 'list'
        else:
            kind = 'prose'
        if kind == 'footnote':
            footnote_continuation = True
        elif kind != 'blank':
            footnote_continuation = False
        visible = '' if kind in {'code', 'quote', 'frontmatter', 'reference', 'blank'} else mask_inline(line)
        rows.append({'line': no, 'kind': kind, 'text': line, 'visible': visible})
    return rows


# Specific intent signals, rather than a blanket ban on technical nouns or politeness.
PATTERNS = [
    ('A01', 'high', '指示者への依頼応答', r'(?:ご依頼|ご要望|ご指示|ご質問|ご指定)(?:に|の|を|へ)'),
    ('A02', 'high', 'プロンプトの制作指示への言及', r'プロンプト(?:で求められた|の指示|に従|に沿|を入力した方)|(?:依頼者|指示者|ユーザー)(?:向けに|の(?:要望|指示)に)'),
    ('A03', 'high', '回答・修正作業の報告', r'(?:この|本)回答(?:では|は|に)|(?:修正版|完成稿)を(?:以下に|お届け|示)|(?:指示|要望)を反映し(?:ました|ています)'),
    ('A04', 'high', 'チャット上の追加申し出', r'(?:ご希望があれば|必要でしたら|ご要望があれば|ご希望に応じて).{0,45}(?:できます|します|可能|補足|ご用意)'),
    ('A05', 'medium', '執筆方針・制作の自己説明', r'(?:初見|初心者|読者|読み手).{0,32}(?:分かるよう|わかるよう|理解できるよう|伝わるよう|分かりやすく|わかりやすく).{0,28}(?:説明|解説|構成|整理)|(?:読みやすく|分かりやすく|わかりやすく|網羅的に).{0,16}(?:構成しました|整理しました|まとめました)|(?:文章|文面|文書).{0,20}(?:読みやすく|分かりやすく).{0,16}構成しました'),
    ('A06', 'high', '会話履歴への依存', r'先ほど(?:の回答|お伝えした|ご説明した)|前の回答|ここまでの(?:会話|やり取り)'),
    ('A07', 'high', '未処理の編集指示', r'(?:ここに|この箇所に|この段落に|この位置に).{0,25}(?:図|表|画像|説明|追記|挿入|追加)(?:を|する|して|入れ)|(?:TODO|TBD)\s*[:：]|\[(?:要追記|要確認|ここに[^\]]*)\]'),
]
COMPILED = [(i, s, label, re.compile(pattern)) for i, s, label, pattern in PATTERNS]


def local_lint(text: str, genre: str = 'report') -> list[dict]:
    if genre not in GENRES:
        raise ValueError('不明なgenreです。')
    findings = []
    for row in blocks(text):
        visible = row['visible']
        if not visible.strip():
            continue
        for rule, severity, label, rx in COMPILED:
            if genre == 'email' and rule in {'A01', 'A04'}:
                continue
            if genre == 'template' and rule == 'A07':
                continue
            m = rx.search(visible)
            if m:
                findings.append({'rule': rule, 'severity': severity, 'issue': label,
                                 'line': row['line'], 'column': m.start()+1,
                                 'kind': row['kind'], 'excerpt': row['text'][:240],
                                 'decision': 'REVIEW_NOT_AUTOFIX'})
    return findings


def sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r'(?<=[。！？])\s*|(?<=[.!?])(?:\s+|$)', text) if x.strip()]


def outline(text: str) -> list[dict]:
    out = []
    buf = []
    start = 1
    def flush():
        nonlocal buf
        if buf:
            body = ''.join(buf)
            parts = sentences(body)
            out.append({'kind': 'paragraph', 'line': start, 'first_sentence': parts[0] if parts else body,
                        'characters': len(body), 'sentences': len(parts)})
            buf = []
    for row in blocks(text):
        if row['kind'] == 'prose':
            if not buf:
                start = row['line']
            buf.append(row['text'].strip())
        else:
            flush()
            if row['kind'] in {'heading', 'list', 'caption', 'footnote'}:
                out.append({'kind': row['kind'], 'line': row['line'], 'text': row['text']})
    flush()
    return out


def paragraph_hints(text: str) -> list[dict]:
    hints = []
    for row in outline(text):
        if row['kind'] != 'paragraph':
            continue
        if row['characters'] > 700:
            hints.append({'line': row['line'], 'rule': 'P01', 'severity': 'low',
                          'issue': '長い段落。論点が変わる位置を確認する。長さだけで分割しない。'})
        if len(row['first_sentence']) > 180:
            hints.append({'line': row['line'], 'rule': 'P02', 'severity': 'low',
                          'issue': '長い段落冒頭文。主題と修飾の関係を確認する。'})
    return hints


def anchors(text: str, protected: list[str]) -> dict[str, Counter]:
    rows = blocks(text)
    body = '\n'.join(row['text'] for row in rows if row['kind'] != 'code')
    codes = '\n'.join(row['text'] for row in rows if row['kind'] == 'code')
    nums = re.findall(r'(?<![0-9A-Za-z_.])[-+−]?\d+(?:[,.]\d+)*(?:[eE][-+]?\d+)?(?:\s*(?:%|％|ms|μs|秒|分|時間|日|回|件|万円|円|GB|MB))?', text)
    urls = [m.rstrip('。、，．)）]】') for m in re.findall(r'https?://[^\s<>"「」]+', text)]
    modalities = re.findall(r'未確認|未評価|未検証|有意(?:差)?|可能性|示唆|推奨|義務|予定|決定|必要|とは限らない|なかった|ない', body)
    return {
        'code': Counter([codes] if codes else []),
        'inline_code': Counter(m[1] for m in re.findall(r'(?<!`)(`+)([^`\n]+)\1(?!`)', body)),
        'numbers_and_units': Counter(nums),
        'urls': Counter(urls),
        'citations': Counter(re.findall(r'\[(?:\d+(?:[-,–]\d+)*|\^[^\]]+|@[^\]]+)\]', text)),
        'ids': Counter(re.findall(r'\b[A-Z][A-Z0-9]*(?:[-_][A-Z0-9]+)*[-_]\d+\b|(?<!\w)#\d+\b|(?<!\w)@[A-Za-z0-9][\w-]*', text)),
        'link_targets': Counter(re.findall(r'!?\[[^\]\n]*\]\(([^\s)]+)', body)),
        'reference_links': Counter(row['text'] for row in rows if row['kind'] == 'reference'),
        'literal_quotes': Counter(row['text'] for row in rows if row['kind'] == 'quote'),
        'frontmatter': Counter(row['text'] for row in rows if row['kind'] == 'frontmatter'),
        'math': Counter(re.findall(r'\$\$[\s\S]*?\$\$|(?<![\\$])\$[^\n$]+\$|\\\[[\s\S]*?\\\]', body)),
        'checkboxes': Counter(re.findall(r'^\s*[-*+]\s+\[([ xX])\]', body, re.M)),
        'modality_candidates': Counter(modalities),
        'specified_terms': Counter({s: text.count(s) for s in protected}),
    }


def compare_anchors(before: str, after: str, protected: list[str] | None = None) -> list[dict]:
    protected = protected or []
    if any(not term or len(term) > 200 for term in protected):
        raise ValueError('--protectには1〜200文字を指定してください。')
    left, right = anchors(before, protected), anchors(after, protected)
    changes = []
    for kind in left:
        if left[kind] != right[kind]:
            changes.append({'kind': kind, 'removed': list((left[kind]-right[kind]).elements()),
                            'added': list((right[kind]-left[kind]).elements())})
    if before.strip() and not after.strip():
        changes.append({'kind': 'empty_output', 'removed': ['本文全体'], 'added': []})
    elif len(before) >= 300 and len(after) < len(before) * 0.6:
        changes.append({'kind': 'large_reduction', 'removed': ['40%以上の短縮。情報落ちを確認する。'], 'added': []})
    return changes


def upstream(name: str, args: list[str]) -> dict:
    marker = json.loads((ROOT / '.installer.json').read_text(encoding='utf-8'))
    if marker.get('owner') != 'basic-memory-workgraph/codex-yomiyasu' or marker.get('schema') != 1:
        raise ValueError('所有manifestを確認できません。--doctorで診断してください。')
    tracked = marker.get('files', {})
    for rel, digest in tracked.items():
        if not rel.startswith('upstream/'):
            continue
        p = ROOT / rel
        if not p.is_relative_to(ROOT) or '..' in Path(rel).parts:
            raise ValueError('不正な管理パスです。')
        for parent in [p, *p.parents]:
            if parent.is_symlink():
                raise ValueError('上流資材のsymlinkを拒否しました。')
            if parent == ROOT:
                break
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            raise ValueError('上流資材に変更・欠落があります: ' + rel)
    # Reject untracked helper modules as well, before allowing sibling imports.
    for p in (ROOT/'upstream').rglob('*'):
        if p.is_symlink() or (p.is_file() and p.relative_to(ROOT).as_posix() not in tracked):
            raise ValueError('未管理の上流資材があります。')
    rel = 'upstream/scripts/' + name
    if rel not in tracked:
        raise ValueError('上流scriptが未配置です。')
    script = ROOT/rel
    command = 'import runpy,sys; p=sys.argv.pop(1); sys.path.insert(0,str(__import__("pathlib").Path(p).parent)); sys.argv[0]=p; runpy.run_path(p,run_name="__main__")'
    result = subprocess.run([sys.executable, '-I', '-B', '-c', command, str(script), *args],
                            capture_output=True, text=True, encoding='utf-8', timeout=30,
                            cwd=script.parent, check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError('上流検査が失敗しました: ' + result.stderr[:600])
    if len(result.stdout) > 5_000_000:
        raise ValueError('上流の検査出力が上限を超えました。')
    report = json.loads(result.stdout)
    if not isinstance(report, dict):
        raise ValueError('上流JSONの形式が変わっています。')
    return {'status': 'EXECUTED', 'exit_code': result.returncode, 'report': report}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    lint = sub.add_parser('lint')
    lint.add_argument('file'); lint.add_argument('--genre', choices=GENRES, default='report')
    lint.add_argument('--strict', action='store_true'); lint.add_argument('--local-only', action='store_true')
    ol = sub.add_parser('outline'); ol.add_argument('file')
    diff = sub.add_parser('compare')
    diff.add_argument('before'); diff.add_argument('after'); diff.add_argument('--protect', action='append', default=[])
    diff.add_argument('--stance', choices=('説明', '決まり', '勧め')); diff.add_argument('--local-only', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.cmd == 'outline':
            _, text = read_text(args.file)
            out = {'kind': 'outline', 'entries': outline(text), 'semantic_structure_verified': False}
            code = 0
        elif args.cmd == 'lint':
            file, text = read_text(args.file)
            local = local_lint(text, args.genre)
            hints = paragraph_hints(text)
            up = {'status': 'NOT_RUN_EXPLICIT_LOCAL_ONLY', 'exit_code': 0} if args.local_only else upstream('yomiyasu_lint.py', [str(file), '--json'] + (['--strict'] if args.strict else []))
            out = {'kind': 'writing_review', 'audience_findings': local, 'paragraph_hints': hints,
                   'upstream': up, 'meaning_preservation_verified': False}
            code = max(up['exit_code'], int(any(x['severity'] == 'high' or args.strict for x in local)))
        else:
            b, before = read_text(args.before); a, after = read_text(args.after)
            if a == b:
                raise ValueError('前後で異なるファイルを指定してください。')
            changes = compare_anchors(before, after, args.protect)
            up = {'status': 'NOT_RUN_EXPLICIT_LOCAL_ONLY', 'exit_code': 0} if args.local_only else upstream('yomiyasu_diff.py', [str(b), str(a), '--json'] + (['--stance='+args.stance] if args.stance else []))
            out = {'kind': 'before_after_review', 'protected_changes': changes, 'upstream': up,
                   'status': 'REVIEW_REQUIRED' if changes else 'NO_PROTECTED_CHANGE_DETECTED',
                   'meaning_preservation_verified': False}
            code = max(up['exit_code'], int(bool(changes)))
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return code
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'status': 'ERROR_NOT_CHECKED', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
