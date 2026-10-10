# yomiyasuと補助Skillで日本語の構成と表現を整える

[docs一覧](../README.md) · [導入手順](installation.md) · [使い方](usage.md)

日本語の技術文書、仕様書、Issue・PR、報告文などを、意味を保ったまま読みやすく整えるためのSkillです。
主張、数値、専門用語、条件、断定の強さを確認し、読みにくい表現だけを直します。
paragraph-writingで文書と段落の構成を整理し、yomiyasuで表現を仕上げます。構成の変更が不要な場合は、段落の並べ替えを省きます。
japanese-direct-writingでは、不要な留意書き・予防線・免責を点検します。主張や重要な条件を保ち、判断に必要な不確実性だけを具体的に残します。

[install_codex_yomiyasu.sh](../../install_codex_yomiyasu.sh)は単体で使えます。
引数なしでは導入予定を表示し、`--apply`で配置します。

## 導入するもの

| 資材 | 提供元 | 役割 |
|---|---|---|
| yomiyasuの原本・lint・diff | [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu) | 日本語の推敲手順と静的検査 |
| Codex用の入口と運用設定 | このリポジトリ | 用途に合わせて手順を選び、数値・条件・コード等を保持する |
| paragraph-writing | このリポジトリ。[k16shikanoのGist](https://gist.github.com/k16shikano/fd287c3133457c4fd8f5601d34aa817d)から調整 | 段落の役割、主張と根拠、文書全体の順序を整理する |
| japanese-direct-writing | 提供された`japanese-direct-writing.zip`を無改変で同梱 | 不要な留意書き・免責を点検し、根拠に即して直接書く |
| `scripts/check.py` | このリポジトリ | 原本の検査ツールをローカルで実行し、保護対象の変化を調べる |

yomiyasuとparagraph-writingの原本は、各Skill内の`upstream/SKILL.upstream.md`に保存します。japanese-direct-writingはZIPの本文を入口の`SKILL.md`に配置し、原本のhashとZIPのSHA256を`SOURCE.json`に記録します。Codexから見える入口Skillは3件です。
Gistの確認済み版とUnlicenseは同梱済みで、paragraph-writingの導入・更新時にGistへ通信しません。
japanese-direct-writingの導入・更新も、スクリプトの同梱版を使います。ZIPの元の保存先へはアクセスしません。
ECC、Basic Memory、Office Workbench、GitHub Project Directorは必須の依存ではありません。
既存のHook、MCP、AGENTS、他のSkillの設定は変更しません。

## 読む順序

1. [導入手順](installation.md)で配置先と更新方法を確認します。
2. [使い方](usage.md)で対象の文章と保持する条件を指定します。

このリポジトリの追加設定は、上流の校正手順をCodexで使うためのものです。
新しい校正アルゴリズムや、文章の正確性を保証する仕組みではありません。
文章への効果と具体例は[比較検証](validation.md)に記載します。インストーラーの自己テストと文章品質の評価は別です。
