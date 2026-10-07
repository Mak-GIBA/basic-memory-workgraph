# 認知負荷の少ないUI/UX設計Tips

## 1. 一度に注意を向けさせる情報を減らす

### 原則

画面上の情報量や要素数が増えるほど、ユーザーは目的の情報を見つけるために多くの視覚探索を必要とする。

特に問題になるのは、単純な要素数ではなく、

- 重要度の異なる情報が大量に並んでいる
- 異なる種類の情報が混在している
- 複数の操作目的が同一画面に存在する
- 同じ強さで多数の要素が主張している

状態である。

### 具体的な方法

- その画面の**Primary Taskを1つ明確にする**
- Primary / Secondary / Detail の優先順位をつける
- 低頻度機能は常時表示しない
- 補足情報は詳細領域へ移す
- 関連性の低いニュース、広告、説明、装飾を削る
- 重要でないカードやウィジェットをDashboardに大量配置しない

### 悪い例

```text
Dashboard

売上
ユーザー数
広告
ニュース
お知らせ
ランキング
キャンペーン
レポート
チャット
おすすめ
新機能
管理設定
```

### 改善例

```text
Dashboard

今日確認すべきKPI
├ 売上
├ コンバージョン率
└ 異常アラート

今日のタスク
├ 承認待ち 3件
└ 要確認 2件

詳細レポート >
```

### ポイント

**「情報を減らす」こと自体が目的ではない。**

減らすべきなのは、

> ユーザーの注意を奪い合う情報

である。

---

# 2. 同じ画面に異なる「目的」を混ぜすぎない

## 原則

Visual Complexityは、

- 情報量
- 情報密度
- 要素の種類
- 配置
- 文脈の切り替え

によって増える。

特に、異なる目的の情報が同一画面に混在すると、ユーザーは頻繁にContext Switchingを行う必要がある。

## 具体的な方法

1画面の情報を、

- 顧客情報
- 請求
- 分析
- 管理設定
- コミュニケーション

など、意味的なまとまりで分離する。

### 悪い例

```text
顧客詳細

基本情報
請求履歴
チャット
売上グラフ
管理者設定
おすすめ商品
契約変更
ニュース
```

### 改善例

```text
顧客概要
├ 基本情報
├ 最近の活動
└ 次に必要なアクション

契約
├ 契約内容
├ 請求
└ 支払い

分析
├ 利用状況
└ 売上分析
```

## 設計時の確認

> この画面を見たユーザーは、「ここで何をする場所なのか」を数秒で説明できるか？

できなければ、目的を混ぜすぎている可能性が高い。

---

# 3. 要素数だけでなく「要素の種類」を減らす

## 原則

同じ形式の情報が10個並ぶことより、

```text
グラフ
フォーム
動画
広告
チャット
テーブル
ニュース
通知
```

のように異なる種類の要素が8個並ぶ方が、認知的に複雑になることがある。

ユーザーは各要素について、

> 「これは何なのか」

を解釈し直さなければならないためである。

## 具体的な方法

- 同じ種類の情報は同じUIパターンに統一する
- 同じ意味のステータスには同じ表現を使う
- Card / Table / Listを必要以上に混在させない
- 情報表現方式を画面内で頻繁に変更しない
- 操作方法を統一する

## 例

悪い：

```text
ステータスA → 緑色カード
ステータスB → アイコン
ステータスC → テキスト
ステータスD → バッジ
```

良い：

```text
[Active]
[Pending]
[Error]
[Completed]
```

同一パターンとして表現する。

---

# 4. ユーザーに「覚えながら操作」させない

## 原則

人間がWorking Memory上で同時に保持できる情報には強い制約がある。

そのため、

> 前の画面で見た情報を覚えて、次の画面で使う

設計は避ける。

## 悪い例

```text
画面A

Customer ID
58327

↓

画面B

Customer IDを入力してください
[             ]
```

ユーザーは `58327` を記憶する必要がある。

## 改善例

