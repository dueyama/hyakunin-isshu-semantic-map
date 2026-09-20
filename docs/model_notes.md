# Model Notes

最終更新: 2026-09-20

## 制作支援と判定モデル

2026-09-20の季節比較補章、全首一覧、Luna根拠付き追加実験は、Codex GPT-6 Astra Ultraの支援で分析・実装・本文整理を行い、まとめた。これは比較を構成する制作支援モデルの記録であり、各歌のAPI判定モデルは下記Run 4のTypeSafe Jev、Run 5・6のOpenAI GPT-5.6-Lunaである。根拠語句・短い説明はRun 6のLuna生成出力を掲載している。

従来章のCodex GPT-5.6 Sol Ultraと、それ以前のモデル・レビュー協力の履歴は[更新履歴](updates/)に残す。

## Run 1: OpenAI embedding large, original + kana

- 実行日: 2026-07-02
- モデル名: `text-embedding-3-large`
- 提供元: OpenAI API
- 入力データ: `data/hyakunin_isshu.csv`
- 対象: 小倉百人一首 100首
- 入力形式: `original_kana`
- 入力テキスト:
  - `waka_original` を `scripts/normalize_waka.py` で保守的に正規化。
  - `waka_kana` を同じく正規化。
  - 両者を改行で結合。
- 正規化:
  - Unicode NFKC。
  - 空白、句読点、括弧類の除去。
  - 歴史的仮名遣い、踊り字、語形は勝手に現代化しない。
- ベクトル正規化:
  - OpenAIの埋め込みは長さ1に正規化されたベクトルとして返る仕様である。
  - このため、cosine similarity、内積、ユークリッド距離による近傍順位は同じになる。
- 次元数: 3072。
- 埋め込みキャッシュ:
  - `data/embeddings/hyakunin_isshu_original_kana_text-embedding-3-large.json`
  - このファイルは非公開。`.gitignore` 対象。
- 当時生成した派生データ:
  - `public/data/embeddings_pca.json`
  - `public/data/adjacency_stats.json`
  - `public/data/pair_rankings.json`
  - `docs/viewer/viewer_data.json`
  - `docs/figures/semantic-pca-map.svg`
  - `docs/figures/semantic-pca-distribution.svg`
- 現行公開方針:
  - 現行の公開本文は `docs/` 以下の記事と図版である。
  - `public/data/*.json` と `docs/viewer/` は、旧ビューアや再解析時に作られるローカル生成物として扱い、GitHub公開対象には含めない。
  - 本文で必要な図は `docs/figures/` に置く。
- 派生データの本文方針:
  - poem text は含めない。
  - embedding vector は含めない。
  - 歌番号、歌人名、主題タグ、出典候補、PCA座標、類似度統計のみを含める。

## Projection

- PCA実装: centered Gram matrix + pure Python power iteration。
- PCA seed: `20260702`。
- PCA寄与率:
  - PC1: 0.06239951833603717
  - PC2: 0.05253483625740732
- UMAP: 未実行。依存パッケージ未導入のため、Run 1 では標準ライブラリだけで PCA を作成した。
- t-SNE: 未実行。

## Sequence Statistics

- 類似度: cosine similarity。
- 対象: 小倉順の99隣接ペア。
- 比較: ランダム順10,000回。
- ランダム seed: `20260702`。
- 小倉順 平均隣接類似度: 0.40530104632649677。
- ランダム順 平均: 0.40471218799658787。
- z-score: 0.09682795209180234。
- percentile: 0.5447。

## Run 2: OpenAI embedding small, original + kana

- 実行日: 2026-07-02
- モデル名: `text-embedding-3-small`
- 提供元: OpenAI API
- 入力データ: `data/hyakunin_isshu.csv`
- 対象: 小倉百人一首 100首
- 入力形式: `original_kana`
- 入力テキスト、正規化方針: Run 1 と同じ。
- ベクトル正規化:
  - OpenAIの埋め込み仕様上、長さ1に正規化されたベクトルとして返る。
  - 小倉100首の実測ノルムは 0.9996 から 1.0004 の範囲に収まった。
- 次元数: 1536。
- 埋め込みキャッシュ:
  - `data/embeddings/hyakunin_isshu_original_kana_text-embedding-3-small.json`
  - このファイルは非公開。`.gitignore` 対象。
