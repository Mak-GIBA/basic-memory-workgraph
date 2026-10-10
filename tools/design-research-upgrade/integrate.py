#!/usr/bin/env python3
"""Apply pinned-base research functionality and simplify the Codex-facing entry."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import re
from command_assets import assets, COMMANDS

ROOT = Path(__file__).resolve().parent
VERSION_D, VERSION_U = '2.4.0', '2.0.5'


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def one(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Changed integration anchor: ' + before[:100])
    return text.replace(before, after, 1)


def patch_installer(text):
    text = one(text, 'def main(installer: Path, argv: list[str]) -> int:',
               (ROOT/'installer_commands.py').read_text('utf-8') +
               '\n\ndef main(installer: Path, argv: list[str]) -> int:')
    text = one(text, '            result = inspect_target(safe_path(root / NAME))',
               '            result = {**inspect_target(safe_path(root / NAME)), "legacy_shortcuts": command_status(root)}')
    text = one(text, '        print("  Scholarly helper: <skill>/scripts/research.py providers")',
               '        print("  Codex: $design-research + a short natural-language goal")\n'
               '        print("  Plan, research, reassess, resume and status are internal workflow phases.")\n'
               '        print("  Scholarly helper: <skill>/scripts/research.py providers")')
    text = one(text, '"scripts/reassessment.py", "scripts/readable_report.py", "scripts/research_workstreams.py"',
               '"scripts/reassessment.py", "scripts/readable_report.py", "scripts/research_workstreams.py",\n'
               '    "scripts/codex_interface.py", "scripts/workflow_overview.py", "references/codex-interface.md",\n'
               '    "references/workflow-guide.md", "scripts/evaluation_contract.py",\n'
               '    "references/effectiveness-evaluation.md"')
    text = re.sub(r'(?m)^VERSION = "[0-9.]+"$', 'VERSION = "' + VERSION_D + '"', text)
    compile(text, 'install_design_research.py', 'exec')
    return text


def apply_to_stage(repo):
    """Only called on disposable, hash-verified base sources, never live app code."""
    core = module(ROOT/'core_upgrade/apply_upgrade.py', 'core_workstream_upgrade')
    changes = core.plan(repo, verify_base=True)
    for rel, raw in changes.items():
        path = repo/rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    for source in (ROOT/'overlay').rglob('*'):
        if source.is_file() and source.suffix != '.pyc' and '__pycache__' not in source.parts:
            target = repo/source.relative_to(ROOT/'overlay')
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(source.read_bytes())
    skill = repo/'tools/design-research/skill'
    for rel, raw in assets().items():
        p = skill/rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
    p = repo/'tools/design-research/install_design_research.py'
    p.write_text(patch_installer(p.read_text('utf-8')), 'utf-8')
    for p in (repo/'tools/design-research/build_installer.py', skill/'scripts/harness.py'):
        s = p.read_text('utf-8').replace('2.2.2', VERSION_D)
        p.write_text(s, 'utf-8')
    p = skill/'SKILL.md'; s = p.read_text('utf-8')
    main_flow = '''
## 最初に判断する: 1つの入口からワークフロー全体を扱う
`$design-research` が唯一の推奨ユーザー入口。Skill名を使い分けさせず、
[ワークフローと停止境界](references/workflow-guide.md)を**必ず読む**。
短い指示例: `$design-research 検索精度を改善して`。
初回は `scripts/workflow_overview.py --project <project>` で実行済み工程を確認し、
目的・要件・過去runを読んで以下を依頼から判断する。
- 新しい単一方式の比較: `research`。
- 複数のコアロジックにまたがる要件: 要件から分解・計画し、要求された範囲で各workstreamを研究。
- 完了研究の条件変更/よりよい別原理の探索: `reassess`。
- 中断した同条件の作業: `resume`。
- 状態確認のみ: `runs`（read-only）。
- 新機能全体の要件・設計書: 親の `$upstream-new` / `$upstream-change` が責任を持ち、
  このSkillを方式比較の段階で使用し、最後に統合設計へ戻す。
約5候補を目安に、必要な数式・反証条件・図解を用意する。小さな比較では候補数を減らす理由を明記する。
提案手法章はその詳細設計が目的に必要な場合に選び、ユーザーに長い手順指示を求めない。
内部では[scripts/codex_interface.py](scripts/codex_interface.py)の実行前確認・ハッシュ照合・
実ハーネスによる検証を保持。ネット利用・実装変更・承認の境界を守る。
効果・精度・性能の検証では[主要指標と対照実験](references/effectiveness-evaluation.md)を必ず読み、
実験前に評価目的・主要指標・採点・比較条件・採用条件を固定する。最終出力の実測と
同じ入力を使った基準案・候補案の具体例を報告する。ツールの応答を主要効果の代理にしない。
設計・文献調査は効果未測定を明記して条件付きで完了できる。改善なしも有効な測定結果。
汎用比較ではcomparison、提案手法の詳細章が必要な場合はproposed-methodを選ぶ。
比較設計と実験コードの作成は別工程。保存済み工程を再開時に再利用し、タイムアウトの
原因と実行済み検証をrole receiptで区別する。既存の時間・安全・証拠の制限を守る。
並列は依存関係に応じた計画のみ、同一projectでは既存ロックに従い直列で実行する。
計画のみがユーザー目的なら、研究を自動開始せず計画で停止する。
短い自然文からのSkill自動発見は保証ではなく、Codex実機で別途評価する。
'''
    s = one(s, '# Design Research\n', '# Design Research\n' + main_flow)
    p.write_text(s, 'utf-8')
    # Keep one explicit/implicitly discoverable interface; don't require long prompts.
    p = skill/'agents/openai.yaml'
    yaml_text = p.read_text('utf-8')
    for key, replacement in (
        ('short_description', '要件から研究テーマを見つけ、方式検討・再検討・検証・図解報告を一括で行う'),
        ('default_prompt', 'Use $design-research. 依頼と現行要件・過去結果を確認し、必要な研究工程だけ実施して。'),
    ):
        pattern = r'(?m)^  ' + key + r': [^\n]*$'
        yaml_text, count = re.subn(pattern, '  ' + key + ': ' + json.dumps(replacement, ensure_ascii=False), yaml_text)
        if count != 1:
            raise ValueError('Changed Skill interface field: ' + key)
    p.write_text(yaml_text, 'utf-8')
    for rel in ('assets/prompts/common.md', 'assets/references/RESEARCH_FIRST.md'):
        p = repo/'tools/speckit-upstream'/rel
        p.write_text(p.read_text('utf-8') + '''
## 研究との接続: ユーザーにSkillの使い分けを求めない
upstreamは全体ワークフロー（ストーリー→要件→方式比較→設計→検証）の親。
技術選択の不確実な部分を要件から切り出して、内部で `design-research` を実行する。
ユーザーは `$upstream-new` や `$upstream-change` でシステム全体の目的を伝えるだけでよい。
設計前には実行済みの研究結果と要件IDを接続し、統合後の設計・図解・検証を戻す。
必要な場合だけ `design-research/references/workflow-guide.md` の中の工程を選ぶ。
ユーザーに `design-research-plan` 等の旧ショートカットを使い分けさせない。
個別の研究は `$design-research` だけで依頼できる。計画と実験の結果を混同しない。
''', 'utf-8')
    for rel in ('build_single.py', 'workbench/__init__.py'):
        p = repo/'tools/speckit-upstream'/rel
        p.write_text(p.read_text('utf-8').replace('2.0.3', VERSION_U), 'utf-8')
    for p in (repo/'tools/design-research').rglob('*.py'):
        compile(p.read_text('utf-8'), str(p), 'exec')
    for p in (repo/'tools/speckit-upstream').rglob('*.py'):
        compile(p.read_text('utf-8'), str(p), 'exec')
    return {'design_research_version': VERSION_D, 'upstream_version': VERSION_U,
            'skills': ['design-research'], 'base_commit': core.BASE,
            'migration': 'unmodified owned 2.3.0 shortcuts retired, edited/unmanaged preserved'}