```text
Customer ID
58327

注文情報
...
```

必要なContextを次画面にも保持する。

## 具体的な方法

- 選択した対象名を次画面にも表示する
- 入力済み内容を保持する
- 前回選択したフィルタを保持する
- 最近使用した項目を表示する
- 比較対象を同時表示する
- コピー&ペースト前提の設計にしない
- 前画面と現在画面を往復させない

## チェックポイント

> この操作を完了するために、ユーザーが何かを頭の中に覚えておく必要があるか？

ある場合、画面側に保持できないか検討する。

---

# 5. RecallではなくRecognitionを使う

## 原則

ユーザー自身に情報を思い出させるより、

> **候補を見せて選ばせる**

方が認知負荷は小さい。

---

## 具体的な方法

### 検索

悪い：

```text
Search
[                     ]
```

改善：

```text
Search
[machine lear...]

machine learning
machine learning model
machine learning dataset
```

---

### 最近使用したもの

表示すると効果的なもの：

- Recent files
- Recent projects
- 最近使用したテンプレート
- 最近使用した検索条件
- 最近開いた顧客
- 最近利用したPrompt

---

### コマンド

悪い：

```text
コマンドを覚えて入力してください
```

良い：

```text
Undo last commit
Create branch
Merge branch
```

---

### アイコン

頻度の低い機能をIcon onlyにすると、

> このアイコンは何だったか？

を思い出す必要がある。

そのため、

```text
✎ Edit
🗑 Delete
↗ Share
```

のようにLabelを併記する。

---

# 6. 初回チュートリアルに依存しすぎない

## 原則

最初に大量の操作方法を説明し、

> 「あとは覚えて使ってください」

という設計はRecall依存になる。

## 改善方法

### 初回

```text
ようこそ

ここではプロジェクトを作成できます。
[プロジェクトを作成]
```

### 実際に必要になった場面

```text
API Key

ⓘ API KeyはSettings > APIから確認できます
```

つまり、

> **説明を必要なタイミングで出す**

Contextual Helpを使う。

## 有効なUI

- Tooltip
- Inline Help
- Empty State
- Contextual Tip
- Example
- Placeholder
- Help Popover

---

# 7. 関連する情報は近くに置く

## 原則

関連情報が離れていると、ユーザーは、

```text
探す
↓
読む
↓
覚える
↓
元の場所へ戻る
↓
対応付ける
```

必要がある。

これはSplit Attentionを発生させる。

## 代表的な適用例

### フォームエラー

悪い：

```text
ページ上部

入力エラーがあります


...


メール
[abc]
```

良い：

```text
メール
[abc]

有効なメールアドレスを入力してください
```

---

### グラフ

悪い：

```text
[グラフ]


画面下部

青 = 今年
灰 = 昨年
点線 = 予測
```

良い：

可能な限り、

- 線の近く
- グラフ内
- 直近のLegend

に意味を表示する。

---

### 設定画面

悪い：

```text
Advanced Mode [ ON ]

詳細はマニュアルを参照
```

良い：

```text
Advanced Mode ⓘ
[ ON ]

高度な設定項目を表示します。
```

---

# 8. 比較するものは同時に見せる

## 原則

比較対象を別々に見せると、

> Aを覚えたままBを見る

必要がある。

これもWorking Memoryを消費する。

## 悪い例

```text
Plan Aを見る
↓
戻る

Plan Bを見る
↓
戻る

Plan Cを見る
```

## 改善例

|         |  Basic |    Pro | Enterprise |
| ------- | -----: | -----: | ---------: |
| 価格      | ¥1,000 | ¥3,000 |        要相談 |
| Storage |   10GB |  100GB |  Unlimited |
| API     |      × |      ○ |          ○ |
| Support |  Email |  Email |  Dedicated |

## 適用領域

特に、

- 料金プラン
- 商品比較
- AIモデル比較
- Candidate比較
- Before / After
- 設定差分
- 権限比較

では有効。

---

# 9. 情報をChunkとしてまとめる

