# 検証記録

## 実行済み

- `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -v`：56件成功。
- `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s overlay/tests -v`：同じ機能テストの43件がリポジトリ配置でも成功。
- 合成入力から「提案手法」章と3枚のSVG、編集用JSONを実生成。SVGのXMLとしての整合、ノードの重なり・はみ出し、本文参照先の存在を検査。
- 3枚のSVGをPNG化して画像を確認。日本語フォント指定、矢印ラベルの背景描画を修正し、全体図・詳細図・比較図で読めることを確認。
- Markdownからサンプル閲覧用のHTMLを作成し、3枚のSVGをデータURIとして埋め込み。フォントファイル・外部スクリプトは同梱しない。
- 実際のGitHubコネクターで対象mainと関連ソースを読み、統合箇所と現在のblob SHAを確認。

テストログは `validation/package-tests.log` と `validation/repository-layout-tests.log` に保存。

## 検査内容

章の必須説明、記号と数式または擬似コード、3種類の図、図の重複・孤立ノード・不正参照・明示されない循環、全体図と全構成要素の対応、手法・出典・実験IDの照合、5手法目安と理由付き例外、下書きの未完成表示、未測定と採用判断の区別を検査。

不正なXML文字列のエスケープ、ワークスペース外への書き込み拒否、シンボリックリンク拒否、成果物の変更拒否、設計・レンダラー版に応じた保存先、CLIによる既存レポートの上書き拒否も検査。

適用処理では、アンカー一致、Python構文、バージョン宣言、dry-run無変更、独自編集保護、模擬ビルド失敗時の復元、再適用の冪等性、bytecodeの除外を検査。upstreamの完全な代替実行ではなく、小型fixtureとmockを用いる。

## 未検証・未完了

1. 公開リポジトリ全体への実適用、既存テスト全体の回帰、実インストーラー再生成と自己テスト。
2. Codex CLIを通じた実モデルでの企画・生成・独立レビュー・最終報告までの一連の実行。
3. 実研究の新規性、正確性、性能、読み手の理解度への改善効果。
4. GitHub上のブランチ・commit・PR作成。

## GitHubでの停止点

確認したmain：`d3f46e0d591b45cb2423317030a489b91566e891`。
作成を試したブランチ：`codex/design-research-proposed-method-report`。
GitHubのcreate_branchは2回とも `403 Resource not accessible by integration` を返した。ブランチは作成できていない。利用可能なGitHub CLIとCLI用トークンもないため、認証済みCLIへの切り替えは行えていない。

読み取りが成功したことは書き込み許可を意味しない。本パッケージは変更コードの提供であり、PR作成の完了報告ではない。書き込みとPR作成が許可される接続で、実リポジトリへの適用・検証・公開を完了する必要がある。
