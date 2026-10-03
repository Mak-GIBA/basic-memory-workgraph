---
name: ecc-security
description: 認証・秘密情報を扱う変更や安全性レビューでECCのsecurity-reviewを参照する。
---

認証・秘密情報を扱う変更や、依頼された安全性レビューで使うECC原本への入口。

`python3 {{MANAGER}} resolve security-review --json` を実行し、返された `path` の本文を読んで今回の作業に適用する。
相対参照は `skill_dir`、プラグイン共通資材は `plugin_root` を基準に解決し、必要な参照だけ読む。
取得に失敗した場合はエラーを報告し、推測したキャッシュや代替のECCインストールを使わない。
現在のユーザー・開発者・プロジェクトの指示を優先する。レビューを外部への検査・送信の許可と解釈しない。