## 原則

Working Memoryでは、個々の情報をバラバラに扱わせるより、

> 意味のあるまとまり

として認識させる方が扱いやすい。

## 悪い例

```text
名前
住所
会社
メール
役職
電話
支払い
契約
請求
```

## 改善例

```text
基本情報
├ 名前
├ 会社
└ 役職

連絡先
├ メール
├ 電話
└ 住所

契約
├ 契約
├ 支払い
└ 請求
```

## 有効な方法

- Section
- Group
- Heading
- Card
- Accordion
- Tabs
- Whitespace
- Divider

を使う。

ただし、

> Cardを使えばChunkになる

わけではない。

**意味的に関連している情報をまとめること**が重要。

---

# 10. 情報の重要度を視覚化する

## 原則

すべての情報を同じ強さで表示すると、

ユーザー自身が、

> どこを見るべきか

判断しなければならない。

Signalingによってその判断をUI側が支援する。

## 具体的な方法

使えるCue：

- Heading
- Font Size
- Font Weight
- Whitespace
- Alignment
- Position
- Numbering
- Highlight
- Section
- Progress Indicator

## 悪い例

```text
売上 ¥12M
ユーザー 2,400
エラー 23
ニュース
アップデート
支払い設定
キャンペーン
```

すべて同じVisual Weight。

## 改善例

```text
要対応

⚠ エラー 23件


主要KPI

売上       ¥12M
ユーザー   2,400


その他

ニュース >
アップデート >
```

---

# 11. Primary Actionを明確にする

## 原則

同じ強さのボタンが多数存在すると、

> どれを押すべきか

という意思決定コストが増える。

## 悪い例

```text
[保存]
[保存して閉じる]
[次へ]
[プレビュー]
[キャンセル]
[共有]
```

全部同じスタイル。

## 改善例

```text
[保存して次へ]

保存
キャンセル
```

## ポイント

Primary CTAを1つに絞ることが理想だが、

業務画面などで複数操作が必要な場合でも、

**視覚的な優先順位を明確にする。**

---

# 12. 不要な情報・装飾を削る

## 原則

追加された情報は、それぞれ他の情報とユーザーの注意を奪い合う。

そのため、

> 情報がある方が親切

とは限らない。

## 削除候補

- Decorative Illustration
- Hero Image
- 意味の薄いIcon
- 重複説明
- 不要なAnimation
- 低頻度のShortcut
- 使用頻度の低いWidget
- 無関係なNews
- 過剰なBadge
- 過剰なColor coding

## 判断基準

各要素について、

> **これがなくなることで、ユーザーのTask Completionが悪化するか？**

を考える。

Noなら削除候補。

---

# 13. 同じ情報を重複して見せすぎない

## 原則

「同じ情報を複数形式で出せば親切」とは限らない。

## 悪い例

```text
✓ Success

成功しました

処理は正常に成功しました。

SUCCESS
```

## 改善例

```text
✓ 保存しました
```

必要であれば、

```text
✓ 保存しました

更新時刻 14:32
```

程度でよい。

## 注意

Accessibility対応としての、

- Captions
- Alt text
- Screen reader用Label

まで削ってよいという意味ではない。

---

# 14. Feedbackは操作直後に出す

## 原則

ユーザーの操作と結果が時間的に離れると、

> この結果は自分の操作によるものか？

が分かりにくくなる。

Temporal Contiguityを意識する。

## 良い例

```text
[保存]

↓

Saving...

↓

✓ Saved
```

## 悪い例

ユーザーが保存した後、

何のFeedbackもなく、

5秒後に画面右下へToastだけ表示される。

## 特に重要な操作

- Save
- Upload
- Delete
- Submit
- Payment
- Deploy
- AI Generation
- API Call

では、状態変化を即座に表示する。

---

# 15. システム状態を画面上に残す

## 原則

ユーザーが、

> 今何が起きているか

を覚えたり推測したりする必要を減らす。

## 表示すべき状態

