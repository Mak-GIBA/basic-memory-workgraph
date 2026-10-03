# Office Workbench — PDF・Word・PowerPointを扱う

[docs一覧](../README.md) · [導入手順](installation.md) · [使い方](usage.md)

PDF、DOCX、PPTXの閲覧・作成・部分編集と、原本の保護・差分・描画確認を支援します。
[install_codex_office.sh](../../install_codex_office.sh)は単体で使えます。
引数なしでは予定を表示し、`--apply`でツールを導入します。

## 導入するもの

| ツール・資材 | 提供元 | 用途 |
|---|---|---|
| OfficeCLI 1.0.153と参照資料 | OfficeCLI | Office文書の操作。既存バイナリの明示再利用も可能 |
| MarkItDown | Microsoft | PDF・DOCX・PPTXの文章抽出 |
| PDF・Office用のPythonライブラリ | 各ライブラリの提供元 | PDFのページ操作・抽出・画像化、限定したOffice編集 |
| 入口Skillと`office-workbench` | このリポジトリ | 原本保護、作業コピー、差分、描画確認の補助 |

標準ではMCPを登録しません。必要な場合だけ`--with-mcp`を指定します。
複雑なPDFの構造解析には、任意のDocling環境を追加できます。
追加キットはこのリポジトリ独自の実装です。Microsoft・OpenAI・OfficeCLIの公式統合製品ではありません。

## 表示の確認

Office文書の全ページ画像化にはLibreOffice、日本語の表示には適切なフォントが必要です。
Word・PowerPoint本体と同じ表示は保証しません。特殊な図形、フォント、アニメーション等は最終的にOfficeアプリで確認します。
MarkItDownの抽出結果を、元のレイアウトを保持する往復変換には使いません。

詳細な同梱ガイドは`--extract`で展開できます。導入は[導入手順](installation.md)、
最初の編集と確認は[使い方](usage.md)を参照してください。
