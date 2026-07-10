# hyakunin-isshu-semantic-map

このリポジトリは、小倉百人一首と百人秀歌の歌順を、意味空間・隣接類似度・配列差分から探索する実験です。目的は、百人一首に秘密暗号があると主張することではありません。むしろ、藤原定家周辺の選歌・配列が、どのような主題的連続性や転換を持つのかを、計量的な地図として眺めることを目指します。

- Repository: <https://github.com/dueyama/hyakunin-isshu-semantic-map>
- GitHub Pages: <https://dueyama.github.io/hyakunin-isshu-semantic-map/>

## プロジェクトの位置づけ

本研究は、先行する公開リポジトリ `dueyama/buddhist-text-embedding-map` と `dueyama/honen-shinran-shared-core-map` の公開方式と方法意識を、和歌配列研究に移したものです。

引き継ぐ方針は次の通りです。

- HTML読み物、図表、再現コード、制作記録を同じリポジトリで管理する。
- GitHub Pages で読める公開物にする。
- 公開本文は日本語HTMLのみとし、英語版は当面作成しない。
- raw本文、未確認の翻刻、embedding vector、API key、ローカル絶対パスは公開しない。
- 図や数値を結論ではなく、読み直す場所を探すための地図として扱う。

百人一首版では、仏教文献で用いた「意味層・語彙層・典拠層」の考え方を、次の三層に置き換えます。

1. 意味層: 和歌本文、読み、注釈的パラフレーズの埋め込み。
2. 主題層: 季節、恋、雑、羇旅、哀傷、孤独、無常などのタグ。
3. 配列・出典層: 小倉順、百人秀歌順、出典勅撰集、巻、歌番号、歌人年代。

## 方法上の立場

このプロジェクトは、AIや統計モデルに和歌解釈を任せるためのものではありません。短い和歌を正規化し、主題タグや現代語パラフレーズを補助的に使い、意味空間上の近さ・遠さ・歌順のジャンプを可視化することで、人間が精読すべき箇所を探します。

意味埋め込みの近さは、藤原定家の意図、歌人間の影響、隠された政治的メッセージを直接証明しません。現代語訳やタグを使う場合も、それは原文そのものではなく、解釈を含む補助情報です。

このリポジトリの図や数値は、結論ではありません。読む場所を探すための地図です。

## 最初の問い

1. 小倉百人一首の隣接歌は、ランダム順より意味的に近いか。
2. 百人秀歌の順序と比べて、小倉百人一首はどの部分で大きく変わったか。
3. 意味空間上で孤立する歌はどれか。
4. 歌順の中で、大きな意味的ジャンプはどこにあるか。
5. 前半・後半、あるいは鏡像配置に対応らしきものはあるか。

## 公開物

今回は論文やPDFではなく、随時更新できるHTMLシリーズ記事として整備します。

- GitHub Pages entry point: `docs/index.html`
- Favicons: `docs/favicon.svg`, `docs/favicon.ico`
- Prologue HTML essay: `docs/paper/0/index.html`
- Chapter 1 HTML essay: `docs/paper/index.html`
- Chapter 2 HTML essay: `docs/paper/2/index.html`
- Chapter 3 HTML essay: `docs/paper/3/index.html`
- Final chapter HTML essay: `docs/paper/final/index.html`
- Update summary page: `docs/updates/index.html`
- Data source and license notes: `docs/data_sources.md`
- Method notes: `docs/method.md`
- Model notes: `docs/model_notes.md`
- First findings (2026-07-02 historical snapshot): `docs/first_findings.md`
- PCA figure: `docs/figures/semantic-pca-map.svg`
- PCA distribution figure: `docs/figures/semantic-pca-distribution.svg`
- Small-model PCA distribution figure: `docs/figures/semantic-pca-distribution-small.svg`
- Publication checklist: `docs/PUBLICATION.md`
- AI researcher guide: `AI_RESEARCHER_GUIDE.md`

PDF版・TeX版は作りません。HTML本文は固定版ではなく、文献確認や追加解析に応じて更新します。

## データ方針

本文・翻刻・画像は、提供元ごとの利用条件を確認してから扱います。ライセンスや再配布可否が未確認の本文・画像は `public/` や `docs/` に置きません。

現時点の方針は次の通りです。

- `data/hyakunin_isshu.csv`: Japanese Wikisource 由来の初期データ候補。CC BY-SA 3.0 として扱い、学術版・出典勅撰集との照合を要する。
- `data/hyakunin_shuka.csv`, `data/metadata_poets.csv`: 公開用の列構成だけを示すschema placeholder。解析に用いた百人秀歌本文・埋め込みは含まない。
- `data/*.csv`: 公開可能な範囲の最小データセット候補。出典と校訂方針を `docs/data_sources.md` に記録する。
- `data/raw/`: 取得元確認中のrawデータ置き場。GitHub公開対象に含めない。
- `public/data/*.json`: 旧ビューア・将来のWebアプリ用の生成データ。現行の日本語HTML読み物公開では使わない。
- embedding cache/vector: 公開しない。

