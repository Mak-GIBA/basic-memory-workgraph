#!/usr/bin/env python3
"""Flag likely prompt-author-facing prose in Japanese Markdown/TXT drafts.

This is a conservative *candidate finder*, not an automatic rewriting tool.
By default high-confidence findings cause a non-zero exit; all findings need
human/agent context review. No external dependencies.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

RULES = [
    ("high", "指示者への言及", r"(?:ご依頼|ご要望|ご指示|ご質問|ご指定)(?:に|の|を|へ)"),
    ("high", "プロンプトへの言及", r"(?:ご提示の|いただいた|与えられた)?(?:プロンプト|依頼文|指示文)(?:に|の|を|では|から)"),
    ("high", "返答そのものへの言及", r"(?:この|本)(?:回答|返信|出力)(?:では|は|に)"),
    ("high", "追加提案の会話文", r"(?:ご希望があれば|必要でしたら|ご要望があれば).{0,40}(?:でき|します|可能|ご用意)"),
    ("high", "未完成の編集指示", r"(?:ここに|この箇所に|この段落に|この位置に).{0,25}(?:図|表|画像|説明|追記|挿入|追加)(?:を|する|して|入れ)"),
    ("medium", "対話的な導入", r"(?:以下に|これから|ここでは).{0,32}(?:説明|解説|紹介|まとめ|整理)(?:します|いたします|していきます|する|ます|ました)"),
    ("medium", "執筆方針の説明", r"(?:初見の方|初心者|読者|読み手).{0,24}(?:分かりやすく|わかりやすく|理解できるよう|伝わるよう)(?:.{0,18})(?:説明|解説|まとめ|整理|構成)"),
    ("medium", "内容より制作の自己評価", r"(?:読みやすく|網羅的に|分かりやすく|わかりやすく).{0,15}(?:まとめました|整理しました|解説しました|構成しました)"),
]
COMPILED = [(s, n, re.compile(p)) for s, n, p in RULES]


@dataclass
class Finding:
    file: str
    line: int
    severity: str
    issue: str
    excerpt: str


def inspect(path: Path) -> list[Finding]:
    findings = []
    text = path.read_text(encoding="utf-8-sig")
    fence = None
    yaml_frontmatter = False
    for line_no, line in enumerate(text.splitlines(), start=1):
        s = line.strip()
        if line_no == 1 and s == "---":
            yaml_frontmatter = True
            continue
        if yaml_frontmatter:
            if s == "---":
                yaml_frontmatter = False
            continue
        m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if m:
            token = m.group(1)
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1]:
                fence = None
            continue
        if fence is not None or not s:
            continue
        # Do not inspect obvious quoted examples or markdown tabular rows.
        if s.startswith((">", "|", "<!--", "//")):
            continue
        # Disregard inline code identifiers but not surrounding prose.
        plain = re.sub(r"`[^`]+`", "", line)
        for severity, issue, pattern in COMPILED:
            if pattern.search(plain):
                findings.append(Finding(str(path), line_no, severity, issue, s[:180]))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="Markdown or UTF-8 text files")
    parser.add_argument("--json", action="store_true", help="Output JSON diagnostics")
    parser.add_argument("--fail-on", choices=("high", "all", "never"), default="high")
    args = parser.parse_args()
    findings: list[Finding] = []
    for p in args.files:
        if not p.is_file():
            parser.error(f"File not found: {p}")
        if p.suffix.lower() not in {".md", ".txt", ".rst", ".tex"}:
            parser.error(f"Only text sources are supported: {p}")
        findings.extend(inspect(p))
    if args.json:
        print(json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2))
    else:
        for f in findings:
            print(f"{f.file}:{f.line}: [{f.severity}] {f.issue}: {f.excerpt}")
        print(f"{len(findings)} possible audience-boundary issue(s); review in context.")
    if args.fail_on == "all" and findings:
        return 1
    if args.fail_on == "high" and any(f.severity == "high" for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
