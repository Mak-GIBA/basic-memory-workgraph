# 参照先と利用範囲

確認日：2026-10-11。最新版の固定的な保証ではなく、今回の設計時点の記録。

- 既存インストーラー：Mak-GIBA/basic-memory-workgraph、commit f0efd23a53c1c1cd028775aa415cc3f34ca5661a。CLI、管理manifestのowner/schema、バックアップ・更新・編集保護の設計を継承。
  https://github.com/Mak-GIBA/basic-memory-workgraph
- 上流：nanaism/yomiyasu v1.1.1、commit 373356eb874af5184962c88e925ea7eb58450318。実際の推敲規則とlint/diffは上流原本を利用し、インストール時に取得する。MITとUNICODE-LICENSE.txtを保持する。
  https://github.com/nanaism/yomiyasu/releases/tag/v1.1.1
- coji/natural-japanese：書く前の構成設計、検出と判断の分離を設計比較に使用。コード・スキル本文を取り込んだり、追加インストールしたりしない。
  https://github.com/coji/natural-japanese
- tqkqt0/humanizer-jp：日本語の定型表現、応答残り、書き手の文体への適合を比較。コード・スキル本文は同梱しない。
  https://github.com/tqkqt0/humanizer-jp
- bamboo-nova/meiseki：意味を保持した明晰化、読みやすさと個性付与の区別を比較。コード・スキル本文は同梱しない。
  https://github.com/bamboo-nova/meiseki
- Purdue OWL, On Paragraphs：一段落一論点、統一性、つながり、主題文という一般的な段落原則を参照。記事本文は転載しない。
  https://owl.purdue.edu/owl/general_writing/academic_writing/paragraphs_and_paragraphing/index.html
- Harvard College Writing Center, Anatomy of a Body Paragraph：主題、根拠、その解釈の関係と、不必要な末尾再要約を避ける考え方を参照。記事本文は転載しない。
  https://writingcenter.fas.harvard.edu/anatomy-body-paragraph
- OpenAI, Build skills：SKILL.md、参照資料、ユーザー配置、明示・暗黙選択の仕様を確認。
  https://developers.openai.com/codex/skills/

独自の日本語本文・例文・検査ロジックは、この提案のために作成した。上流の本文は上流フォルダに分離し、著作権表示とライセンスを変更しない。