- Loading
- Saving
- Saved
- Uploading
- Processing
- Failed
- Completed
- Selected
- Filtered
- Draft
- Published

## 悪い例

```text
[Generate]
```

押しても何も変わらない。

ユーザー：

> 押せた？
> 処理している？
> もう一回押す？

````

## 改善例

```text
Generating...

Step 2 / 4

Generating summary...
````

---

# 16. 中断しても復帰しやすくする

## 原則

ユーザーは、

- 通知
- 電話
- Meeting
- 別タスク
- Browser Tab

などで頻繁に作業を中断する。

そのため、

> 中断前の状態を頭の中だけに保持させない

ことが重要。

## 具体的な方法

- Draft保存
- Auto Save
- Current Step
- Last Edited
- Selected Item
- 完了済みStep
- 未完了Task
- Recent Activity

を残す。

## 例

```text
申請作成

Step 3 / 5
「支払い情報」

✓ 基本情報
✓ 契約内容
→ 支払い情報
  確認
  送信
```

これだけでも復帰時の認知負荷が大きく下がる。

---

# 17. 「次に何をすればよいか」を明確にする

## 原則

情報を理解できても、

> 次に何をすればよいか分からない

UIは認知負荷が高い。

## 良い設計

```text
プロジェクトがありません。

最初のプロジェクトを作成すると、
分析を開始できます。

[プロジェクトを作成]
```

悪い設計：

```text
No Data
```

だけ表示する。

## 適用場所

- Empty State
- Error
- Onboarding
- Completion
- Permission Error
- Setup
- Configuration

---

# 18. メニュー名から行き先を予測できるようにする

## 原則

ユーザーはNavigation Labelを見て、

> そこに目的の情報がありそうか

を判断する。

意味が曖昧なラベルは探索コストを増やす。

## 悪い例

```text
その他
管理
ツール
詳細
Advanced
Resources
```

## 改善例

```text
通知設定
ユーザー管理
API設定
請求
アクセス権限
ログ
```

## 判断基準

> メニュー名だけを見せても、何が入っているか予想できるか？

---

# 19. Progressive Disclosureは「何でも隠す」ために使わない

## 原則

画面をシンプルにするために情報を隠すと、

Visual Complexityは下がる。

しかし同時に、

- Click
- Search
- Expansion
- Navigation

が増えてInteraction Complexityが上がる場合がある。

## 推奨される分類

### 常時表示

意思決定やTask Completionに必須。

```text
価格
主要ステータス
エラー
Primary Action
```

### Contextual

現在の操作に応じて必要。

```text
入力エラー
補助説明
関連設定
```

### Progressive Disclosure

あるユーザーには必要。

```text
詳細分析
追加フィルタ
ログ
```

### Advanced

ごく一部のExpert向け。

```text
API設定
Debug
Fine tuning parameter
```

---

# 20. Summary → Detail の階層を作る

## 原則

詳細情報を全部削除する必要はない。

むしろ、

> 最初に概要を理解でき、その後必要なら詳細へ進める

構造が有効。

## 例

```text
モデル評価

Accuracy
92.4%

主な問題
・Class BのRecallが低い

[詳細指標を見る]
```

詳細：

```text
Confusion Matrix
Precision
Recall
F1
Per-class metrics
Threshold analysis
```

これにより、

初心者はSummaryだけ、

Expertは詳細まで利用できる。

---

# 21. 認知負荷を「ゼロ」にすることを目的にしない

## 原則

重要なポイントとして、

> Cognitive Loadが低ければ低いほど良い

とは限らない。

例えば、

```text
申請は却下されました。
```

だけ表示すれば非常にシンプルだが、

ユーザーは理由を理解できない。

## より良い設計

```text
申請は却下されました。

主な理由
本人確認情報が一致していません。