- 生成した派生データ:
  - `public/data/embeddings_pca_small.json`
  - `public/data/adjacency_stats_small.json`
  - `public/data/pair_rankings_small.json`
  - `docs/viewer/viewer_data_small.json`
  - `docs/figures/semantic-pca-map-small.svg`
  - `docs/figures/semantic-pca-distribution-small.svg`

Run 2 PCA寄与率:

- PC1: 0.06746465245248022
- PC2: 0.049302596261112434

Run 2 sequence statistics:

- 小倉順 平均隣接類似度: 0.41463621786095756。
- z-score: 1.149。
- percentile: 0.8721。

## Large / Small Comparison

| 指標 | large | small |
|---|---:|---:|
| 次元数 | 3072 | 1536 |
| PC1+PC2寄与率 | 0.1149 | 0.1168 |
| 同主題ペア平均類似度 | 0.4161 | 0.4215 |
| 異主題ペア平均類似度 | 0.4010 | 0.4032 |
| 同主題 - 異主題 gap | 0.0151 | 0.0184 |
| 最近傍が同主題の率 | 0.420 | 0.400 |
| 上位5近傍の同主題率 | 0.448 | 0.426 |
| 小倉順平均隣接類似度 | 0.4053 | 0.4146 |
| ランダム順比較 z-score | 0.0968 | 1.149 |
| ランダム順比較 percentile | 0.5447 | 0.872 |

観察:

- `small` は平均隣接類似度のランダム順比較で、`large` より高く出た。
- 主題分離は、同主題/異主題の平均類似度 gap では `small` がやや大きいが、最近傍・上位5近傍の同主題率では `large` がやや高い。
- 全ペア類似度の large/small 相関は 0.6483 で、完全には同じ地図ではない。
- 大きなジャンプの共通候補は H009-H010、H041-H042、H068-H069、H093-H094、H098-H099。
- 隣接類似度上位の共通候補は H001-H002、H006-H007、H052-H053、H067-H068、H070-H071、H085-H086。

## Run 3: 10×10 random-placement comparison

- 更新日: 2026-07-10。
- モデル名: `text-embedding-3-small`。
- 入力形式: 作業用 `original`。第1章の `original_kana` とは別条件。
- 対象: 百人秀歌101首、小倉百人一首100首。
- ベクトル: 非公開キャッシュ。公開物には含めない。
- 近傍: 上下左右180組、斜めを含む8近傍342組。
- ランダム基準: 同じ100首を固定した10×10格子へ無作為に置き直す。
- 試行数: 10,000回。
- seed: `20260710`。
- 主な再集計値:
  - 百人秀歌からS076を枠外に置く斜めつづら折り、上下左右 percentile 0.9514、z-score 1.685。
  - 小倉の螺旋置き、上下左右 percentile 0.9364、z-score 1.535。
  - 百人秀歌基準で共通97首を固定し小倉三首を入れる最良8近傍条件、percentile 0.9877、z-score 2.322。
- 旧集計は、格子の境界と隣接依存を保たない任意ペア抽出を比較基準にしていた。格子シャッフルへ修正しても主要な配置順位と解釈の方向は変わらなかったが、公開数値と図は再生成した。

## Cost Note

API実行時に厳密な使用トークン数と課金額は記録していない。100首のみのため費用は小さいと考えられるが、HTML本文に料金を書く場合は、実行時点の OpenAI pricing page と API usage dashboard で確認してから記載する。

## Interpretation Note

この run は、古語本文と読みだけを使った最初の意味空間である。現代語訳、詞書、出典文脈、歌枕、本歌取り、注釈的パラフレーズは入っていない。したがって、図は「和歌の意味そのもの」ではなく、モデルが本文と読みから捉えた近さの初期地図として扱う。

## Next Model Comparisons

次に比較したい入力条件:

- `original`: 漢字かな交じり本文のみ。
- `kana`: 読みのみ。
- `original_tags`: 本文 + 主題/季節タグ。
- `all`: 本文 + 読み + 主題/季節タグ + 注記。
- 注釈的パラフレーズを加えた入力。ただし訳者・作成者の解釈を含むことを明記する。

次に比較したいモデル:

- multilingual-e5 系
- sentence-transformers 多言語モデル
- 日本語特化 embedding モデル

## Run 4: Jev season comparison

