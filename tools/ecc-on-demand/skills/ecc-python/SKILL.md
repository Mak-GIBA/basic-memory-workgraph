---
name: ecc-python
description: Python実装でECCのpython-patternsを必要時に参照する。
---

Pythonの実装・リファクタリングで使うECC原本への入口。

`python3 {{MANAGER}} resolve python-patterns --json` を実行し、返された `path` の本文を読んで今回の作業に適用する。
相対参照は `skill_dir`、プラグイン共通資材は `plugin_root` を基準に解決し、必要な参照だけ読む。
取得に失敗した場合はエラーを報告し、推測したキャッシュや代替のECCインストールを使わない。
現在のユーザー・開発者・プロジェクトの指示を優先する。テスト専門の手順が必要なら `ecc-library` から探す。