[詳細を見る]
```

多少情報量は増えるが、

- Understanding
- Trust
- Learning
- Decision Making

は改善する。

## 目標

最小化すべきなのは、

> **Taskに必要のない認知負荷**

である。

---

# 22. Visual ComplexityだけでなくInteraction Complexityも見る

画面がシンプルでも、

```text
クリック
↓
クリック
↓
展開
↓
別画面
↓
戻る
↓
別画面
```

が必要なら認知負荷は高い。

そのため、

```text
Visual Complexity
+
Interaction Complexity
```

の両方を見る。

## チェック項目

- Click数
- 画面遷移数
- Backtracking
- Accordion展開回数
- Modal数
- Context Switching
- 再入力
- 同じ情報の再検索

---

# 23. 見た目の「シンプルさ」と認知的な「シンプルさ」を分ける

例えば、

```text
⚙
☰
⋮
+
◇
```

だけのUIは見た目としてはMinimalである。

しかしユーザーが、

> このアイコンは何だろう？

と考えるなら、認知負荷は高い。

一方、

```text
Settings
Menu
More
Create
```

と書いてある方がVisual Complexityは多少増えても理解は容易。

したがって、

> **Minimal Appearance ≠ Minimal Cognitive Load**

である。

---

# 24. 視覚的な一貫性を維持する

## 原則

同じ意味なのにUI表現が毎回変わると、そのたびに新しいルールとして学習する必要がある。

## 統一すべきもの

- Button
- Link
- Error
- Warning
- Status
- Modal
- Navigation
- Selection
- Delete
- Save

## 例

削除操作を、

```text
Page A → ゴミ箱Icon
Page B → Remove
Page C → Delete
Page D → 赤い×
```

のように変えない。

---

# 25. Errorでは「原因」と「次の行動」をセットで示す

## 悪い例

```text
Error 400
```

## 改善例

```text
CSVをアップロードできませんでした。

必須列「customer_id」がありません。

CSVにcustomer_id列を追加し、
もう一度アップロードしてください。

[再アップロード]
```

ユーザーが、

- 原因
- 解決策
- 次の操作

を推測しなくて済む。

---

# 26. 空白を情報構造として使う

Whitespaceは単なる装飾ではない。

適切なWhitespaceによって、

```text
A
B
C
D
E
F
```

を、

```text
A
B
C


D
E


