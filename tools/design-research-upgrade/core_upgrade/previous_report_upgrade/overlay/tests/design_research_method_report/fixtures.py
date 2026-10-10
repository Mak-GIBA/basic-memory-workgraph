"""Synthetic fixtures only. Sources below are fictional and are not research evidence."""
from __future__ import annotations
from copy import deepcopy
try:
    from .test_previous_ideation import complete
except ImportError:
    from test_previous_ideation import complete


def node(i, label, detail, component="", lane="proposal", change="unchanged"):
    return dict(id=i, label=label, detail=detail, component_id=component, lane=lane, change=change)


def edge(a,b,label,kind="flow"):
    return {"from":a,"to":b,"label":label,"kind":kind}


def fixture():
    ideas=complete()
    ideas["question"]="【表示確認用の架空例】検索の上位候補を、候補の局所密度を考慮して並べ替える設計を説明する。"
    ideas["task"]="固定済み特徴量を使う類似検索。実在の実験や論文を報告するものではない。"
    ideas["baseline"]["id"]="BASE"
    ideas["baseline"]["name"]="内積による候補検索"
    ideas["baseline"]["method"]="正規化した特徴量同士の内積で全候補を並べ、上位K件を返す。以下は表示確認用の仮想的な設計である。"
    names=["調整範囲を限定する最小改良", "特徴抽出器を置き換える改良", "候補密度を考慮した再ランキング", "特徴表現と後処理を組み合わせる案"]
    for i,c in enumerate(ideas["candidates"]):
        c["name"]=names[i]
    for i,s in enumerate(ideas["sources"],1):
        s["title"]=f"架空の一次資料{i}（構造テスト用・実在しません）"
        s["url"]=f"https://example.invalid/fictional-source-{i}"
    ideas["failure_modes"][0].update(symptom="問い合わせと関係の薄い頻出候補が繰り返し上位に現れるという仮想的な症状。", suspected_cause="候補の一般的な類似しやすさと、その問い合わせへの類似性を分けていないという原因仮説。")
    c=ideas["candidates"][2]
    c.update(
        core_hypothesis="全体の多くの入力に似てしまう候補は、真に近い候補より過剰に上位へ現れる可能性がある。局所密度による補正がその偏りを抑える、という未検証の仮説を置く。",
        mechanistic_explanation="まず従来と同じ内積検索で候補を集める。次に候補ごとの近傍類似度の平均を密度指標として引き、候補の順位を補正する。検索範囲や特徴抽出器を変えずに後処理だけを変更することで、特徴学習の効果とは切り分けて検証できる。ただし、密度が高い領域に本当に正解が多ければ、必要な候補まで下げてしまう可能性がある。",
        transfer_mapping="近傍分布による相対化という原理を、学習済みモデルの再学習ではなく検索結果の後処理へ移す。原典との照合はこの架空例では実施していない。",
        mathematical_specification="s(q,x_i) = q^T x_i\nrho_i = (1/k) sum_{j in N_k(i)} x_i^T x_j\ns_corrected(q,x_i) = s(q,x_i) - lambda * rho_i\noutput = topK_{i in C(q)} s_corrected(q,x_i)",
        pseudocode="# Preparation: use the reference corpus, not test-label feedback\nfor each corpus item i:\n    rho[i] = mean(inner_product(x[i], x[j]) for j in neighbors(i, k))\n# Query processing\nq = normalize(encode(query))\ncandidates = retrieve_by_inner_product(q, limit=L)\nfor i in candidates:\n    score[i] = inner_product(q, x[i]) - lambda_ * rho[i]\nreturn top_k(candidates, score, K)",
        integration_plan="既存の候補取得APIと出力形式は維持し、順位決定の直前に補正関数を追加する。候補ごとの密度は索引と同じ版で保存し、索引更新時に再計算する。",
        resource_tradeoff="問い合わせ時には候補数Lに比例する減算と再並べ替えが増える。事前の近傍探索と密度の保存には別の計算・記憶コストが必要である。実測値は存在しない。",
        prior_art_difference="密度補正そのものの新規性は主張しない。この例は、検索処理のどこを変更し何を固定するかを説明するための架空設計であり、実際の提案では最も近い既存法との同等性を調べる必要がある。",
        novelty_status="unverified",
        expected_failure_regime="最初の候補取得で正解が欠落した場合、再ランキングでは回復できない。また、密集領域に正解が集中する入力では補正が不利益になる可能性がある。",
        assumptions=["初期候補集合には評価したい正解が十分含まれる。", "参照集合の密度が索引更新後も対応している。"],
        testable_predictions=["頻出候補による誤検索が多い条件で効果が大きい、という仮説を検証する。"],
        critical_objections=["改善は密度補正ではなく、補正係数の探索予算が増えたためではないか。"],
        revision_actions=["調整予算を一致させ、係数ゼロと別の単純な再並べ替えも対照に含める。"],
    )
    ideas["selection"]["rationale"]="この案を説明対象にする理由は、特徴抽出器を固定して補正だけを切り替えられ、最小の対照実験で機序を調べられるためである。実験結果から優位性を確認したという意味ではない。"
    comps=[
        dict(id="M1",name="共通の候補取得",inputs="問い合わせ特徴量qと参照特徴量x_i",outputs="内積の大きい上位L件の集合C(q)",operation="従来と同じ索引、同じ特徴量、同じ探索設定で候補を取得する。",rationale="検索範囲の変更を混ぜず、後処理の効果に比較を限定する。",baseline_difference="この段階は変更しない。",cost="既存検索と共通。"),
        dict(id="M2",name="候補密度の推定",inputs="参照集合の正規化特徴量と近傍数k",outputs="各候補の近傍類似度の平均rho_i",operation="自分自身を除いたk近傍を集め、内積の平均を計算する。密度は参照集合から事前計算し、問い合わせ間で再利用する。",rationale="多くの参照項目に似る候補を、問い合わせからの類似性とは別の指標で捉える。",baseline_difference="従来は保持していなかった密度の値を追加する。",cost="参照集合の近傍探索と、項目数に比例するスカラー値の保存が増える。"),
        dict(id="M3",name="スコア補正と順位決定",inputs="候補集合C(q)、元の内積、rho_i、補正係数lambda",outputs="補正スコアが大きい上位K件",operation="候補ごとの内積からlambda倍の密度を引き、補正スコアで順位を決める。lambdaがゼロなら元の順位に戻る。",rationale="元の類似度を保持しつつ、頻出候補への偏りを相対的に弱める、という仮説に対応する。",baseline_difference="元の内積のみで並べ替えする処理を、密度補正後のスコアによる並べ替えに変える。",cost="上位L候補の補正と並べ替えが増える。問い合わせごとの全件近傍探索は行わない。"),
    ]
    overview=dict(
        id="F1",kind="architecture",title="提案手法の全体構成",caption="従来の候補取得を保ち、密度の事前計算とスコア補正を追加する。破線は使わず、実行時に受け渡す情報を実線で示す。",alt_text="問い合わせから共通の候補取得を経てスコア補正へ進み、別途準備した候補密度も入力して結果を返す図。",explanation="左側の問い合わせの流れと、右側の参照集合の準備を区別する。提案部分はM2とM3であり、M1を変えないことが比較条件になる。",component_ids=["M1","M2","M3"],
        nodes=[node("Q","問い合わせ","正規化特徴量q",lane="shared"),node("R","参照集合","正規化特徴量x_i",lane="shared"),node("A","候補の取得","同じ索引で上位L件","M1",lane="shared"),node("D","密度の事前計算","k近傍の平均類似度","M2",change="added"),node("S","スコア補正","内積から密度項を減算","M3",change="modified"),node("O","検索結果","補正後の上位K件")],
        edges=[edge("Q","A","問い合わせ特徴量q"),edge("R","A","参照索引"),edge("R","D","参照特徴量"),edge("A","S","候補と元スコア"),edge("D","S","事前計算したrho_i"),edge("S","O","順位")])
    detail=dict(
        id="F2",kind="module_detail",title="提案部分の内部処理",caption="候補の密度を準備する処理と、問い合わせ時の減算・並べ替えを分けて拡大した概念図。",alt_text="近傍を取得して平均類似度を計算し、その値を補正係数で重み付けして元スコアから減算する処理の図。",explanation="学習し直すのではなく、参照集合の密度だけを事前に計算する。補正係数はテスト結果を見ながら選ばず、検証集合で選ぶ。",component_ids=["M2","M3"],
        nodes=[node("N","自己を除くk近傍","参照集合内で求める","M2",change="added"),node("D","近傍類似度を平均","rho_iとして保存する","M2",change="added"),node("P","lambdaで重み付け","候補密度への補正量","M3",change="modified"),node("S","元スコアから減算","候補集合内で再並べ替え","M3",change="modified")],
        edges=[edge("N","D","近傍特徴量"),edge("D","P","rho_i"),edge("P","S","lambda * rho_i")])
    diff=dict(
        id="F3",kind="baseline_comparison",title="既存法と提案法の違い",caption="同じ特徴量と候補集合に対し、既存法は内積をそのまま使い、提案法だけが密度補正を加える。",alt_text="左の既存法は候補取得から元の内積で順位付けする。右の提案法は同じ候補取得の後に密度補正して順位付けする。",explanation="両列の最初の条件は揃える。提案法の実験には係数ゼロの対照も入れ、追加容量や探索予算だけでは説明できないかを調べる。",component_ids=["M1","M3"],
        nodes=[node("B1","共通の候補取得","同じ特徴量・索引・L","M1",lane="baseline"),node("P1","共通の候補取得","同じ特徴量・索引・L","M1"),node("B2","内積をそのまま使用","元のスコアで順位決定",lane="baseline"),node("P2","密度でスコア補正","rho_iを事前計算して使用","M3",change="modified"),node("B3","上位K件","同じ評価手順",lane="baseline"),node("P3","上位K件","同じ評価手順")],
        edges=[edge("B1","B2","元スコア"),edge("P1","P2","元スコア"),edge("B2","B3","順位"),edge("P2","P3","補正後の順位")])
    c["presentation"]=dict(
        overview="この架空例では、検索モデルを大型化せず、検索結果の並べ替え方だけを変える。多くの入力に似てしまう候補に小さな罰則を与えることで、問い合わせに固有の候補を浮かび上がらせる、という考え方である。",
        worked_example="たとえば、様々な問い合わせに毎回現れる候補と、その問い合わせにだけ近い候補があるとする。元の内積が似ていても、前者の局所密度が高いときは補正後に順位が下がる。この例は動作の説明であり、具体的な精度改善を観測した例ではない。",
        training="特徴抽出器は固定する。参照集合から候補密度を事前計算し、補正係数と近傍数は検証集合だけで選ぶ。",inference="問い合わせの特徴量で上位L件を検索し、保存済みの密度でスコアを補正して、上位K件を返す。",
        equation_explanation="第一式は元の類似度である。第二式は候補周辺の密度を表す。第三式で密度の高い候補に罰則を与え、第四式で補正後の順位を返す。係数ゼロで既存法に戻るため、対照条件を明確にできる。",
        evidence_scope="【合成入力・表示確認用】この章に用いる資料と実験記録は架空のテスト用データである。実験は未測定であり、図も性能の証拠ではない。",
        selection_note="これは説明する設計の暫定選定であり、実証済みの最良手法の選定ではない。比較で不利益が出れば既存法を維持する。",
        symbols=[dict(symbol="q, x_i",definition="問い合わせ・候補の正規化特徴量",shape="R^d、ノルム1"),dict(symbol="k, N_k(i)",definition="近傍数と自己を除く近傍集合",shape="kは1以上、参照件数未満"),dict(symbol="rho_i",definition="近傍との平均類似度",shape="実数スカラー"),dict(symbol="lambda",definition="検証集合で選ぶ補正係数",shape="0以上の実数"),dict(symbol="L, C(q), K",definition="初期候補数、候補集合、出力件数",shape="1 <= K <= L")],
        components=comps,differences=[dict(aspect="順位を決めるスコア",baseline="内積のみ",proposal="内積から候補密度を減算",tradeoff="密度と正解頻度が一致する領域では過補正に注意する。")],
        figures=[overview,detail,diff],verification=[dict(hypothesis="候補密度の補正が頻出候補への偏りを抑える。",experiment_id="E1",component_ids=["M2","M3"],alternative_explanation="追加の調整予算や一般的な再並べ替えの効果だけで説明できる。",rejection_condition="同予算の単純な再並べ替えと差がなく、頻出候補条件でも予測した傾向が見られなければ機序の説明を見直す。")])
    candidates=[dict(id="BASE",name=ideas["baseline"]["name"],baseline=True,summary=ideas["baseline"]["method"],hard_constraints=[])]
    candidates += [dict(id=x["id"],name=x["name"],baseline=False,summary=x["core_hypothesis"],hard_constraints=[]) for x in ideas["candidates"]]
    return dict(schema_version=1,question=ideas["question"],scope=ideas["task"],checked_as_of="2026-10-09",constraints=[],sources=deepcopy(ideas["sources"]),claims=[],candidates=candidates,comparison=[],experiments=[dict(id="E1",hypothesis="密度補正の寄与を条件を揃えて調べる。",status="planned",controls=["特徴量・候補数・評価分割・調整予算を固定する。"],metrics=["Recall@10と計算コスト"],acceptance="事前に定めた実用差と不確実性で判断する。",artifacts=[])],decision=dict(candidate_id="P3",status="provisional",rationale=ideas["selection"]["rationale"],unresolved=["実験未測定"],revisit_when=["公平な比較で利点が確認できない場合"]),method_ideas=ideas)
