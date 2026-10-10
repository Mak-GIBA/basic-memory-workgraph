# 保存単位と完了条件

新規runはexecution_contract_version=2を使用する。既存runは保存された契約のまま再開し、
旧state・報告をインストール時に移行・上書きしない。同一projectのロックと既存の隔離・時間・証拠制限を保持する。

研究は最小の実行可能設計、実行資材、親による実行と採点、候補ごとの原典確認、結果台帳、
必要な提案手法説明・読み手向け説明、項目別独立レビュー、台帳レビューに分ける。
約5候補を必要に応じて維持し、候補の詳細を単位ごとに確認する。文献を読むための時間は確保し、
1つの子工程に調査・数式・実装・図・完成版報告を集中させない。

精度・効果・性能の問いは主要な最終成果指標、対照条件、採点、期待出力を実行前に固定する。
親の実行記録に結びついた最終出力を採点し、同等・悪化も完了した結果として報告する。
設計・文献調査は原典に支えられた条件付き結論で完了できる。実験を無理に作らず効果未測定と記す。
auditは実際の確認・所見・独立レビューで完了し、対象の全動作の合格を意味しない。
runは依頼範囲の変更、実行による確認、独立レビューが揃ったときに完了する。

各単位は問い、入力、依存関係、必須性、出力ハッシュ、状態を保存する。原典・評価条件・実測は
要約だけで置き換えない。子には現在の役割に必要な情報だけを渡す。入力は指示込みで16 KiB以内とし、
大きい値は全文を保存したread_file/sha256/bytesの参照に変換する。意味を削る切り詰めは禁止する。
子はSKILL全体や全書式を読み直さず、名前で指定された契約と決定的な原典・成果物を読む。

検証済みの工程・実行結果は再開時にハッシュを確認して再利用する。完了した実験を繰り返さない。
実行中に停止して確定receiptがないコマンドは自動再実行せず、残った成果を保全して新しいrunで扱う。
入力・出力・実行記録が変わった場合は再利用を拒否する。モデル工程のtimeoutは方式の効果の不合格ではない。
時間上限の引き上げや無条件再試行を解決策にしない。

主要な実測は詳細説明より先に報告へ保存する。必須の追加確認・説明・レビューが残る間は
全体をresearch_complete/passedとして扱わない。最終報告には同一入力での基準案・候補案の
具体的な最終出力、主要指標、採用条件、結論の範囲、残る作業を示す。

Final dossier review returns `{base_sha256, replace:{changed_field: complete_value}}` in dossier_json. The base hash binds the saved full ledger; unchanged method/reader/figure sections are not regenerated. The parent reconstructs the full dossier, validates frozen identities, sources, receipts, figures and outcomes, and saves the validated full result. Criterion reviews and known ledger errors are passed into this final responsibility. Legacy full replies remain readable.
