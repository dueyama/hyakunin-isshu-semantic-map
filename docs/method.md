# Method Notes

最終更新: 2026-07-02

## 目的

小倉百人一首の歌順、隣接関係、主題配置を、百人秀歌や出典勅撰集の位置と比較しながら探索します。目的は暗号や隠された政治的意図を発見することではなく、どの歌の近くを読み直すべきかを見つけることです。

## 三層モデル

先行する仏教文献埋め込み地図の「意味層・語彙層・典拠層」を、百人一首では次のように置き換えます。

1. 意味層
   - 和歌本文のみの埋め込み。
   - 和歌本文 + 読みの埋め込み。
   - 和歌本文 + 注釈的パラフレーズの埋め込み。
2. 主題層
   - 季節、恋、雑、羇旅、離別、哀傷、自然景、孤独、老い、無常などの手作業タグ。
   - LLM補助タグは `auto_tag` として分ける。
3. 配列・出典層
   - 小倉百人一首の現行順。
   - 百人秀歌順。
   - 出典勅撰集、巻、歌番号、部立。
   - 歌人の時代、身分、性別、系譜。

## 入力データ

`data/hyakunin_isshu.csv` の必須列:

```csv
id,poet_jp,poet_kana,waka_original,waka_kana,kami_no_ku,shimo_no_ku,source_anthology,source_book,source_number,theme,season,notes
```

`data/hyakunin_shuka.csv` の必須列:

```csv
shuka_order,hyakunin_id,poet_jp,waka_original,waka_kana,notes,variant_group
```

`data/metadata_poets.csv` の必須列:

```csv
hyakunin_id,poet_jp,period,approx_year,birth_year,death_year,status,gender,lineage,notes
```

## 正規化

`scripts/normalize_waka.py` で次を行います。

- Unicode NFKC正規化。
- 空白、改行、句読点、括弧類の整理。
- 踊り字や歴史的仮名遣いは、初期段階では勝手に現代仮名へ変換しない。
- 原文表記、読み、解析用正規化テキストを別列で保持する。

## Embedding

初期候補:

- OpenAI embeddings
- multilingual-e5 系
- sentence-transformers 多言語モデル
- 日本語特化 embedding モデル

短い和歌だけでは埋め込みが不安定になる可能性があるため、次の入力を比較します。

- `waka_original`
- `waka_kana`
- `waka_original + waka_kana`
- `waka_original + notes/paraphrase`
- `waka_original + theme + season`

### Run 1

2026-07-02 の初回解析では、OpenAI `text-embedding-3-large` を使い、`waka_original` と `waka_kana` を保守的に正規化して改行結合した `original_kana` 入力を embedding した。100首の embedding vector は `data/embeddings/` に非公開キャッシュとして保存し、公開用には本文とvectorを含まないPCA座標・類似度統計だけを書き出した。

Run 1 では外部依存パッケージを追加せず、PCAを標準ライブラリだけで実装した。UMAPは未実行であり、次段階で追加する。

## 可視化

まず PCA と UMAP を作ります。t-SNEは後回しにします。

表示候補:

- Overview Map: 100首の地図。小倉順・百人秀歌順の線を切替。
- Sequence View: 隣接類似度と距離ジャンプ。
- Pair Explorer: 類似度上位/下位、隣接、鏡像、二首一組。
- Comparison View: 小倉順と百人秀歌順の移動量。
- Notes / Method: データ出典、前処理、モデル、限界。

## 隣接類似度

小倉百人一首の隣接99ペアについて、cosine similarityを計算します。

比較対象:

- ランダム順 10,000回。
- 歌人年代順。
- 出典勅撰集順。
- 百人秀歌順。

出力:

- 平均隣接類似度。
- 中央値。
- 上位10ペア。
- 下位10ペア。
- ランダム順に対する z-score / percentile。
- bootstrap confidence interval。

## 距離ジャンプ解析

歌順に沿った意味空間上の移動距離を計算します。

見るもの:

- 大きなジャンプがどこにあるか。
- ジャンプ前後で主題・時代・身分・出典が変わるか。
- 「章」の切れ目らしき場所があるか。

## 対応関係

機械的に抽出する関係:

- 隣接ペアの意味類似度。
- 2首ごとのペア平均類似度。
- 奇数番/偶数番での主題差。
- 前半50首と後半50首の対応。
- `i` 番と `101-i` 番の鏡像対応。
- 百人秀歌との差分で移動距離が大きい歌。

## 統計的検定

最低限、次を実装します。

- permutation test。
- bootstrap confidence interval。
- ランダムseedの記録。
- multiple testing の注意書き。

p値だけで文学的意味を主張しません。

## 初回結果の扱い

Run 1 では、小倉順の平均隣接類似度はランダム順とほぼ同程度だった。したがって現時点では、「小倉順全体がランダム順より意味的に近い」とは主張しない。

一方で、隣接類似度が高い箇所と大きなジャンプははっきり抽出できる。初期段階では、全体平均よりも、H052-H053、H070-H071、H084-H085、H085-H086 のような局所的連続と、H042-H043、H093-H094、H098-H099 のような転換点を精読候補として扱う。

## 解釈上の注意

- 埋め込みの近さは、撰者意図の証明ではない。
- 主題タグは研究者の解釈を含む。
- 現代語訳やパラフレーズは訳者・作成者の解釈を含む。
- UMAPやPCAの図だけから強い結論を出さない。
- 百人秀歌との違いは、成立論・伝本論・注釈史と照合する必要がある。
