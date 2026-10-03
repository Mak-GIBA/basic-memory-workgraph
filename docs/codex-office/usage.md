# Office Workbenchで文書を扱う

[概要](README.md) · [導入手順](installation.md)

## 最初の依頼

導入後に新しいCodexセッションを開き、会話欄に対象ファイルと保持する条件を書きます。

```text
$office-workbench report.docxの第3章を修正して。
原図と章構成を維持し、原本は上書きしないで。
```

```text
$office-workbench slides.pptxの4枚目の下半分を整理して。
既存のデザインを維持し、重なりも確認して。
```

```text
$office-workbench paper.pdfを図表込みで読み、根拠ページ付きで説明して。
```

`$office-workbench`はターミナルのコマンドではありません。
CLIの`prepare`は原本ハッシュと作業コピーのreceiptを作ります。
原本と既存出力を上書きせず、変更後の本文・構造・描画を確認します。
日本語の本文推敲にはyomiyasuを併用できますが、文章検査とレイアウト確認は別です。

## 環境と合成サンプルを確認する

```bash
office-workbench doctor
office-workbench smoke-test --out-dir /tmp/office-smoke-01
```

`doctor`は環境の存在を調べます。`AVAILABLE`はレイアウトが正しいという判定ではありません。
smoke-testはユーザー文書ではなく、日本語の合成DOCX・PPTX・PDFを作って操作を確認します。
`smoke-report.json`と出力PNGを確認してください。
OfficeCLIがなければ`NOT_RUN`を記録し、別エンジンの成功で代用しません。
PNG生成の成功だけで見た目を確認済みにはしません。

## 対象外と保存先

`.doc`、`.ppt`、マクロ付き・暗号化ファイルは通常経路では拒否します。
PDFの自由な本文編集、真のredaction、署名・フォーム等の完全保持はページ操作CLIの対象外です。
特殊なOffice機能を含む文書は、最終的にOfficeアプリで確認します。

文書・抽出結果・PNGは指定した出力先に保存します。記憶DBや共有先へ自動送信しません。
ツールの変換処理はローカルですが、Codexに渡す文章・画像は利用中のCodexの処理方針に従います。
補助CLIの詳細は、[導入手順](installation.md#更新解除検査)の`--extract`で展開する同梱ガイドを参照してください。
