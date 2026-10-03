# yomiyasu — 日本語の文章を整える

[docs一覧](../README.md) · [導入手順](installation.md) · [使い方](usage.md)

日本語の技術文書、仕様書、Issue・PR、報告文などを、意味を保ったまま読みやすく整えるためのSkillです。
主張、数値、専門用語、条件、断定の強さを確認し、読みにくい表現だけを直します。

[install_codex_yomiyasu.sh](../../install_codex_yomiyasu.sh)は単体で使えます。
引数なしでは導入予定を表示し、`--apply`で配置します。

## 導入するもの

| 資材 | 提供元 | 役割 |
|---|---|---|
| yomiyasuの原本・lint・diff | [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu) | 日本語の推敲手順と静的検査 |
| Codex用の入口と運用設定 | このリポジトリ | 用途に合わせて手順を選び、数値・条件・コード等を保持する |
| `scripts/check.py` | このリポジトリ | 原本の検査ツールをローカルで実行し、保護対象の変化を調べる |

上流のSkillは`upstream/SKILL.upstream.md`に保存します。Codexから見える入口Skillは1件です。
ECC、Basic Memory、Office Workbench、GitHub Project Directorは必須の依存ではありません。
既存のHook、MCP、AGENTS、他のSkillの設定は変更しません。

## 読む順序

1. [導入手順](installation.md)で配置先と更新方法を確認します。
2. [使い方](usage.md)で対象の文章と保持する条件を指定します。

このリポジトリの追加設定は、上流の校正手順をCodexで使うためのものです。
新しい校正アルゴリズムや、文章の正確性を保証する仕組みではありません。