F
```

のように意味単位へ分けられる。

## 注意

Whitespaceを増やしすぎて、

- スクロールが極端に増える
- 関連情報が離れる
- 比較対象を同時表示できない

場合は逆効果。

---

# 27. 頻度に応じて操作を配置する

## 推奨

### 高頻度

常時表示。

```text
Save
Search
Create
```

### 中頻度

MenuやToolbar。

### 低頻度

More / Settings。

### Expert向け

Advanced。

これによって、

**利用頻度の低い機能がPrimary Taskの探索を邪魔することを防ぐ。**

---

# 28. ユーザーが推測しなければならない箇所を減らす

認知負荷の高いUIでは、頻繁に、

```text
これは何？
どこを押す？
何が起きた？
どこにある？
次は何？
これとこれは何が違う？
前に何を選んだ？
```

という推論が必要になる。

したがってUIレビューでは、

> **ユーザーが推測している箇所を探す**

という視点が非常に有効。

---

# 29. 認知負荷を下げるUIの6つの基本操作

これまでの研究をかなり圧縮すると、UI設計でやるべきことは次の6つに整理できる。

## 1. Reduce

不要なものを減らす。

- Noise
- Decoration
- Low priority information
- Duplicate information

---

## 2. Group

関連情報をまとめる。

- Semantic Group
- Section
- Chunk

---

## 3. Prioritize

重要度を示す。

- Primary
- Secondary
- Detail

---

## 4. Externalize

覚えさせず、画面に残す。

- Current State
- Previous Selection
- Recent Items
- Comparison

---

## 5. Colocate

関連情報を近づける。

- Error ↔ Input
- Label ↔ Object
- Description ↔ Setting

---

## 6. Guide

次の行動を示す。

- Primary Action
- Next Step
- Progress
- Contextual Help

---

# UIレビュー用チェックリスト

## 情報量

- [ ] Primary Taskと関係のない情報が目立っていない
- [ ] 低頻度機能がPrimary Actionと競合していない
- [ ] 不要な装飾が多すぎない
- [ ] 情報の種類が多すぎない

## 情報構造

- [ ] 関連情報がまとまっている
- [ ] Primary / Secondary / Detailが分かる
- [ ] Sectionの意味が明確
- [ ] 画面の目的が1つにまとまっている

## Memory

- [ ] 前画面の情報を覚える必要がない
- [ ] 比較対象を同時に見られる
- [ ] 入力・選択状態が保持される
- [ ] Recent Itemsが必要に応じて表示される

## Recognition

- [ ] 選択肢が見えている
- [ ] Iconだけに依存していない
- [ ] Search Suggestionが利用できる
- [ ] メニューの意味を推測しなくてよい

## Split Attention

- [ ] Errorが対象Fieldの近くにある
- [ ] Helpが対象設定の近くにある
- [ ] GraphのLegendが離れすぎていない
- [ ] 比較対象が別画面に分断されていない

## Navigation

- [ ] メニュー名から内容を予測できる
- [ ] 現在地が分かる
- [ ] 次に進む場所が分かる
- [ ] 不要な画面往復がない

## Progressive Disclosure

- [ ] 必須情報を隠していない
- [ ] Advanced機能だけを適切に隠している
- [ ] Accordionの開閉が多すぎない
- [ ] 「シンプルに見せるためだけ」に隠していない

## Feedback

- [ ] 操作後すぐ状態が変化する
- [ ] Loading / Saving / Completedが分かる
- [ ] Error時に原因が分かる
- [ ] Error時に次のActionが分かる

---

# 最重要ポイント

認知負荷を下げるUIとは、

> **「情報が少ないUI」ではなく、ユーザーが頭の中で処理しなければならないことが少ないUI**

である。

特に減らすべきなのは、ユーザーが行う次の処理である。

- **覚える**
- **探す**
- **比較する**
- **対応付ける**
- **推測する**
- **行き来する**
- **状態を把握する**
- **次に何をすべきか考える**

したがって、UIレビュー時には、

> **「この画面では、ユーザーは頭の中で何をしなければならないか？」**

を考えるとよい。

その処理をUI側へ外部化できれば、認知負荷の少ないUIに近づく。

---

# 実務上特に優先すべき10項目

まず以下の10項目を守るだけでも効果が大きい。

1. **1画面1Primary Taskを基本にする**
2. **重要情報と補助情報を明確に分ける**
3. **ユーザーに情報を覚えさせない**
4. **RecallではなくRecognitionを使う**
5. **関連情報は近くに置く**
6. **比較対象は同時に表示する**
7. **入力エラーは対象Fieldの近くに表示する**
8. **操作結果を即座にFeedbackする**
9. **低頻度・Advanced機能だけProgressive Disclosureする**
10. **「何をすればよいか」を常に分かる状態にする**

## 参考となる主な研究・文献

- Baughan et al., *Keep it Simple: How Visual Complexity and Preferences Impact Search Efficiency on Websites*, CHI 2020
- Harper, Michailidou & Stevens, *Toward a Definition of Visual Complexity as an Implicit Measure of Cognitive Load*, ACM TAP, 2009
- Chandler & Sweller, *The Split-Attention Effect as a Factor in the Design of Instruction*, 1992
- Mayer & Fiorella, *Principles for Reducing Extraneous Processing in Multimedia Learning*
- Nielsen Norman Group, *Recognition Rather Than Recall*
- Nielsen Norman Group, *Aesthetic and Minimalist Design*
- Cowan, *The Magical Number 4 in Short-Term Memory*, 2001
- Kosch et al., *A Survey on Measuring Cognitive Workload in Human-Computer Interaction*, ACM Computing Surveys
- Anik & Bunt, *Designing Effective Training Dataset Explanations: The Impact of Information Depth and Progressive Disclosure*, IUI 2026
