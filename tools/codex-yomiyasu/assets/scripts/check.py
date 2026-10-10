#!/usr/bin/env python3
"""Read-only runner for pinned yomiyasu tools plus conservative anchor checks.
No LLM call, no source rewrite, no network. Findings do not prove semantics.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 2_000_000


def read_text(path: str) -> tuple[Path, str]:
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_file() or p.suffix.lower() not in {'.md', '.markdown', '.txt'}:
        raise ValueError('入力はUTF-8の .md/.markdown/.txt を指定してください。Office/PDFは別ツールで読み取ります。')
    if p.stat().st_size > MAX_BYTES:
        raise ValueError('入力は2MB以下にしてください。大きい文書は対象範囲を分けます。')
    with p.open('rb') as f:
        raw = f.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('入力が大きすぎます。')
    text = raw.decode('utf-8-sig')
    if '\x00' in text:
        raise ValueError('バイナリ入力は扱いません。')
    return p, text


def verified_script(name: str) -> Path:
    rel = 'upstream/scripts/' + name
    path = ROOT / rel
    manifest = json.loads((ROOT / '.installer.json').read_text(encoding='utf-8'))
    if manifest.get('owner') != 'basic-memory-workgraph/codex-yomiyasu':
        raise ValueError('installerの所有情報を確認できません。')
    for p in [path, *path.parents]:
        if p.is_symlink():
            raise ValueError('script pathにsymlinkがあります。')
        if p == ROOT:
            break
    expected = manifest.get('files', {}).get(rel)
    if not expected or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('配布元scriptが変更されています。installer --doctorで確認してください。')
    return path


def upstream(name: str, args: list[str]) -> dict:
    path = verified_script(name)
    # Isolated mode avoids accidental imports from the user's working directory.
    result = subprocess.run([sys.executable, '-I', '-B', str(path), *args],
                            capture_output=True, text=True, encoding='utf-8',
                            timeout=30, cwd=str(path.parent.parent), check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError('配布元ツールが失敗しました: ' + result.stderr[:600])
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError('配布元ツールのJSONを読めません。未実行・未確認として扱います。') from exc
    if not isinstance(output, dict):
        raise ValueError('配布元の応答形式が不正です。')
    return {'exit_code': result.returncode, 'report': output}


def anchors(text: str, protected: list[str]) -> dict[str, collections.Counter]:
    """Conservative pattern extraction, not a Markdown parser or semantic checker."""
    fences = []
    outside = []
    block = []
    start = None
    for line in text.splitlines(keepends=True):
        if start:
            block.append(line)
            if re.fullmatch(r' {0,3}' + re.escape(start[0]) + '{' + str(start[1]) + r',}[ \t]*(?:\r?\n)?', line):
                fences.append(''.join(block)); block = []; start = None
        else:
            m = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
            if m:
                start = (m[1][0], len(m[1])); block = [line]
            else:
                outside.append(line)
    if block:
        fences.append(''.join(block))
    body = ''.join(outside)
    front = re.match(r'\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|$)', body, re.S)
    inline = re.findall(r'(?<!`)(`+)([^`\n]+?)\1(?!`)', body)
    # Counts intentionally flag deletions and additions alike for human review.
    nums = re.findall(r'(?<![0-9A-Za-z_])[-+−]?\d+(?:[,.]\d+)*(?:[%％]|\s*(?:ms|秒|分|時間|日|回|件|円|万円|MB|GB))?', text)
    ids = re.findall(r'\b[A-Z][A-Z0-9]*(?:[-_][A-Z0-9]+)*[-_]\d+\b|(?<!\w)#\d+\b|(?<!\w)@[A-Za-z0-9][A-Za-z0-9-]*', text)
    urls = [u.rstrip('。、，．)）]】') for u in re.findall(r'https?://[^\s<>\]"「」]+', text)]
    return {
        'code_blocks': collections.Counter(fences),
        'inline_code': collections.Counter(v for _, v in inline),
        'frontmatter': collections.Counter([front[0]] if front else []),
        'numbers_and_units': collections.Counter(nums),
        'ids_mentions': collections.Counter(ids),
        'urls': collections.Counter(urls),
        'link_targets': collections.Counter(re.findall(r'!?\[[^\]\n]*\]\(([^\s)]+)', body)),
        'reference_links': collections.Counter(re.findall(r'^ {0,3}\[[^\]\n]+\]:\s*.+$', body, re.M)),
        'literal_quotes': collections.Counter(re.findall(r'^ {0,3}>.*$', body, re.M)),
        'math': collections.Counter(re.findall(r'\$\$[\s\S]*?\$\$|(?<![\\$])\$[^\n$]+\$', body)),
        'checkbox_state': collections.Counter(re.findall(r'^\s*[-*+]\s+\[([ xX])\]', body, re.M)),
        'specified_terms': collections.Counter({s: text.count(s) for s in protected}),
    }


def compare_anchors(before: str, after: str, protected: list[str]) -> list[dict]:
    left, right = anchors(before, protected), anchors(after, protected)
    changes = []
    for kind in left:
        if left[kind] != right[kind]:
            changes.append({'kind': kind,
                            'removed': list((left[kind]-right[kind]).elements()),
                            'added': list((right[kind]-left[kind]).elements())})
    return changes


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sp = p.add_subparsers(dest='cmd', required=True)
    l = sp.add_parser('lint', help='配布元lintを実行。点数は文章品質の合否ではありません。')
    l.add_argument('file'); l.add_argument('--strict', action='store_true')
    d = sp.add_parser('compare', help='修正前後の差分候補と保護対象の変更を検査。意味の一致は要レビュー。')
    d.add_argument('before'); d.add_argument('after')
    d.add_argument('--stance', choices=['勧め', '決まり', '説明'])
    d.add_argument('--protect', action='append', default=[], help='表記・出現数を保持したい語。繰り返し指定可能。')
    args = p.parse_args(argv)
    try:
        if args.cmd == 'lint':
            file, _ = read_text(args.file)
            report = upstream('yomiyasu_lint.py', [str(file), '--json'] + (['--strict'] if args.strict else []))
            out = {'kind': 'upstream_lint', **report, 'meaning_preservation_verified': False,
                   'note': '指摘数・点数はヒューリスティックです。0件でも意味・読みやすさ・事実を保証しません。'}
            code = report['exit_code']
        else:
            before, text_b = read_text(args.before); after, text_a = read_text(args.after)
            if before == after:
                raise ValueError('修正前と修正後は異なるファイルを指定してください。')
            if any(not term or len(term)>200 for term in args.protect):
                raise ValueError('--protectには1〜200文字の語句を指定してください。')
            report = upstream('yomiyasu_diff.py', [str(before), str(after), '--json'] +
                              (['--stance=' + args.stance] if args.stance else []))
            changes = compare_anchors(text_b, text_a, args.protect)
            out = {'kind': 'before_after_review', 'upstream': report,
                   'protected_changes': changes, 'meaning_preservation_verified': False,
                   'status': 'REVIEW_REQUIRED' if changes else 'NO_PROTECTED_CHANGE_DETECTED',
                   'note': 'パターン検査のみ。主張・否定・責務・推量・期限の意味は必ず原文と照合してください。'}
            code = 1 if changes else report['exit_code']
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return code
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'status': 'ERROR_NOT_CHECKED', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
