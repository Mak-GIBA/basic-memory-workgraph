# 参照元と確認範囲
確認日: 2026-09-21。公式公開資料を参考に作った独自プロファイルです。
規格・書籍の全文、ベンダーのSkill本文、フォント等は同梱していません。ISO完全準拠の主張もしません。

1. ISO/IEC/IEEE 29148:2018 公開概要
   https://www.iso.org/standard/72089.html
   要求工学の活動と情報項目を整理する標準の位置付けを参照。規格全文を監査したものではありません。
2. NASA Systems Engineering Handbook, 6.2 Requirements Management
   https://www.nasa.gov/reference/6-2-requirements-management/
   双方向追跡、根拠、派生要求、変更影響と承認を参考にしています。
3. NASA Appendix C: How to Write a Good Requirement
   https://www.nasa.gov/reference/appendix-c-how-to-write-a-good-requirement/
   明確さ・単一性・WHAT/HOWの分離・根拠・検証可能性の点検観点を参照しています。
4. arc42 Overview
   https://arc42.org/overview/
   コンテキスト、構成、実行時、配置、設計判断、品質・リスクの説明範囲を参考にしています。
5. Wiegers / Beatty, Software Requirements, 3rd Edition, Microsoft Press
   https://www.microsoftpressstore.com/store/software-requirements-9780735679665
   出版社の公開説明・目次でビジネス要求/ユーザー要求/品質/既存システム/追跡管理の扱いを確認。
   書籍全文を読み込んで条項準拠を検査したものではありません。
6. GitHub Spec Kit v1.0.8
   https://github.com/github/spec-kit/releases/tag/v1.0.8
   https://raw.githubusercontent.com/github/spec-kit/v1.0.8/docs/installation.md
   https://raw.githubusercontent.com/github/spec-kit/v1.0.8/docs/guides/existing-projects.md
   https://raw.githubusercontent.com/github/spec-kit/v1.0.8/docs/reference/integrations.md
   公式PyPI/GitHubの配布、Codex Skill、同梱資材の初期化、既存導入時の注意を参照。
7. Codex Skills
   https://developers.openai.com/codex/skills
   ユーザー共通~/.agents/skillsと、プロジェクト固有のSkill探索先を参照。

IREBの教材も前段の方針検討で挙げましたが、このターンでは該当公開ファイルを取得できませんでした。
今回の実装説明をそのファイルに依存させず、上記の確認できた資料を根拠にしています。