- 実行日: 2026-09-20。TypeSafe `jev-1.13.0` を固定指定。
- 対象: 小倉100首、百人秀歌101首。共通97首を独立標本として二重に解釈しない。
- 小倉入力: 正規化した `waka_original + waka_kana`。秀歌入力: 正規化した `waka_original`。
- 既存タグ、歌番号、歌人名、部立、埋め込みは判定入力に含めない。
- 英語の7質問: 主な季節のChoice、四季への言及のNoul、恋・自然描写のNoul。質問全文は `scripts/jev_seasons.py`。
- 有効応答201件の使用量: 入力239,351 / 出力35,654トークン。S053の初回応答はChoice整合性検証で不合格となり、再取得した有効応答を採用。初回無効応答の使用量は記録できておらず、請求全量は未確定。
- 小倉の季節タグ33首に対し31首一致。空欄67首を負例にしない。
- 四季に分類された集合内の上位5近傍の同季節率: 小倉small39首で0.5436（無作為期待0.3536）、秀歌small45首で0.5067（同0.3606）。
- ラベル置換: seed `20260920`、10,000回。図は既存PCA実装とseed `20260702` を共用。
- H010・H053の保存ベクトルは過去の表記修正前の入力。修正前表記を再構成してハッシュ一致を確認し、旧座標を図に残して今回の統計から除外。新たなOpenAI埋め込み生成はなし。
- Jevの確信度は正解率ではない。共通歌の一致81/97、秀歌の確信度中央値0.59という結果から、古語表記に対する検証が必要。
- 再現方法・限界: [Jev季節比較の方法](jev_season_method.md)。集計: [JSON](jev-season-summary.json)。読者向け: [補章](paper/seasons/)。

## Run 5: GPT-5.6-Luna seasonal comparison and reference divisions

- 実行日: 2026-09-20。APIモデル `gpt-5.6-luna`（実応答のモデルIDも検証）。
- Responses API、推論 `medium`、`max_output_tokens=4096`、`store=false`。
- Jevと同じ正規化本文・主季節の指示・七択基準。ID・作者・部立・Jevの回答は渡さない。補助6問や生成説明文・自己申告の確信度は取得しない。
- 小倉100首: Jevとの一致95/100。文献に季節明示のある33首ではGPT33/33、Jev31/33。これは資料との対応数であって、全首や古典和歌一般の正解率ではない。
- 四季共通37首ではモデル間のラベルが全て一致する。同じ歌・同じグラフで近傍統計も一致することは、新たな独立の性能確認にはならない。
- 小倉100首・秀歌101首の全201首で完了。秀歌はJevとの一致82/101、資料の季節明示35首ではGPT35/35、Jev27/35。共通97首の小倉・秀歌間一致はGPT97/97、Jev81/97。
- GPTの有効201応答の使用量: 入力67,539 / 出力17,854 / 合計85,393トークン。各首の判定と集計は [モデル比較JSON](season-comparison.json) を参照。
- 文献側: 嵯峨嵐山文華館の100首と日文研の秀歌独自4首の出典歌を参照。H026「雑（秋）」を含む季節注記33首と、四季部立32首を区別。秀歌共通歌は小倉側の参照であり、異文判定の正解には扱わない。
- [全首一覧](paper/seasons/list/)は既公開の本文を参照し、各モデル出力と資料の部立を別列に置く。[再現手順](jev_season_method.md)。

## Run 6: GPT-5.6-Luna with evidence and explanations

- 実行日: 2026-09-20。Run 5の本文・主季節指示・七択・推論medium・出力上限を保ち、根拠語句（最大2個×8字）と180字以内の日本語説明を追加した別条件。
- 201首すべて取得。Run 5からの変更はH012季節不特定→秋、S005冬→秋。モデルが説明を出すことと、正しい解釈であることを同一視しない。
- 共通97首の歌集間一致95/97。資料の季節明示との一致33/33・34/35。反復対照がないため、説明要求による効果を単独で推定しない。
- 使用量: 入力96,885 / 出力39,335 / 合計136,220トークン。生応答は元条件と別の非公開cacheに保存。
- 根拠句の逐語不一致4首を一覧で注記、全文引用の差し止め0首。モデル生成の説明を無修正で載せ、文学的注釈とは区別する。
- [全201首の根拠・説明](paper/seasons/luna-reasons/) / [条件・集計JSON](luna-reasoned-comparison.json) / [再現方法](jev_season_method.md)。
