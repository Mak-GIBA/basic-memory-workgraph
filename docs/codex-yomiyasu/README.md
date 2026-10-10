# yomiyasuと補助Skillで日本語の構成と表現を整える

[docs一覧](../README.md) · [導入手順](installation.md) · [使い方](usage.md)

日本語の技術文書、仕様書、Issue・PR、報告文などを、意味を保ったまま読みやすく整えるためのSkillです。
主張、数値、専門用語、条件、断定の強さを確認し、読みにくい表現だけを直します。
2.0.0-proposal.1では、通常の執筆・推敲をyomiyasu一つから進めます。読者と作業範囲を決め、段落の論点と根拠を整理し、表現と不要な留意書きを同じ工程で点検します。必要な条件や不確実性は保持します。
paragraph-writingとjapanese-direct-writingは、それぞれ段落構成だけ、留意書きだけを直す部分作業用です。同じ下書きを3スキルで別々に書き直す運用は行いません。

[install_codex_yomiyasu.sh](../../install_codex_yomiyasu.sh)は単体で使えます。
引数なしでは導入予定を表示し、`--apply`で配置します。

## 導入するもの

| 資材 | 提供元 | 役割 |
|---|---|---|
| yomiyasuの原本・lint・diff | [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu) | 日本語の推敲手順と静的検査 |
| Codex用の入口と運用設定 | このリポジトリ | 読者、段落、表現、留保を一続きで点検し、意味と事実を保持する |
| paragraph-writing | このリポジトリ。Gistに由来する旧版から役割を限定 | 段落構成だけを整理する依頼に使う |
| japanese-direct-writing | 提供されたZIPに由来する旧版から役割を限定 | 不要な留意書き・予防線を減らす依頼に使う |
| `scripts/check.py` | このリポジトリ | 読者に不要な制作説明、段落の冒頭、数値・コード等の変化を調べ、原本の検査も実行する |

yomiyasuの上流原本は`upstream/SKILL.upstream.md`と参照資料・検査スクリプト・ライセンスを含めて保存します。補助2スキルの現在の本文はこのリポジトリで管理し、由来と変更の扱いを`UPSTREAM.json`・`SOURCE.json`に記録します。1.3.0のZIP原本そのものを配置する方式から変わっています。
Codexから見える入口Skillは3件です。補助2スキルは同梱版から導入・更新し、GistやZIPの元の保存先へはアクセスしません。
ECC、Basic Memory、Office Workbench、GitHub Project Directorは必須の依存ではありません。
既存のHook、MCP、AGENTS、他のSkillの設定は変更しません。

## 読む順序

1. [導入手順](installation.md)で配置先と更新方法を確認します。
2. [使い方](usage.md)で対象の文章と保持する条件を指定します。

このリポジトリの追加設定は、上流の校正手順をCodexで使うためのものです。
新しい校正アルゴリズムや、文章の正確性を保証する仕組みではありません。
文章への効果と具体例は[比較検証](validation.md)に記載します。インストーラーの自己テストと文章品質の評価は別です。
