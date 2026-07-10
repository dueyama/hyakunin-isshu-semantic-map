# Model Notes

最終更新: 2026-07-10

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
