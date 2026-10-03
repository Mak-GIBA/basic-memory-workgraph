---
name: ecc-errors
description: 例外処理・再試行・失敗からの復旧設計でECCのerror-handlingを参照する。
---

エラー処理、外部サービスの再試行、復旧設計で使うECC原本への入口。

`python3 {{MANAGER}} resolve error-handling --json` を実行し、返された `path` の本文を読んで今回の作業に適用する。
相対参照は `skill_dir`、プラグイン共通資材は `plugin_root` を基準に解決し、必要な参照だけ読む。
取得に失敗した場合はエラーを報告し、推測したキャッシュや代替のECCインストールを使わない。
現在のユーザー・開発者・プロジェクトの指示を優先する。実際の再試行や外部操作の権限は元の依頼に従う。