## リポジトリ構成

```text
hyakunin-isshu-semantic-map/
  README.md
  AI_RESEARCHER_GUIDE.md
  data/
    hyakunin_isshu.csv
    hyakunin_isshu.normalized.csv
    hyakunin_shuka.csv
    metadata_poets.csv
  docs/
    index.html
    assets/
    figures/
    glossary/
    references/
    updates/
    data_sources.md
    method.md
    model_notes.md
    first_findings.md
    literature_notes.md
    PUBLICATION.md
    paper/
  scripts/
    build_dataset.py
    normalize_waka.py
    embed_texts.py
    analyze_sequence.py
    compare_orders.py
    layout_permutation.py
    analyze_shuka_layout_private.py
    analyze_ogura_layout_private.py
    analyze_shuka_base_shared_grid_private.py
    export_web_json.py
```

`_private/`、`data/raw/`、`data/embeddings/`、`docs/progress.md`、`public/data/` はローカル作業用または生成物用であり、GitHub公開対象には含めません。

## 再現性

初期の本文なし検証は、Python標準ライブラリだけで実行できます。

```bash
python3 -m py_compile scripts/*.py
python3 scripts/build_dataset.py --check
python3 scripts/export_web_json.py --omit-text
```

Wikisource raw wikitextを取得済みの場合、初期CSV候補は次のように再生成できます。

```bash
python3 scripts/import_wikisource_hyakunin.py --raw /path/to/hyakunin_wikisource_raw.txt
python3 scripts/normalize_waka.py
python3 scripts/analyze_sequence.py
python3 scripts/export_web_json.py --omit-text
```

埋め込みを実行する段階では、`docs/model_notes.md` にモデル名、入力形式、正規化、次元数、実行日、費用見積もりを記録します。

埋め込みキャッシュがある場合、初回PCAと隣接類似度は次のように再生成できます。

```bash
python3 scripts/analyze_embeddings.py
```

第2章・第3章の10×10検査コードも公開していますが、実行には公開リポジトリに含めない百人秀歌の作業用本文と埋め込みキャッシュが必要です。公開cloneだけで同じ集計を完全再生成できる、という意味ではありません。10×10のランダム基準は、同じ100首を固定した格子へ10,000回置き直す方法で、seedは `20260710` です。`numpy` があれば計算を高速化し、なくても標準ライブラリへフォールバックします。

## 現時点の初期所見

2026-07-02 の初回解析では、OpenAI `text-embedding-3-large` と `text-embedding-3-small` で `waka_original + waka_kana` を埋め込み、PCA地図と隣接類似度を作成しました。

- PCAでは、恋・身の嘆き側と、季節・自然景側が第1主成分方向にゆるく分かれます。
- `large` では、小倉順の平均隣接類似度は 0.4053、ランダム順10,000回の平均は 0.4047 で、全体平均としては明確な差は見えません。
- `small` では、小倉順の平均隣接類似度は 0.4146、ランダム順比較 percentile は 0.8721 で、やや順番らしさが出ます。
- H052-H053、H070-H071、H085-H086 などの局所的連続と、H093-H094、H098-H099 などの大きな転換点は、両モデルで比較する価値があります。

この節と `docs/first_findings.md` は、2026-07-02時点の初回解析記録です。現在の比較と解釈は、GitHub Pagesの第1章以降を参照してください。

## 公開方針

公開前には `docs/PUBLICATION.md` を確認します。特に次のものは公開しません。

- `.env`
- API key / token
- ライセンス未確認のraw本文、翻刻、画像
- embedding cache / embedding vector
- `_private/`, `docs/progress.md`, `docs/viewer/`, `public/data/`
- ローカル絶対パスを含む出力
- ローカルの一時生成物

## ライセンス

このリポジトリは分割ライセンスを採用します。

- 解析コードは MIT License です。`LICENSE-CODE` を参照してください。
- HTML読み物、図表、公開文書、制作プロセス、公開用派生データは Creative Commons Attribution 4.0 International (CC BY 4.0) です。`LICENSE-CONTENT` を参照してください。
- 外部提供元の本文・翻刻・画像、またそれを含むデータファイルは本リポジトリ独自のCC BY 4.0対象外です。`data/hyakunin_isshu.csv` とその本文由来列は Japanese Wikisource の CC BY-SA 3.0 表記に従います。その他の外部資料も各提供元の利用条件に従います。
