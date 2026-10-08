# SpecKit Upstream Workbench 2.0.1

単一のinstall_speckit_upstream.shで独自CLI・資材・Skillを導入します。SpecKit本体は同梱せず、既存CLIを再利用します。
必要な場合に取得する公式CLIの固定版はspecify-cli==1.0.8です。

## 導入と新規準備

```bash
bash install_speckit_upstream.sh --dry-run
bash install_speckit_upstream.sh --apply
# 前版の未編集の管理資材を更新する場合
bash install_speckit_upstream.sh --apply --update
export PATH="$HOME/.local/bin:$PATH"
speckit-workbench doctor
speckit-workbench attach --project . --system APP --mode existing
speckit-workbench attach --project . --system APP --mode existing --apply
```

Python 3.11以上が必要です。通信せず独自資材だけ導入する場合は--skip-specifyを使います。
インストーラーとattachの既定はプレビューです。手で編集した管理ファイルは上書きしません。

## 読む資料

新規の正本は要件・設計・検証の3文書。内容、内部記録、旧形式の扱いは[ARTIFACTS.md](assets/references/ARTIFACTS.md)を参照してください。
必要なResearch結果も1本のreport.mdにまとめます。詳細な[見直し手順](assets/references/REASSESSMENT.md)と[項目・節の形式](assets/references/TRACE_FORMAT.md)を備えています。

日本語の要件・設計・検証文書、研究・レビュー報告には、利用可能なyomiyasuで下書きを一度推敲することを推奨します。
主張、数値、ID、条件、確認結果、根拠と断定の強さを保ち、レビュー・承認前に仕上げます。
未導入でも執筆を続け、承認済み本文を変える場合は再レビューします。固定済み資料や生ログは保持します。

## 入口と確認

| Codexの入口 | 作業 |
|---|---|
| $upstream-new | 新規の目的・要件・設計・検証計画 |
| $upstream-existing | 現状・合意済み仕様・提案の整理 |
| $upstream-change | 仕様変更の理由と影響 |
| $upstream-bug | 再現・期待挙動・修正/回帰計画 |
| $upstream-refactor | 不変条件・品質目標・設計変更 |
| $upstream-check | 文書の構造と内容の確認 |
| $upstream-review | 対象IDと本文の固定。承認はしない |
| $upstream-approve | 明示された対象だけ承認を記録 |

```bash
speckit-workbench check --project . --phase draft
speckit-workbench trace --project . --write
speckit-workbench approval-plan --project .
speckit-workbench review --project . --checkpoint next --write
speckit-workbench approve --project . --review ACTUAL_REVIEW_ID --id APP-FR-001 --by user --reference '今回の明示承認'
# 適用する承認は上のコマンドに--applyを追加
speckit-workbench gate --project . --write
speckit-workbench gate --project . --verify
```

readyには目的・ニーズ・ストーリー・要件・設計・検証と現在有効な承認が必要です。
need/storyの適用除外はgoalの具体的な理由を明示承認する場合だけ使えます。
構造検査はアプリ動作や要件の意味を保証しません。上流整理はアプリ変更の承認ではありません。

## 旧資料の任意移行

更新やattachだけでは既存の形式を変えません。

```bash
speckit-workbench migrate --project .
speckit-workbench migrate --project . --apply
```

プレビューに統合本文・リンク変更・再レビュー対象を示します。旧標準文書と既定itemを3文書へまとめ、元の文書と設定をバックアップします。
独自の上流文書を含める場合は--include-docで明示します。公式specsは移動しません。
ID・出典・承認台帳・過去スナップショットを保持し、配置が変わった承認を付け直しません。
重複ID、壊れた記録、リンクの解決不能、競合を検出し、途中失敗は復元します。移行済みなら再実行は変更しません。

## 配布の確認

```bash
bash install_speckit_upstream.sh --self-test
bash install_speckit_upstream.sh --extract /tmp/swb-source
```

保守用の正本はtools/speckit-upstream/にあります。build_single.pyで単一ファイルを再生成できます。
--self-testは公式SpecKit境界とCodex利用をモックにしたオフラインテストです。実モデルの出力品質の評価ではありません。
